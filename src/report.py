"""Stages 9-13: scenario runs, sensitivity, diagnostics and the exported outputs (A-F).

Every number written here comes out of the draws produced by simulate.py. Files are plain CSV. Nothing is overwritten silently:
the output directory is created if missing and files are rewritten on each run (reproducible given the seed in cfg_parameters).
"""
import json
import pathlib
import platform
import sys

import numpy as np
import pandas as pd

import backtest as BT
import coalitions as CO
import simulate as SM
import turnout as TU
import local_swing as LS


# ------------------------------------------------------------------------------------------------ scenarios
def scenario_set(model):
    """Baseline plus every sensitivity defined in cfg_* (nothing is typed here)."""
    P = model.P
    out = [SM.Scenario(name='baseline', description='Polls + event mixture (if events after the last poll) + user turnout range')]
    out.append(SM.Scenario(name='polls_only', use_event_mixture=False, description='No realignment mixture: polls taken as they are'))
    for sid, comp in model.mixture.items():
        out.append(SM.Scenario(name=f'event_{sid}', use_event_mixture=False, transfers=[dict(t) for t in comp['transfers']],
                               description=f'Mixture replaced by one component: {sid}'))
    out += model.sensitivity_scenarios()
    for de in P.floats('poll_sensitivity_design_effects'):
        out.append(SM.Scenario(name=f'poll_design_effect_{de:g}', poll_overrides={'design_effect': de}, description=f'Poll design effect {de:g}'))
    for sd in P.floats('poll_sensitivity_election_error_sd'):
        out.append(SM.Scenario(name=f'poll_election_error_{sd:g}', poll_overrides={'election_error_sd': sd}, description=f'Election-day polling miss SD {sd:g}'))
    for h in model.poll['houses']:
        out.append(SM.Scenario(name=f'poll_leave_out::{h}', poll_overrides={'leave_out': h}, description=f'Poll aggregation without pollster {h}'))
    lo, hi = P['turnout_voters_low'], P['turnout_voters_high']
    for off in P.floats('turnout_sensitivity_offsets'):
        out.append(SM.Scenario(name=f'turnout_{off:+.0f}', turnout_range=(lo + off, hi + off), description=f'Participating voters {lo + off:,.0f}-{hi + off:,.0f}'))
    out.append(SM.Scenario(name='turnout_low_end', turnout_range=(lo, lo), description=f'Participating voters fixed at the low end of the range ({lo:,.0f})'))
    out.append(SM.Scenario(name='turnout_high_end', turnout_range=(hi, hi), description=f'Participating voters fixed at the high end of the range ({hi:,.0f})'))
    for v in P.floats('minority_sensitivity_phi_values'):
        out.append(SM.Scenario(name=f'minority_phi_{v:g}', param_overrides={'minority_turnout_responsiveness_low': v, 'minority_turnout_responsiveness_high': v},
                               description=f'Minority group votes respond to turnout with elasticity {v:g}'))
    for v in P.floats('minority_sensitivity_capture_means'):
        out.append(SM.Scenario(name=f'minority_new_entrant_capture_{v:g}', param_overrides={'minority_new_entrant_capture_mean': v},
                               description=f'New-entrant minority lists capture {v:g} of their group pool on average'))
    for k in P.list('minority_status_sensitivity_keys'):
        out.append(SM.Scenario(name=f'not_minority::{k}', minority_status_override={k: False}, description=f'{k} treated as a non-minority list'))
    return out


def scenario_row(model, draws):
    sc = draws['scenario']
    seat_res = SM.seats_for(model, draws)
    keys = draws['keys']
    seats = seat_res['seats']
    per, form, flags, tot = SM.coalition_results(model, draws, seat_res)
    share = draws['votes_cont'] / draws['valid'][:, None]
    top = seats.max(axis=1)
    row = dict(scenario=sc.name, description=sc.description, n_draws=draws['n'])
    for k in model.polled:
        i = keys.index(k)
        row[f'share_median__{k}'] = float(np.median(share[:, i]))
        row[f'seats_median__{k}'] = float(np.median(seats[:, i]))
        row[f'p_most_seats__{k}'] = float((seats[:, i] == top).mean())
        row[f'p_takes_part__{k}'] = float(seat_res['eligible'][:, i].mean())
    ref, stu = model.ref, model.P['student_list_key']
    row['p_majority_alone__' + ref] = float((seats[:, keys.index(ref)] >= model.P['majority_seats']).mean())
    row['p_majority_alone__' + stu] = float((seats[:, keys.index(stu)] >= model.P['majority_seats']).mean())
    f = form.set_index('event').probability
    for lab, col in (('incumbent-anchored coalition has a majority', 'p_incumbent_anchored_majority'),
                     ('student-anchored coalition has a majority', 'p_student_anchored_majority'),
                     ('only an incumbent-anchored coalition has a majority', 'p_only_incumbent_anchored'),
                     ('only a student-anchored coalition has a majority', 'p_only_student_anchored'),
                     ('both kinds have a majority (order of invitation not modelled)', 'p_both_kinds')):
        row[col] = float(f[lab])
    held = draws['poll'].get('held_at_full_sample', [])
    row['note'] = ('polled only by the omitted pollster, held at the full-sample posterior: ' + ', '.join(held)) if held else ''
    return row


def run_scenarios(model, n=None, scenarios=None, verbose=True):
    n = n or model.P['n_simulations']
    rows, keep = [], {}
    for sc in scenarios or scenario_set(model):
        d = SM.draw_national(model, n, sc)
        rows.append(scenario_row(model, d))
        if sc.name == 'baseline':
            keep['baseline'] = d
        if verbose:
            print(f'    scenario {sc.name}')
    return pd.DataFrame(rows), keep


def threshold_sweeps(model):
    """For each focus list: shift its poll strength over a grid and record how its threshold crossing, seats and the coalition
    arithmetic react. This shows the cliff at the threshold; it is NOT a probability statement about the shift."""
    P = model.P
    n = P['n_sweep_simulations']
    rows = []
    for k in P.list('threshold_focus_list_keys'):
        for dlt in P.floats('threshold_sweep_shift_log'):
            sc = SM.Scenario(name=f'sweep::{k}::{dlt:+.2f}', shift_log={k: dlt}, use_event_mixture=False)
            d = SM.draw_national(model, n, sc)
            r = SM.seats_for(model, d)
            i = d['keys'].index(k)
            per, form, flags, tot = SM.coalition_results(model, d, r)
            f = form.set_index('event').probability
            rows.append(dict(list_key=k, shift_log=dlt, share_median=float(np.median(d['votes_cont'][:, i] / d['valid'])),
                             p_takes_part=float(r['eligible'][:, i].mean()), seats_median=float(np.median(r['seats'][:, i])),
                             p_incumbent_anchored_majority=float(f['incumbent-anchored coalition has a majority']),
                             p_student_anchored_majority=float(f['student-anchored coalition has a majority'])))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ diagnostics
def diag_polls(model):
    pl = model.poll
    s = pl['summary'].copy()
    margin_ix = 0       # first target coordinate
    s['reference'] = model.ref
    s['posterior_log_ratio_first_target_at_election'] = float(pl['mean'][margin_ix])
    s['posterior_sd'] = float(np.sqrt(pl['cov'][margin_ix, margin_ix]))
    s['pollster_effect_sd_used'] = pl['tau_h']
    s['pollster_effect_sd_moment_estimate'] = pl['tau_h_moment_estimate']
    s['days_from_last_poll_to_election'] = pl['days_to_election']
    return s


def diag_poll_vs_structural(model, draws):
    """Poll posterior against the observed 2023 baseline and the descriptive local-election signal (cross-check, not an input)."""
    P = model.P
    keys = draws['keys']
    share = draws['votes_cont'] / draws['valid'][:, None]
    nat = model.nat_family
    cur = nat[nat.election_id == model.curr_id].set_index('family').share_valid
    rows = []
    for k in model.polled:
        i = keys.index(k)
        origin = model.origin_weights[model.origin_weights.list_key == k].sort_values('weight', ascending=False)
        fam = origin.origin.iloc[0] if len(origin) else ''
        rows.append(dict(list_key=k, main_2023_origin_family=fam, share_2023_origin_family=float(cur.get(fam, np.nan)),
                         poll_posterior_share_median=float(np.median(share[:, i])),
                         poll_posterior_share_p10=float(np.quantile(share[:, i], 0.1)), poll_posterior_share_p90=float(np.quantile(share[:, i], 0.9))))
    out = pd.DataFrame(rows)
    ls = model.local_summary
    ref_row = out.list_key == model.ref
    if ls is not None:
        out['local_signal_mean_change_pp'] = np.where(ref_row, ls['mean'], np.nan)
        out['local_signal_n_municipalities'] = np.where(ref_row, ls['n'], np.nan)
        out['indicative_share_if_local_swing_carried_nationally_alpha1'] = np.where(ref_row, out.share_2023_origin_family + ls['mean'] / 100.0, np.nan)
    out['note'] = np.where(ref_row, 'Descriptive only: 10-13 municipalities, different contest and lists, non-random sample; composition of the local lead list differs from the parliamentary list.', '')
    return out


def diag_implied_flows(model, draws):
    """Plausibility accounting. NOT a transition matrix: transitions are not identified without poll cross-tabs (ext_poll_transitions)."""
    keys = draws['keys']
    med = np.median(draws['votes_cont'], axis=0)
    nat = model.nat_family
    cur = nat[nat.election_id == model.curr_id].set_index('family')
    v23 = cur.votes
    pn = model.panel
    voters23 = float(pn.turned_out_baseline.sum())
    rows = []
    for k in model.nonmin_keys:
        ow = model.origin_weights[(model.origin_weights.list_key == k) & model.origin_weights.origin.isin(v23.index)]
        pool = float(sum(v23[o] for o in ow.origin))
        main = ow.sort_values('weight', ascending=False).origin.iloc[0] if len(ow) else ''
        rows.append(dict(list_key=k, votes_2026_median=med[keys.index(k)], main_2023_origin_family=main,
                         votes_2023_main_origin=float(v23.get(main, np.nan)) if main else np.nan,
                         votes_2023_all_origin_families_followed=pool if len(ow) else np.nan,
                         net_change_vs_main_origin=med[keys.index(k)] - float(v23.get(main, np.nan)) if main else np.nan,
                         votes_2026_over_pool=med[keys.index(k)] / pool if pool > 0 else np.nan))
    out = pd.DataFrame(rows)
    inc = model.P.list('incumbent_bloc_list_keys')
    extra = dict(participating_voters_2023=voters23, participating_voters_2026_median=float(np.median(draws['V'])),
                 additional_participants=float(np.median(draws['V']) - voters23),
                 valid_votes_2023=float(pn.valid_baseline.sum()), valid_votes_2026_median=float(np.median(draws['valid'])))
    for side, ks in (('incumbent_bloc', [k for k in model.nonmin_keys if k in inc]),
                     ('other_non_minority_lists', [k for k in model.nonmin_keys if k not in inc])):
        fams = set(model.origin_weights[model.origin_weights.list_key.isin(ks) & model.origin_weights.origin.isin(v23.index)].origin)
        pool = float(sum(v23[f] for f in fams))
        votes = float(sum(med[keys.index(k)] for k in ks))
        extra[f'{side}__votes_2026_median_sum'] = votes
        extra[f'{side}__votes_2023_of_origin_families_followed (union)'] = pool
        extra[f'{side}__net_change_vs_union_pool'] = votes - pool
        if side == 'other_non_minority_lists':
            extra[f'{side}__net_change_as_multiple_of_additional_participants'] = (votes - pool) / max(extra['additional_participants'], 1.0)
    extra['reading'] = ('Accounting identity only. A multiple above 1 means the lists cannot be fed by 2023 voters of their origin families plus '
                        'all additional participants; some 2023 voters of other families would have to switch. Transitions are not identified without '
                        'poll cross-tabs (ext_poll_transitions).')
    return out, pd.DataFrame([extra]).T.reset_index().rename(columns={'index': 'quantity', 0: 'value'})


def diag_market_validation(model, draws, seat_res):
    """Prediction-market quotes next to model quantities. VALIDATION ONLY: the quoted market is about the prime minister, the model
    quantity is about seats; no mapping is asserted and nothing here feeds back into the forecast."""
    mk = model.markets
    if len(mk) == 0:
        return pd.DataFrame(), pd.DataFrame()
    g = mk.sort_values('observed_at').groupby(['platform', 'market_question', 'outcome_label']).agg(
        n_quotes=('price', 'size'), price_min=('price', 'min'), price_max=('price', 'max'), price_last=('price', 'last'),
        first_quote=('observed_at', 'min'), last_quote=('observed_at', 'max')).reset_index()
    g['range_width'] = g.price_max - g.price_min
    g['note'] = 'Intraday range shown because quotes in the source differ widely; thin market. Not used as an input.'
    model_rows = SM.seat_majority_table(model, draws, seat_res)
    return g, model_rows


def diag_turnout_methods(model):
    pn, P = model.panel, model.P
    mid = 0.5 * (P['turnout_voters_low'] + P['turnout_voters_high'])
    out = pn[['geo_id', 'geo_name', 'region_id', 'registered_target', 'turnout_rate_baseline']].copy()
    for m in TU.METHODS:
        out[f'rate__{m}'] = TU.calibrate(pn.registered_target.values, pn.turnout_rate_baseline.values, mid, fixed=pn.fixed_rate.astype(bool).values, method=m)
    base = out['rate__logit_shift']
    out['max_abs_difference_between_methods_pp'] = 100 * (out[[f'rate__{m}' for m in TU.METHODS]].max(axis=1) - out[[f'rate__{m}' for m in TU.METHODS]].min(axis=1))
    summ = out.groupby('region_id', dropna=False).apply(lambda d: pd.Series({
        'registered_2026': d.registered_target.sum(), 'baseline_turnout': np.average(d.turnout_rate_baseline, weights=d.registered_target),
        **{f'turnout__{m}': np.average(d[f'rate__{m}'], weights=d.registered_target) for m in TU.METHODS}}), include_groups=False).reset_index()
    return out, summ


def diag_local(model):
    ls, la = model.local_summary, model.local_assoc
    rows = []
    if ls:
        rows.append(dict(quantity='n municipalities used', value=ls['n']))
        rows.append(dict(quantity='mean change (pp)', value=ls['mean']))
        rows.append(dict(quantity='between-municipality SD (pp)', value=ls['sd_between']))
        for lv in (80, 95):
            lo, hi = ls[f'mean_ci_{lv}']
            rows.append(dict(quantity=f'{lv}% interval for the mean (pp)', value=f'{lo:.2f} to {hi:.2f}'))
            lo, hi = ls[f'predictive_{lv}']
            rows.append(dict(quantity=f'{lv}% predictive interval for a NEW municipality (pp)', value=f'{lo:.2f} to {hi:.2f}'))
    if la:
        rows.append(dict(quantity='slope of change on turnout change (pp per pp)', value=la['slope']))
        rows.append(dict(quantity='slope 95% CI', value=f"{la['slope_ci95'][0]:.2f} to {la['slope_ci95'][1]:.2f}"))
        rows.append(dict(quantity='leave-one-out slope range', value=f"{la['loo_slope_min']:.2f} to {la['loo_slope_max']:.2f}"))
        rows.append(dict(quantity='Spearman rho', value=la['spearman_rho']))
    rows.append(dict(quantity='difference-in-differences / event study', value='not identified: no municipality without a local election is observed after the baseline in the same outcome'))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ orchestration
def run_all(model, outdir, n=None, n_unit=None, make_charts=True, verbose=True):
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    P = model.P
    n = n or P['n_simulations']
    n_unit = n_unit or P['n_unit_draws']
    files = {}

    def save(df, name, desc, stage):
        df.to_csv(out / name, index=False)
        files[name] = (stage, desc)

    log = (lambda *a: print(*a)) if verbose else (lambda *a: None)
    log('  national draws and seats')
    base = SM.draw_national(model, n)
    seat_res = SM.seats_for(model, base)
    tab = SM.summarize_lists(model, base, seat_res)
    tab = tab.merge(most_votes_probability(model, base).rename_axis('list_key').reset_index(), on='list_key', how='left')
    save(tab, 'A_national_votes_shares_seats.csv', 'A/B. National votes, share of valid votes and seats per list: median, mean, intervals, P(takes part), P(any seat)', 'Stages 5-9')
    maj = SM.seat_majority_table(model, base, seat_res)
    save(maj, 'B_seat_majority_probabilities.csv', 'B. Probability of most seats / absolute majority by list', 'Stage 9')
    dist = pd.DataFrame({'seats': np.arange(0, P['seats_total'] + 1)})
    for k in model.polled:
        dist[k] = np.bincount(seat_res['seats'][:, base['keys'].index(k)], minlength=P['seats_total'] + 1) / n
    save(dist, 'B_seat_distribution_polled_lists.csv', 'B. Full distribution of seats for the polled lists', 'Stage 9')
    thr = SM.threshold_sensitivity(model, base)
    save(thr, 'B_threshold_sensitivity.csv', 'B. Seats and P(takes part) for every threshold base x uplift scope, same draws', 'Stage 9')
    save(pd.DataFrame({'quantity': ['threshold votes (draw median, base: ' + P['threshold_denominator'] + ')'], 'value': [float(np.median(seat_res['threshold_votes']))]}),
         'B_threshold_votes.csv', 'B. Votes needed for 3 percent under the configured base', 'Stage 9')
    per, form, flags, tot = SM.coalition_results(model, base, seat_res)
    save(per, 'C_coalitions.csv', 'C. Majority probability of each named coalition (cfg_coalitions); compatibility is an analyst assumption', 'Stage 10')
    save(form, 'C_government_formation_conditional.csv', 'C. Conditional government-formation probabilities by assumption set', 'Stage 10')
    kt, kd = SM.kingmaker_table(model, base, seat_res)
    save(kt, 'C_minority_pivotality.csv', 'C. Can either side reach the majority without minority lists?', 'Stage 10')
    save(kd, 'C_bloc_seat_quantiles.csv', 'C. Seat quantiles of the incumbent bloc, other non-minority lists and minority lists', 'Stage 10')

    log('  scenarios')
    scen, _ = run_scenarios(model, n, verbose=False)
    save(scen, 'E_scenario_comparison.csv', 'E. Baseline and sensitivity scenarios: shares, seats, threshold, coalition arithmetic', 'Stage 11')
    log('  threshold sweeps')
    sweeps = threshold_sweeps(model)
    save(sweeps, 'E_threshold_sweeps.csv', 'E. Shift in poll strength of near-threshold lists vs threshold crossing, seats and coalition majorities', 'Stage 9/11')

    log('  municipal layer')
    muni_rows, units_base = [], None
    alphas = P.floats('local_transfer_alpha_values')
    for a in alphas:
        u = SM.simulate_units(model, base, n_unit=n_unit, alpha=a)
        long, turn = SM.summarize_units(model, u)
        long['alpha'] = a
        muni_rows.append(long)
        if a == alphas[0]:
            units_base = (u, long.copy(), turn)
    long0, turn0 = units_base[1], units_base[2]
    save(long0.drop(columns='alpha'), 'D_municipal_list_shares_alpha0.csv', f'D. Unit x list expected share of valid votes with intervals and P(first); local-election carry-over alpha={alphas[0]:g}', 'Stage 8')
    save(turn0, 'D_municipal_turnout.csv', 'D. Unit turnout: 2023 baseline vs 2026 scenario mean and interval', 'Stage 3')
    grid = pd.concat(muni_rows)
    key_lists = [model.ref, P['student_list_key']]
    piv = grid[grid.list_key.isin(key_lists) & grid.geo_id.isin(model.local_use.geo_id)].pivot_table(
        index=['geo_id', 'geo_name'], columns=['list_key', 'alpha'], values='share_mean')
    piv.columns = [f'share_mean__{a}__alpha{b:g}' for a, b in piv.columns]
    save(piv.reset_index(), 'D_municipal_alpha_grid_local_units.csv', 'D. Expected shares in municipalities with a recent local election under the alpha grid (alpha is NOT identified)', 'Stage 4/8')
    comp = []
    for geo, mult in (('proportional', 1.0), ('additive', 1.0), ('proportional', min(P.floats('dispersion_sensitivity_multipliers'))),
                      ('proportional', max(P.floats('dispersion_sensitivity_multipliers')))):
        u = SM.simulate_units(model, base, n_unit=n_unit, alpha=0.0, geography=geo, dispersion_multiplier=mult)
        l2, _ = SM.summarize_units(model, u)
        l2 = l2[l2.list_key.isin(key_lists)].assign(geography=geo, dispersion_multiplier=mult)
        comp.append(l2)
    cg = pd.concat(comp)
    cmp_tab = cg.assign(width=cg.share_hi80 - cg.share_lo80).groupby(['geography', 'dispersion_multiplier', 'list_key']).agg(
        units_expected_first=('p_first', 'sum'), mean_lo80_hi80_width=('width', 'mean')).reset_index()
    save(cmp_tab, 'E_municipal_geography_sensitivity.csv', 'E. Number of municipalities expected to be won, and interval width, by geography method and dispersion multiplier', 'Stage 8/11')

    contrib = unit_contributions(model, units_base[0], base)
    save(contrib, 'D_unit_contributions_to_national_change.csv',
         'D. Each unit: expected votes vs 2023 origin-family votes and its share of the national net change and of the national variance', 'Stage 8')
    save(conditional_outcomes(model, base, seat_res), 'E_conditional_on_threshold.csv',
         'E. Outcomes conditional on each near-threshold list taking part or missing the threshold', 'Stage 9/11')
    tl = poll_timeline(model)
    save(tl, 'E_forecast_timeline_polls.csv', 'E. Poll-based aggregate as it would have looked at each publication date', 'Stage 5/13')

    log('  diagnostics')
    save(diag_polls(model), 'F_diag_polls.csv', 'F. Poll panel summary and aggregate', 'Stage 5')
    save(diag_poll_vs_structural(model, base), 'F_diag_poll_vs_structural.csv', 'F. Poll posterior vs 2023 baseline vs local-election signal (cross-check)', 'Stage 5/11')
    flows, flow_extra = diag_implied_flows(model, base)
    save(flows, 'F_diag_implied_flows.csv', 'F. Implied votes vs 2023 origin pools (accounting, not transitions)', 'Stage 6')
    save(flow_extra, 'F_diag_implied_flows_totals.csv', 'F. Participation and student-pool arithmetic', 'Stage 6')
    mk, mk_model = diag_market_validation(model, base, seat_res)
    if len(mk):
        save(mk, 'F_diag_market_quotes.csv', 'F. Prediction-market quotes (validation only)', 'Stage 5')
        save(mk_model, 'F_diag_market_model_side.csv', 'F. Model-side quantities to compare with the quotes by eye (definitions differ)', 'Stage 5')
    save(model.uncaptured_events if len(model.uncaptured_events) else pd.DataFrame({'note': ['no events after the last poll']}),
         'F_diag_events_after_last_poll.csv', 'F. Events that trigger the realignment mixture (dated after the last poll)', 'Stage 5')
    tr, trs = diag_turnout_methods(model)
    save(tr, 'F_diag_turnout_methods_by_unit.csv', 'F. Unit turnout under three allocation methods at the middle of the range', 'Stage 3')
    save(trs, 'F_diag_turnout_methods_by_region.csv', 'F. Regional turnout under three allocation methods', 'Stage 3')
    save(diag_local(model), 'F_diag_local_elections.csv', 'F. What recent local elections can and cannot tell (descriptive)', 'Stage 4')
    save(model.swing.reset_index().rename(columns={'index': 'family'}), 'F_diag_swing_dispersion_2022_2023.csv', 'F. Unit and region dispersion of the 2022->2023 swing by family', 'Stage 6')
    bt = BT.run(model.ufv, model.panel, model.prev_id, model.curr_id)
    save(bt['b1'], 'F_backtest_geography_methods.csv', 'F. Backtest B1: downscaling methods 2022->2023', 'Stage 12')
    save(bt['b2'], 'F_backtest_new_list_geography.csv', 'F. Backtest B2: geography assumptions for new lists', 'Stage 12')
    save(bt['b3'], 'F_backtest_leave_region_out_dispersion.csv', 'F. Backtest B3: leave-one-region-out dispersion calibration', 'Stage 12')

    meta = dict(random_seed=P['random_seed'], n_simulations=n, n_unit_draws=n_unit, election_target_date=str(P['election_target_date']),
                turnout_range=[P['turnout_voters_low'], P['turnout_voters_high']], threshold_denominator=P['threshold_denominator'],
                minority_uplift_scope=P['minority_uplift_scope'], last_poll_date=str(model.last_poll_date.date()),
                mixture_active=bool(model.mixture_active), n_events_after_last_poll=int(len(model.uncaptured_events)),
                poll_houses=model.poll['houses'], python=sys.version.split()[0], platform=platform.platform(),
                numpy=np.__version__, pandas=pd.__version__)
    (out / 'run_metadata.json').write_text(json.dumps(meta, indent=2, default=str))
    files['run_metadata.json'] = ('all', 'Seed, sizes and software versions of this run')
    if make_charts:
        import charts
        charts.make_all(model, base, seat_res, tab, per, scen, thr, sweeps, units_base, bt, out, files, timeline=tl, contrib=contrib, form=form)
    pd.DataFrame([(k, v[0], v[1]) for k, v in files.items()], columns=['file', 'stage', 'description']).to_csv(out / 'OUTPUT_MANIFEST.csv', index=False)
    return dict(tab=tab, seat_res=seat_res, draws=base, coalitions=per, formation=form, scenarios=scen, units=units_base, files=files, backtest=bt)


# ------------------------------------------------------------------------------------------------ additional outputs
def most_votes_probability(model, draws):
    top = draws['votes'].max(axis=1)
    return pd.Series((draws['votes'] == top[:, None]).mean(axis=0), index=draws['keys'], name='p_most_votes')


def conditional_outcomes(model, draws, seat_res):
    """Outcomes conditional on whether each near-threshold list takes part in the allocation (same draws, split)."""
    P = model.P
    keys = draws['keys']
    seats = seat_res['seats']
    per, form, flags, tot = SM.coalition_results(model, draws, seat_res)
    inc = flags[[c for c in model.coalitions[model.coalitions.plausibility_assumption_set == 'incumbent_anchored'].coalition_id]].any(axis=1)
    stu = flags[[c for c in model.coalitions[model.coalitions.plausibility_assumption_set == 'student_anchored'].coalition_id]].any(axis=1)
    top = seats.max(axis=1)
    ref, st = model.ref, P['student_list_key']
    rows = []
    for k in P.list('threshold_focus_list_keys'):
        i = keys.index(k)
        for label, m in (('takes part (>= threshold)', seat_res['eligible'][:, i]), ('below threshold (no seats)', ~seat_res['eligible'][:, i])):
            m = np.asarray(m)
            if m.sum() < 30:
                rows.append(dict(list_key=k, condition=label, share_of_draws=float(m.mean()), note='too few draws for conditional statistics'))
                continue
            rows.append(dict(list_key=k, condition=label, share_of_draws=float(m.mean()), n_draws=int(m.sum()),
                             p_incumbent_anchored_majority=float(inc[m].mean()), p_student_anchored_majority=float(stu[m].mean()),
                             p_most_seats_ref=float((seats[m, keys.index(ref)] == top[m]).mean()),
                             p_most_seats_student=float((seats[m, keys.index(st)] == top[m]).mean()),
                             seats_ref_median=float(np.median(seats[m, keys.index(ref)])), seats_student_median=float(np.median(seats[m, keys.index(st)]))))
    return pd.DataFrame(rows)


def unit_contributions(model, units, draws):
    """Where do the national changes come from? For the polled lists: each unit's expected votes against the 2023 votes of the
    list's main origin family, and its share of the national draw-to-draw variance (covariance of unit votes with the national total)."""
    pn = model.panel
    keys = units['keys']
    n = units['n']
    nat = draws['votes_cont'][:n]
    ufv = model.ufv[model.ufv.election_id == model.curr_id].pivot_table(index='geo_id', columns='family', values='votes', aggfunc='sum').reindex(pn.geo_id).fillna(0.0)
    rows = []
    for k in model.polled:
        j = keys.index(k)
        v = units['votes'][:, :, j]
        ow = model.origin_weights[model.origin_weights.list_key == k].sort_values('weight', ascending=False)
        fam = next((o for o in ow.origin if o in ufv.columns), None)
        base = ufv[fam].values if fam else np.full(len(pn), np.nan)
        cov = ((v - v.mean(axis=0)) * (nat[:, [j]] - nat[:, [j]].mean(axis=0))).mean(axis=0)
        var = nat[:, j].var()
        exp_v = v.mean(axis=0)
        net = exp_v - base
        d = pd.DataFrame({'geo_id': pn.geo_id.values, 'geo_name': pn.geo_name.values, 'region_id': pn.region_id.values, 'list_key': k,
                          'main_2023_origin_family': fam, 'votes_2023_origin_family': base, 'votes_2026_expected': exp_v, 'net_change': net,
                          'share_of_national_net_change': net / np.nansum(net) if np.nansum(net) != 0 else np.nan,
                          'share_of_national_variance': cov / var if var > 0 else np.nan})
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def poll_timeline(model, n_draws=4000, seed=7):
    """How the poll-based forecast would have moved as polls became known (publication date if given, else fieldwork end).
    Uses only polls available at each date; events and the closure are not re-applied (poll aggregate only).
    Reported on the log-ratio scale against the reference list, which does not depend on which other lists a poll covers; a
    list that no available poll covers yet is left blank rather than filled from the prior."""
    import polls as PO
    P = model.P
    pp = model.polls_panel.copy()
    pp['available'] = pp.publication_date.fillna(pp.poll_date)
    dates = sorted(pp.available.unique())[:int(P['poll_timeline_max_points'])]
    rng = np.random.default_rng(seed)
    stu = P['student_list_key']
    rows = []
    for d in dates:
        sub = pp[pp.available <= d]
        obs, _ = PO.prepare_log_ratios(sub, model.ref, model.targets, default_sample=P['poll_default_sample'], design_effect=P['poll_design_effect'])
        if not obs:
            continue
        seen = sorted({i for o in obs for i in o['idx']})
        agg = PO.aggregate(sub, model.ref, model.targets, model.election_date, tau_h_floor=P['poll_house_sd_floor'],
                           sigma_rw_per_day=P['poll_rw_sd_per_day'], sigma_election=P['poll_election_error_sd'],
                           design_effect=P['poll_design_effect'], default_sample=P['poll_default_sample'], prior_sd=P['poll_prior_sd'])
        z = rng.multivariate_normal(agg['mean'], agg['cov'], size=n_draws)
        row = dict(available_date=pd.Timestamp(d), n_polls=int(sub.poll_id.nunique()), polls=', '.join(sorted(sub.poll_id.unique())),
                   lists_covered=', '.join([model.ref] + [model.targets[i] for i in seen]))
        for i, k in enumerate(model.targets):
            if i in seen:
                row[f'log_ratio_vs_ref__{k}'] = float(np.median(z[:, i]))
                row[f'lo80__{k}'] = float(np.quantile(z[:, i], 0.1))
                row[f'hi80__{k}'] = float(np.quantile(z[:, i], 0.9))
        if model.targets.index(stu) in seen:
            row['p_reference_ahead_of_student'] = float((z[:, model.targets.index(stu)] < 0).mean())
        rows.append(row)
    return pd.DataFrame(rows)
