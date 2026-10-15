"""Stages 3, 5-11: the Monte Carlo engine.

Pipeline per national draw
  1  participating voters V ~ user-specified range (scenario assumption), mapped to ballots and valid ballots by the turnout grid
  2  polls -> posterior of list strength at the election date (Kalman filter, house effects, election-day miss)  [polls.py]
  3  events dated after the last poll -> mixture of voter-realignment scenarios (cfg_event_scenarios); never double counts polls
  4  closure: valid votes = minority lists (bottom-up, minority.py) + other non-minority lists (prior) + polled lists (posterior)
  5  seats: exact legal rules applied to every draw, with the threshold base and uplift scope of cfg_parameters
     (all alternatives are computed from the SAME draws and reported as sensitivity)
  6  coalition arithmetic (coalitions.py)
Municipal layer (a subset of the same draws): turnout by unit (calibrated to the draw's V), minority votes by unit pattern,
the remaining votes distributed by IPF so that unit totals add up to the unit's valid votes and list totals to the national draw.

Nothing electoral is typed in: every observation comes from the BigQuery tables, every assumption from cfg_* tables.
"""
import dataclasses
import pathlib

import numpy as np
import pandas as pd

import allocation as AL
import coalitions as CO
import electoral_law as EL
import local_swing as LS
import minority as MI
import polls as PO
import turnout as TU
import voteshare as VS
from backend import normalize_df
from pipeline import CONFIG_DIR


# ------------------------------------------------------------------------------------------------ parameters
class Params(dict):
    """cfg_parameters as typed values, with helpers for ';'-separated lists."""

    def list(self, key):
        return [x.strip() for x in str(self[key]).replace(',', ';').split(';') if x.strip()]

    def floats(self, key):
        return [float(x) for x in self.list(key)]


def parse_params(df):
    out = Params()
    for r in df.itertuples():
        t, v = str(r.value_type), r.param_value
        if t in ('float',):
            out[r.param_key] = float(v)
        elif t == 'int':
            out[r.param_key] = int(float(v))
        elif t == 'bool':
            out[r.param_key] = str(v).strip().lower() == 'true'
        else:
            out[r.param_key] = v
    return out


@dataclasses.dataclass
class Scenario:
    """A named deviation from the baseline. Everything not set here is read from cfg_parameters."""
    name: str = 'baseline'
    turnout_range: tuple = None               # (low, high) participating voters
    shift_log: dict = dataclasses.field(default_factory=dict)       # list_key -> additive shift of log(list / reference)
    transfers: list = dataclasses.field(default_factory=list)       # dicts(from_key, to_key, mean, concentration or None)
    use_event_mixture: bool = True            # baseline mixture of realignment scenarios (only if uncaptured events exist)
    poll_overrides: dict = dataclasses.field(default_factory=dict)  # design_effect, election_error_sd, leave_out, ...
    threshold_denominator: str = None
    uplift_scope: str = None
    minority_status_override: dict = dataclasses.field(default_factory=dict)   # list_key -> bool
    param_overrides: dict = dataclasses.field(default_factory=dict)            # cfg_parameters keys replaced for this scenario only
    description: str = ''


# ------------------------------------------------------------------------------------------------ model container
class Model:
    """Everything the engine reads, loaded once from the backend (BigQuery or the DuckDB stand-in)."""

    def __init__(self, be):
        q = lambda t: normalize_df(be.query(f'SELECT * FROM `{{DS}}.{t}`'))
        self.P = parse_params(q('cfg_parameters'))
        P = self.P
        self.panel = q('s2_unit_panel').sort_values('geo_id').reset_index(drop=True)
        self.geo_base = q('s6_unit_geography_base')
        self.min_base = q('s7_minority_unit_base')
        self.ufv = q('s1_unit_family_votes')
        self.nat_family = q('s1_national_family')
        self.polls_panel = q('s5_poll_panel')
        self.events = q('s5_event_panel')
        self.markets = q('s5_market_panel')
        self.local = q('s4_local_swing_panel')
        self.status = q('s0_municipality_status')
        self.registry = q('cfg_list_registry_2026')
        self.roster_map = q('cfg_minority_roster_map')
        self.roster_map['analog_family'] = self.roster_map.analog_family.replace('', np.nan)
        self.origin_weights = q('cfg_origin_weights')
        self.event_cfg = q('cfg_event_scenarios')
        self.coalitions = q('cfg_coalitions')
        self.mandates = q('ext_mandates')
        self._build_roster()
        self._build_poll()
        self._build_events()
        self._build_geography()
        self._build_local()
        self._turnout_cache = {}

    # -------- roster
    def _build_roster(self):
        P, reg = self.P, self.registry
        live = reg[reg.status == 'proclaimed'].reset_index(drop=True)
        ref, targets = P['poll_reference_list_key'], P.list('poll_target_list_keys')
        self.ref, self.targets = ref, targets
        self.polled = [ref] + targets
        is_min = dict(zip(live.list_key, live.minority_status_reported.str.lower().eq('yes')))
        self.minority_keys = list(self.roster_map.list_key)
        missing = [k for k in self.polled if k not in is_min]
        if missing:
            raise ValueError(f'polled lists not on the proclaimed roster: {missing}')
        if any(is_min[k] for k in self.polled):
            raise ValueError('a polled list is marked as a minority list: polled-list closure assumes non-minority lists')
        roster_min = {k for k, v in is_min.items() if v}
        if roster_min != set(self.minority_keys):
            raise ValueError(f'minority lists on the roster {sorted(roster_min)} differ from cfg_minority_roster_map {sorted(self.minority_keys)}')
        self.other_keys = [k for k in live.list_key if not is_min[k] and k not in self.polled]
        self.keys = self.polled + self.other_keys + self.minority_keys
        self.nonmin_keys = self.polled + self.other_keys
        self.is_minority = np.array([is_min[k] for k in self.keys])
        self.names = dict(zip(live.list_key, live.list_name_reported))
        absent = [k for k in self.nonmin_keys if k not in set(self.origin_weights.list_key)]
        if absent:
            raise ValueError(f'lists without a geography in cfg_origin_weights: {absent}')

    # -------- polls
    def _build_poll(self):
        P = self.P
        dd = pd.to_datetime(P['election_target_date'])
        self.election_date = dd
        self.poll = PO.aggregate(self.polls_panel, self.ref, self.targets, dd, tau_h_floor=P['poll_house_sd_floor'],
                                 sigma_rw_per_day=P['poll_rw_sd_per_day'], sigma_election=P['poll_election_error_sd'],
                                 design_effect=P['poll_design_effect'], default_sample=P['poll_default_sample'], prior_sd=P['poll_prior_sd'])
        self.last_poll_date = self.poll['last_poll_date']

    def poll_for(self, overrides):
        """Poll posterior under a scenario's overrides (design effect, election error, leave-one-house-out, ...).

        Leave-one-house-out: a list polled ONLY by the omitted pollster would revert to the (very weak) prior and distort the whole
        composition. Such coordinates are therefore held at their full-sample posterior (mean, variance; cross-covariances set to
        zero) and listed in `held_at_full_sample`; the sensitivity applies to the lists the remaining pollsters do observe."""
        if not overrides:
            return self.poll
        P = self.P
        kw = dict(tau_h_floor=overrides.get('tau_h_floor', P['poll_house_sd_floor']),
                  sigma_rw_per_day=overrides.get('rw_sd_per_day', P['poll_rw_sd_per_day']),
                  sigma_election=overrides.get('election_error_sd', P['poll_election_error_sd']),
                  design_effect=overrides.get('design_effect', P['poll_design_effect']),
                  default_sample=P['poll_default_sample'], prior_sd=P['poll_prior_sd'], leave_out=overrides.get('leave_out'))
        res = PO.aggregate(self.polls_panel, self.ref, self.targets, self.election_date, **kw)
        res['held_at_full_sample'] = []
        lo = overrides.get('leave_out')
        if lo:
            obs, _ = PO.prepare_log_ratios(self.polls_panel, self.ref, self.targets, default_sample=P['poll_default_sample'],
                                           design_effect=kw['design_effect'])
            seen = {i for o in obs if o['house'] != lo for i in o['idx']}
            full = PO.aggregate(self.polls_panel, self.ref, self.targets, self.election_date, **{**kw, 'leave_out': None})
            for i in range(len(self.targets)):
                if i not in seen:
                    res['mean'][i] = full['mean'][i]
                    res['cov'][i, :] = 0.0
                    res['cov'][:, i] = 0.0
                    res['cov'][i, i] = full['cov'][i, i]
                    res['held_at_full_sample'].append(self.targets[i])
        return res

    # -------- events: only events the polls cannot have captured can trigger the realignment mixture
    def _build_events(self):
        ev = self.events.copy()
        types = set(self.P.list('event_activation_types'))
        ev['ref_date'] = ev.event_date.fillna(ev.report_date)
        ev['after_last_poll'] = ev.ref_date > self.last_poll_date
        ev['activation_type'] = ev.event_type.isin(types)
        self.events_annotated = ev
        mix = self.event_cfg[self.event_cfg.in_baseline_mixture.astype(bool)]
        self.mixture = {}
        for sid, g in mix.groupby('scenario_id', sort=False):
            self.mixture[sid] = dict(weight=float(g.baseline_weight.iloc[0]), trigger=str(g.trigger_origin_entity.iloc[0]),
                                     transfers=self._transfers_of(g))
        triggers = {m['trigger'].lower() for m in self.mixture.values() if m['trigger']}
        hit = ev[ev.after_last_poll & ev.activation_type & ev.origin_entity.fillna('').str.lower().isin(triggers)]
        self.uncaptured_events = hit
        self.mixture_active = len(hit) > 0 and len(self.mixture) > 0

    @staticmethod
    def _transfers_of(g):
        conc = g[g.param == 'transfer_beta_concentration']
        out = []
        for r in g[g.param == 'transfer_mean'].itertuples():
            c = conc[(conc.from_list_key == r.from_list_key) & (conc.to_list_key == r.to_list_key)]
            out.append(dict(from_key=r.from_list_key, to_key=r.to_list_key, mean=float(r.value),
                            concentration=float(c.value.iloc[0]) if len(c) else None))
        return out

    def sensitivity_scenarios(self):
        """Scenarios defined in cfg_event_scenarios that are NOT part of the baseline mixture (added on top of the baseline)."""
        out = []
        sens = self.event_cfg[~self.event_cfg.in_baseline_mixture.astype(bool)]
        for sid, g in sens.groupby('scenario_id', sort=False):
            sh = {r.to_list_key: float(r.value) for r in g[g.param == 'shift_log'].itertuples()}
            out.append(Scenario(name=sid, shift_log=sh, transfers=self._transfers_of(g), description=str(g.scenario_name.iloc[0])))
        return out

    # -------- geography
    def _build_geography(self):
        P, pn = self.P, self.panel
        self.unit_ids = pn.geo_id.tolist()
        self.W0 = VS.build_unit_weights(self.geo_base, self.origin_weights, self.nonmin_keys, self.unit_ids)
        ids = self.nat_family.drop_duplicates('election_id').sort_values('election_date').election_id.tolist()
        self.prev_id, self.curr_id = ids[-2], ids[-1]
        free = pd.Series(((~pn.fixed_rate.astype(bool)) & (pn.is_special_electorate == 0)).values, index=pn.geo_id.values)
        wts = pn.set_index('geo_id').valid_baseline
        reg = pn.set_index('geo_id').region_id
        self.swing = VS.swing_dispersion(self.ufv, self.prev_id, self.curr_id, wts, reg, free)
        cap, dflt = P['swing_sd_cap'], P['swing_sd_default']
        unit_sd = {f: min(float(v), cap) for f, v in self.swing.sd_unit_total.items() if np.isfinite(v)}
        reg_sd = {f: min(float(v), cap) for f, v in self.swing.sd_region_means.items() if np.isfinite(v)}
        self.sigma_unit = VS.list_sigmas(self.origin_weights, self.nonmin_keys, unit_sd, dflt) * P['unit_swing_sd_multiplier']
        self.sigma_region = VS.list_sigmas(self.origin_weights, self.nonmin_keys, reg_sd, dflt * 0.5) * P['region_swing_sd_multiplier']
        regions = pn.region_id.fillna('SPECIAL').astype(str)
        self.region_codes, self.region_index = np.unique(regions, return_inverse=True)
        self.min_struct = MI.build_structures(self.roster_map, self.min_base, self.unit_ids, pn.region_id.values,
                                              pn.registered_baseline.values)
        sd, n_u, mu = TU.estimate_unit_sd(pn.valid_ratio_baseline_over_prior.values, pn.valid_baseline.values, free.values)
        self.turnout_sd = sd * P['unit_turnout_sd_multiplier']
        self.turnout_sd_info = dict(sd=sd, n_units=n_u, national_log_change=mu)

    # -------- local information (descriptive + scenario; never a substitute for parliamentary shares)
    def _build_local(self):
        P, loc = self.P, self.local
        col = P['local_swing_outcome']
        self.local_use = loc[loc[col].notna()].copy()
        y = self.local_use[col].astype(float).values
        w = self.local_use.baseline_registered.astype(float).values
        self.local_summary = LS.t_summary(y, weights=w, levels=tuple(P.floats('interval_levels'))) if len(y) >= 3 else None
        self.local_assoc = LS.association(y, self.local_use.turnout_change_pp.astype(float).values) if len(y) >= 4 else None
        # deviation of each observed municipality from the observed (register-weighted) mean, in relative terms of its 2023 lead share
        dev_pp = y - np.average(y, weights=w) if len(y) else np.array([])
        d = pd.Series(dev_pp / (100.0 * self.local_use.lead_share_valid_2023.astype(float).values), index=self.local_use.geo_id.values)
        self.local_log_dev = d.reindex(self.unit_ids).fillna(0.0).values
        self.recent_local_mask = self.status.set_index('geo_id').reindex(self.unit_ids).local_status.eq('recent_local_results_in_dataset').values

    # -------- turnout grid
    def turnout_grid(self, lo, hi, method='logit_shift'):
        key = (round(lo), round(hi), method)
        if key in self._turnout_cache:
            return self._turnout_cache[key]
        pn, P = self.panel, self.P
        grid = np.linspace(lo, hi, max(int(P['turnout_grid_points']), 2))
        ballots_pv, valid_pv = [], []
        for v in grid:
            r = TU.calibrate(pn.registered_target.values, pn.turnout_rate_baseline.values, v, fixed=pn.fixed_rate.astype(bool).values, method=method)
            voters = pn.registered_target.values * r
            b, inv, val = TU.ballots_and_valid(voters, pn.ballots_per_turned_out_baseline.values, pn.invalid_rate_baseline.values,
                                               P['invalid_rate_multiplier_baseline'])
            ballots_pv.append(b.sum() / v)
            valid_pv.append(val.sum() / v)
        self._turnout_cache[key] = (grid, np.array(ballots_pv), np.array(valid_pv))
        return self._turnout_cache[key]


# ------------------------------------------------------------------------------------------------ national draws
def _children(seed, n):
    return [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(n)]


def draw_national(model, n, scenario=None, seed=None):
    """Monte Carlo draws of the national outcome under one scenario. Common random numbers: a component's stream depends only on
    the seed, so two scenarios with the same seed differ only through what the scenario changes."""
    sc = scenario or Scenario()
    P = Params(model.P)
    P.update(sc.param_overrides)
    seed = P['random_seed'] if seed is None else seed
    r_turn, r_poll, r_ev, r_oth, r_min = _children(seed, 5)
    lo, hi = sc.turnout_range or (P['turnout_voters_low'], P['turnout_voters_high'])
    if P['turnout_draw'] != 'uniform_between_low_and_high':
        raise NotImplementedError(f"turnout_draw={P['turnout_draw']!r}")
    V = r_turn.uniform(lo, hi, size=n)
    grid, bpv, vpv = model.turnout_grid(lo, hi)
    ballots = V * np.interp(V, grid, bpv)
    valid = V * np.interp(V, grid, vpv)

    # polls
    pl = model.poll_for(sc.poll_overrides)
    z = r_poll.multivariate_normal(pl['mean'], pl['cov'], size=n, method='cholesky')
    for k, dlt in sc.shift_log.items():
        if k == model.ref:
            z = z - dlt
        else:
            z[:, model.targets.index(k)] += dlt
    p = PO.draws_to_shares(z)                                    # columns: [reference] + targets
    pcol = {k: i for i, k in enumerate(model.polled)}

    # realignment events: only if the data contain events the polls cannot have captured
    comp_id = np.full(n, -1)
    mix_names = list(model.mixture)
    u_ev = r_ev.random(n)
    u_beta = r_ev.random((n, 8))      # reserved uniforms for Beta draws (unused slots are harmless)
    tau_used = np.zeros((n, 0))
    if sc.use_event_mixture and model.mixture_active:
        w = np.array([model.mixture[m]['weight'] for m in mix_names])
        comp_id = np.searchsorted(np.cumsum(w / w.sum()), u_ev, side='right').clip(0, len(mix_names) - 1)
    transfer_log = []
    def _apply(tr, rows, rng_u):
        mean, conc = tr['mean'], tr['concentration']
        if conc is None:
            tau = np.full(rows.sum(), mean)
        elif mean <= 0:
            tau = np.zeros(rows.sum())
        else:
            from scipy import stats
            tau = stats.beta.ppf(rng_u[rows], mean * conc, (1 - mean) * conc)
        fi, ti = pcol[tr['from_key']], pcol[tr['to_key']]
        moved = p[rows, fi] * tau
        p[rows, ti] += moved
        p[rows, fi] -= moved
        transfer_log.append((tr['from_key'], tr['to_key'], rows, tau))
    for ci, m in enumerate(mix_names):
        rows = comp_id == ci
        if rows.any():
            for ti, tr in enumerate(model.mixture[m]['transfers']):
                _apply(tr, rows, u_beta[:, ti % u_beta.shape[1]])
    for ti, tr in enumerate(sc.transfers):
        _apply(tr, np.ones(n, bool), u_beta[:, ti % u_beta.shape[1]])

    # other non-minority lists (prior) and minority lists (bottom-up)
    o_share = np.exp(np.log(P['other_nonminority_share_median']) + r_oth.normal(0, P['other_nonminority_share_sdlog'], size=n)).clip(max=0.25)
    split = r_oth.dirichlet(np.full(len(model.other_keys), P['other_nonminority_split_concentration']), size=n) if model.other_keys else np.zeros((n, 0))
    base_valid = float(model.panel.valid_baseline.sum())
    mvotes, phi = MI.simulate_votes(model.min_struct, n, np.log(valid / base_valid), P, r_min)
    mvotes = mvotes.copy()
    other_total = o_share * valid
    polled_pool = valid - mvotes.sum(axis=1) - other_total
    if (polled_pool <= 0).any():
        raise ValueError('closure failed: minority + other lists exceed valid votes in some draw')
    votes_cont = np.zeros((n, len(model.keys)))
    votes_cont[:, :len(model.polled)] = p * polled_pool[:, None]
    votes_cont[:, len(model.polled):len(model.nonmin_keys)] = split * other_total[:, None]
    votes_cont[:, len(model.nonmin_keys):] = mvotes
    votes = np.rint(votes_cont)

    is_min = model.is_minority.copy()
    for k, v in sc.minority_status_override.items():
        is_min[model.keys.index(k)] = bool(v)
    den = {'voters_turned_out': V, 'ballots_cast': ballots, 'valid_ballots': valid}
    return dict(scenario=sc, keys=model.keys, is_minority=is_min, V=V, ballots=ballots, valid=valid, denominators=den,
                votes_cont=votes_cont, votes=votes, poll_shares=p, phi=phi, mixture_component=comp_id, mixture_names=mix_names,
                poll=pl, n=n, seed=seed)


def seats_for(model, draws, denominator=None, uplift_scope=None, **kw):
    P = model.P
    sc = draws['scenario']
    den = denominator or sc.threshold_denominator or P['threshold_denominator']
    scope = uplift_scope or sc.uplift_scope or P['minority_uplift_scope']
    return AL.allocate_batch(draws['votes'], draws['is_minority'], draws['denominators'][den], seats=P['seats_total'],
                             threshold_share=P['threshold_share'], minority_multiplier=P['minority_quotient_multiplier'],
                             uplift_scope=scope, fallback_if_none_reach=P['fallback_if_no_list_reaches_threshold'], **kw)


# ------------------------------------------------------------------------------------------------ summaries
def _q(x, levels):
    out = {}
    for lv in levels:
        out[f'lo{int(round(lv * 100))}'] = np.quantile(x, 0.5 - lv / 2, axis=0)
        out[f'hi{int(round(lv * 100))}'] = np.quantile(x, 0.5 + lv / 2, axis=0)
    return out


def summarize_lists(model, draws, seat_res):
    """One row per list: votes, share of valid votes, seats, P(passing threshold), P(at least one seat)."""
    levels = model.P.floats('interval_levels')
    keys = draws['keys']
    votes, valid = draws['votes_cont'], draws['valid']
    share = votes / valid[:, None]
    seats = seat_res['seats']
    df = pd.DataFrame({'list_key': keys, 'list_name': [model.names.get(k, k) for k in keys], 'is_minority': draws['is_minority'],
                       'votes_median': np.median(votes, axis=0), 'votes_mean': votes.mean(axis=0),
                       'share_median': np.median(share, axis=0), 'share_mean': share.mean(axis=0)})
    for k, v in _q(share, levels).items():
        df[f'share_{k}'] = v
    for k, v in _q(votes, levels).items():
        df[f'votes_{k}'] = v
    df['seats_median'] = np.median(seats, axis=0)
    df['seats_mean'] = seats.mean(axis=0)
    for k, v in _q(seats, levels).items():
        df[f'seats_{k}'] = v
    thr = seat_res['threshold_votes']
    df['p_votes_at_least_threshold'] = (votes >= thr[:, None]).mean(axis=0)
    df['p_takes_part_in_allocation'] = seat_res['eligible'].mean(axis=0)
    df['p_at_least_one_seat'] = (seats > 0).mean(axis=0)
    return df.sort_values('seats_mean', ascending=False).reset_index(drop=True)


def seat_majority_table(model, draws, seat_res):
    seats = seat_res['seats']
    maj = model.P['majority_seats']
    keys = draws['keys']
    top = seats.max(axis=1)
    out = [dict(event='largest list has an absolute majority of seats', probability=float((top >= maj).mean()))]
    for k in model.polled:
        i = keys.index(k)
        out.append(dict(event=f'{k}: most seats of any list (ties count)', probability=float((seats[:, i] == top).mean())))
        out.append(dict(event=f'{k}: absolute majority of seats alone', probability=float((seats[:, i] >= maj).mean())))
    return pd.DataFrame(out)


def threshold_sensitivity(model, draws):
    """Same draws, every combination of threshold base and uplift scope. Reports seats and P(takes part) for non-minority lists
    that can fall near the threshold, plus the total seats of minority lists."""
    keys = draws['keys']
    rows = []
    for den in ('voters_turned_out', 'ballots_cast', 'valid_ballots'):
        for scope in EL.UPLIFT_SCOPES:
            r = seats_for(model, draws, den, scope)
            for i, k in enumerate(keys):
                rows.append(dict(threshold_denominator=den, uplift_scope=scope, list_key=k, is_minority=bool(draws['is_minority'][i]),
                                 seats_mean=float(r['seats'][:, i].mean()), seats_p10=float(np.quantile(r['seats'][:, i], 0.1)),
                                 seats_p90=float(np.quantile(r['seats'][:, i], 0.9)),
                                 p_takes_part=float(r['eligible'][:, i].mean()), p_any_seat=float((r['seats'][:, i] > 0).mean())))
    return pd.DataFrame(rows)


def threshold_curve(model, draws, key, grid_share=None):
    """P(list takes part) and its mean seats as a function of its share of valid votes (binned over the draws): shows the cliff."""
    i = draws['keys'].index(key)
    r = seats_for(model, draws)
    share = draws['votes_cont'][:, i] / draws['valid']
    if grid_share is None:
        grid_share = np.linspace(np.quantile(share, 0.01), np.quantile(share, 0.99), 13)
    bins = np.digitize(share, grid_share[1:-1])
    rows = []
    for b in range(len(grid_share) - 1):
        m = bins == b
        if m.sum() >= 20:
            rows.append(dict(share_lo=grid_share[b], share_hi=grid_share[b + 1], n_draws=int(m.sum()),
                             p_takes_part=float(r['eligible'][m, i].mean()), seats_mean=float(r['seats'][m, i].mean()),
                             p_government_majority_any=np.nan))
    return pd.DataFrame(rows)


def coalition_results(model, draws, seat_res):
    P = model.P
    keys = draws['keys']
    per, flags, tot = CO.evaluate(seat_res['seats'], keys, draws['is_minority'], model.coalitions, majority=P['majority_seats'],
                                  incumbent_keys=P.list('incumbent_bloc_list_keys'), student_key=P['student_list_key'])
    return per, CO.formation_table(flags, model.coalitions), flags, tot


def kingmaker_table(model, draws, seat_res):
    """Pure seat arithmetic with ONE definition (the incumbent bloc of cfg_parameters): can either side reach the majority
    WITHOUT any minority list, and how many seats do minority lists hold when neither can?"""
    P = model.P
    keys = draws['keys']
    seats = seat_res['seats']
    maj = P['majority_seats']
    inc = np.isin(keys, P.list('incumbent_bloc_list_keys')) & ~draws['is_minority']
    mino = draws['is_minority']
    other = ~inc & ~mino
    s_inc, s_oth, s_min = seats[:, inc].sum(1), seats[:, other].sum(1), seats[:, mino].sum(1)
    rows = [
        ('incumbent bloc (cfg incumbent_bloc_list_keys) reaches the majority without minority lists', float((s_inc >= maj).mean())),
        ('all other non-minority lists together reach the majority without minority lists', float((s_oth >= maj).mean())),
        ('neither reaches the majority without minority lists (minority seats are pivotal)', float(((s_inc < maj) & (s_oth < maj)).mean())),
        ('minority lists hold at least as many seats as the margin needed by the larger side',
         float(((s_inc < maj) & (s_oth < maj) & (s_min >= maj - np.maximum(s_inc, s_oth))).mean())),
    ]
    out = pd.DataFrame(rows, columns=['event', 'probability'])
    dist = pd.DataFrame({'quantity': ['seats incumbent bloc', 'seats other non-minority lists', 'seats minority lists'],
                         'p10': [np.quantile(x, 0.1) for x in (s_inc, s_oth, s_min)],
                         'median': [np.median(x) for x in (s_inc, s_oth, s_min)],
                         'p90': [np.quantile(x, 0.9) for x in (s_inc, s_oth, s_min)]})
    return out, dist


# ------------------------------------------------------------------------------------------------ municipal layer
def simulate_units(model, draws, n_unit=None, alpha=0.0, mobilization=True, seed=None, turnout_method='logit_shift',
                   geography='proportional', dispersion_multiplier=1.0):
    """Downscale the first n_unit national draws to the 192 leaf units.

    alpha        share of each observed municipality's local-election deviation (SNS-led lead list, proxy outcome) carried into its
                 parliamentary geography. NOT identified: reported as a grid. alpha = 0 ignores local elections entirely.
    mobilization an unidentified common shock (mean 0, SD cfg local_mobilization_effect_sd) to the student-list weight in
                 municipalities with a recent local election in the data.
    geography    'proportional' (IPF; the pipeline default) or 'additive' (uniform swing); the 2022 -> 2023 backtest favours neither
                 for every family (see backtest.py), so both are reported.
    dispersion_multiplier  extra multiplier on unit and region dispersion (a longer interval than 2022 -> 2023 argues for > 1).
    Unit totals reproduce the draw's valid votes; list totals reproduce the draw's list votes (checked in `checks`)."""
    P, pn = model.P, model.panel
    n = min(n_unit or P['n_unit_draws'], draws['n'])
    seed = draws['seed'] if seed is None else seed
    r_turn, r_noise, r_reg, r_mob = _children(seed + 101, 4)
    fixed = pn.fixed_rate.astype(bool).values
    V = draws['V'][:n]
    rates = TU.simulate_calibrated(pn.registered_target.values, pn.turnout_rate_baseline.values, V, model.turnout_sd, fixed=fixed,
                                   method=turnout_method, rng=r_turn)
    voters = pn.registered_target.values[None, :] * rates
    ballots, inv, valid = TU.ballots_and_valid(voters, pn.ballots_per_turned_out_baseline.values[None, :],
                                               pn.invalid_rate_baseline.values[None, :], P['invalid_rate_multiplier_baseline'])
    valid = valid * (draws['valid'][:n] / valid.sum(axis=1))[:, None]       # tie unit totals to the national draw (factor ~ 1)
    nm = len(model.nonmin_keys)
    Mv = draws['votes_cont'][:n, nm:]
    mu = Mv[:, :, None] * model.min_struct['patterns'][None, :, :]           # (n, Lmin, U)
    pat = model.min_struct['patterns']
    cap = 0.98 * valid                                                       # a unit cannot give minority lists more than its valid votes
    unplaced = np.zeros(mu.shape[:2])
    for _ in range(12):                                                      # water-filling: move clipped votes to units with headroom
        tot_m = mu.sum(axis=1)
        over = tot_m > cap
        if not over.any() and not unplaced.any():
            break
        new_mu = mu * np.where(over, cap / np.maximum(tot_m, 1e-12), 1.0)[:, None, :]
        lost = (mu - new_mu).sum(axis=2) + unplaced
        mu = new_mu
        room = (mu.sum(axis=1) < cap - 1e-9)[:, None, :] * pat[None, :, :]
        add = room / np.maximum(room.sum(axis=2, keepdims=True), 1e-300) * lost[:, :, None]
        mu = mu + add
        unplaced = np.where(room.sum(axis=2) > 0, 0.0, lost)
        if lost.max() < 1e-6:
            break
    clipped = float(unplaced.sum() / max(mu.sum(), 1.0))
    R = valid - mu.sum(axis=1)
    T = draws['votes_cont'][:n, :nm]
    T = T * (R.sum(axis=1) / T.sum(axis=1))[:, None]                         # exact when nothing was clipped
    K = nm
    logW = np.log(model.W0)[None, :, :] + dispersion_multiplier * model.sigma_unit[None, None, :] * r_noise.standard_normal((n, len(pn), K))
    reps = r_reg.standard_normal((n, len(model.region_codes), K)) * dispersion_multiplier * model.sigma_region[None, None, :]
    logW = logW + reps[:, model.region_index, :]
    ref_ix = model.nonmin_keys.index(model.ref)
    logW[:, :, ref_ix] += alpha * model.local_log_dev[None, :]
    stu_ix = model.nonmin_keys.index(P['student_list_key'])
    if mobilization and model.recent_local_mask.any():
        m = r_mob.normal(0.0, P['local_mobilization_effect_sd'], size=n)
        logW[:, model.recent_local_mask, stu_ix] += m[:, None]
    fit = {'proportional': VS.rake, 'additive': VS.additive_fit}[geography]
    nmv = fit(np.exp(logW), R, T)                                            # (n, U, K)
    votes = np.concatenate([nmv, np.transpose(mu, (0, 2, 1))], axis=2)       # (n, U, L)
    checks = dict(max_abs_unit_sum_error=float(np.abs(votes.sum(axis=2) - valid).max()),
                  max_rel_list_total_error=float(np.max(np.abs(votes.sum(axis=1) - draws['votes_cont'][:n]) /
                                                        np.maximum(draws['votes_cont'][:n], 1.0))),
                  minority_clipped_fraction=clipped, n=n, alpha=alpha, geography=geography, dispersion_multiplier=dispersion_multiplier)
    return dict(votes=votes, valid=valid, voters=voters, rates=rates, checks=checks, keys=draws['keys'], n=n, alpha=alpha)


def summarize_units(model, units, levels=None):
    """Per unit and list: expected share of valid votes with intervals, probability of finishing first; per unit turnout."""
    levels = levels or model.P.floats('interval_levels')
    pn = model.panel
    votes, valid = units['votes'], units['valid']
    share = votes / valid[:, :, None]
    keys = units['keys']
    first = share.argmax(axis=2)
    rows = []
    qs = {}
    for lv in levels:
        qs[lv] = (np.quantile(share, 0.5 - lv / 2, axis=0), np.quantile(share, 0.5 + lv / 2, axis=0))
    mean = share.mean(axis=0)
    med = np.median(share, axis=0)
    pfirst = np.stack([(first == j).mean(axis=0) for j in range(len(keys))], axis=1)
    out = []
    for j, k in enumerate(keys):
        d = pd.DataFrame({'geo_id': pn.geo_id.values, 'geo_name': pn.geo_name.values, 'region_id': pn.region_id.values,
                          'list_key': k, 'share_mean': mean[:, j], 'share_median': med[:, j], 'votes_mean': votes[:, :, j].mean(axis=0),
                          'p_first': pfirst[:, j], 'valid_votes_mean': valid.mean(axis=0),
                          'low_count_flag': valid.mean(axis=0) < model.P['small_unit_valid_votes_flag']})
        for lv, (a, b) in qs.items():
            d[f'share_lo{int(round(lv * 100))}'] = a[:, j]
            d[f'share_hi{int(round(lv * 100))}'] = b[:, j]
        out.append(d)
    long = pd.concat(out, ignore_index=True)
    lv = max(levels)
    turn = pd.DataFrame({'geo_id': pn.geo_id.values, 'geo_name': pn.geo_name.values, 'region_id': pn.region_id.values,
                         'local_status': model.status.set_index('geo_id').reindex(pn.geo_id).local_status.values,
                         'registered_2026': pn.registered_target.values,
                         'turnout_baseline': pn.turnout_rate_baseline.values,
                         'turnout_mean': units['rates'].mean(axis=0),
                         f'turnout_lo{int(round(lv * 100))}': np.quantile(units['rates'], 0.5 - lv / 2, axis=0),
                         f'turnout_hi{int(round(lv * 100))}': np.quantile(units['rates'], 0.5 + lv / 2, axis=0),
                         'voters_mean': units['voters'].mean(axis=0), 'valid_votes_mean': valid.mean(axis=0),
                         'low_count_flag': valid.mean(axis=0) < model.P['small_unit_valid_votes_flag']})
    return long, turn
