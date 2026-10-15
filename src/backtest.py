"""Stage 12: what CAN be backtested with this dataset, done without leakage - and what cannot.

Data limits (stated, not hidden):
  * The package holds two national parliamentary elections (2022, 2023) at unit level. There are NO past polls, so the national
    stage (polls -> national shares) cannot be backtested here. See RESEARCH_LEADS.md for the data that would allow it.
  * 2022 unit registers and turnout are absent; only 2022 valid votes by list family exist. Turnout therefore cannot be
    backtested as a rate; the 2022 -> 2023 change in valid votes is used as the empirical reference for unit-level dispersion.

What is backtested: the DOWNSCALING (national result -> unit geography) 2022 -> 2023, conditional on the true 2023 national
family totals and unit valid votes. Nothing from 2023 enters a prediction except those two sets of known margins.
    B1  methods for the geography of continuing families: carry-forward, proportional swing (IPF; the pipeline's method), additive swing
    B2  geography assumptions for lists that are NEW in the target election (the 2026 student list is such a case): which earlier
        electorate does a new list follow? (two 2023 newcomers serve as test cases)
    B3  calibration of the unit-dispersion estimate with leave-one-region-out
"""
import numpy as np
import pandas as pd

import voteshare as VS


def _wide(ufv, eid, col, units):
    d = ufv[ufv.election_id == eid].pivot_table(index='geo_id', columns='family', values=col, aggfunc='sum')
    return d.reindex(units).fillna(0.0)


def prepare(ufv, panel, prev_id, curr_id):
    units = panel.geo_id.tolist()
    v0, v1 = _wide(ufv, prev_id, 'votes', units), _wide(ufv, curr_id, 'votes', units)
    s0 = v0.div(v0.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    R = v1.sum(axis=1).values
    T = v1.sum(axis=0)
    cont = [f for f in v1.columns if f in v0.columns and v0[f].sum() > 0 and v1[f].sum() > 0]
    new = [f for f in v1.columns if f not in cont]
    return dict(units=units, s0=s0, v1=v1, R=R, T=T, cont=cont, new=new)


def _weights(prep, new_geo):
    """Weight matrix for the 2023 families: continuing families follow their own 2022 share; each new family follows `new_geo[f]`
    (a vector over units)."""
    cols, W = [], []
    for f in prep['v1'].columns:
        cols.append(f)
        if f in prep['cont']:
            W.append(prep['s0'][f].values)
        else:
            W.append(new_geo[f])
    W = np.maximum(np.array(W).T, 1e-6)
    return cols, W


def method_carry_forward(prep):
    cols, W = _weights(prep, {f: np.full(len(prep['R']), 1.0) for f in prep['new']})
    S = W / W.sum(axis=1, keepdims=True)
    return cols, S * prep['R'][:, None]


def method_proportional(prep, new_geo):
    cols, W = _weights(prep, new_geo)
    return cols, VS.rake(W, prep['R'], prep['T'][cols].values)


def method_additive(prep, new_geo):
    cols, W = _weights(prep, new_geo)
    return cols, VS.additive_fit(W, prep['R'], prep['T'][cols].values)


def _metrics(pred, prep, cols, families):
    R = prep['R']
    out = {}
    for f in families:
        j = cols.index(f)
        a = prep['v1'][f].values / R
        p = pred[:, j] / R
        out[f] = dict(mae_pp=float(100 * np.average(np.abs(a - p), weights=R)), rmse_pp=float(100 * np.sqrt(np.average((a - p) ** 2, weights=R))),
                      corr=float(np.corrcoef(a, p)[0, 1]) if a.std() > 0 and p.std() > 0 else np.nan)
    return out


def b1_geography_methods(prep):
    """Continuing families; new 2023 families are given the geography of the broad opposition 2022 (documented default)."""
    anchor = 'OPP_BROAD' if 'OPP_BROAD' in prep['s0'].columns else prep['cont'][0]
    new_geo = {f: prep['s0'][anchor].values for f in prep['new']}
    big = [f for f in prep['cont'] if prep['T'][f] / prep['T'].sum() >= 0.02]
    rows = []
    for name, fn in (('carry_forward_2022_shares', lambda: method_carry_forward(prep)),
                     ('proportional_swing_IPF', lambda: method_proportional(prep, new_geo)),
                     ('additive_uniform_swing', lambda: method_additive(prep, new_geo))):
        cols, pred = fn()
        m = _metrics(pred, prep, cols, big)
        idx = [cols.index(f) for f in big]
        pred_win = np.array(big)[pred[:, idx].argmax(axis=1)]
        true_win = np.array(big)[prep['v1'][big].values.argmax(axis=1)]
        winner_acc = float(np.average(pred_win == true_win, weights=prep['R']))
        for f, mm in m.items():
            rows.append(dict(method=name, family=f, national_share=float(prep['T'][f] / prep['T'].sum()), **mm))
        rows.append(dict(method=name, family='ALL (vote-weighted mean of the above)', national_share=np.nan,
                         mae_pp=float(np.mean([v['mae_pp'] for v in m.values()])), rmse_pp=float(np.mean([v['rmse_pp'] for v in m.values()])),
                         corr=float(np.nanmean([v['corr'] for v in m.values()])), winner_accuracy_weighted=winner_acc))
    return pd.DataFrame(rows)


def b2_new_list_geography(prep):
    """Which earlier electorate does a NEW list follow? Evaluated on the families that are new in the later election."""
    s0, R = prep['s0'], prep['R']
    units = len(R)
    cands = {
        'follows_broad_opposition_2022': lambda: s0['OPP_BROAD'].values,
        'follows_all_opposition_2022 (broad + other, equal weight)': lambda: s0['OPP_BROAD'].values + (s0['OPP_OTHER'].values if 'OPP_OTHER' in s0 else 0),
        'follows_opposition_2022_inverse_SNS': lambda: 1.0 - s0['SNS_LED'].values,
        'proportional_to_valid_votes (no geography)': lambda: np.ones(units),
        'follows_SNS_led_2022': lambda: s0['SNS_LED'].values,
    }
    rows = []
    for f in prep['new']:
        for name, g in cands.items():
            geo = {x: (g() if x == f else np.full(units, 1.0)) for x in prep['new']}
            cols, pred = method_proportional(prep, geo)
            j = cols.index(f)
            a, p = prep['v1'][f].values / R, pred[:, j] / R
            rows.append(dict(new_family=f, national_share=float(prep['T'][f] / prep['T'].sum()), assumption=name,
                             mae_pp=float(100 * np.average(np.abs(a - p), weights=R)),
                             corr=float(np.corrcoef(a, p)[0, 1]),
                             mae_relative_to_mean_share=float(np.average(np.abs(a - p), weights=R) / np.average(a, weights=R))))
    return pd.DataFrame(rows)


def b3_leave_region_out(prep, panel, ufv, prev_id, curr_id):
    """Unit dispersion estimated WITHOUT region r vs the realised dispersion of the proportional-swing residuals inside r."""
    anchor = 'OPP_BROAD' if 'OPP_BROAD' in prep['s0'].columns else prep['cont'][0]
    new_geo = {f: prep['s0'][anchor].values for f in prep['new']}
    cols, pred = method_proportional(prep, new_geo)
    R = prep['R']
    reg = panel.set_index('geo_id').region_id.reindex(prep['units']).values
    fixed = (panel.fixed_rate.astype(bool) | (panel.is_special_electorate == 1)).values
    big = [f for f in prep['cont'] if prep['T'][f] / prep['T'].sum() >= 0.02]
    rows = []
    wts = pd.Series(R, index=prep['units'])
    regs = pd.Series(reg, index=prep['units'])
    for r in sorted({x for x in reg if isinstance(x, str)}):
        free = pd.Series((~fixed) & (reg != r), index=prep['units'])
        sw = VS.swing_dispersion(ufv, prev_id, curr_id, wts, regs, free)
        inr = (reg == r) & ~fixed
        for f in big:
            if f not in sw.index:
                continue
            j = cols.index(f)
            a, p = prep['v1'][f].values, pred[:, j]
            ok = inr & (a > 0) & (p > 0)
            if ok.sum() < 5:
                continue
            res = np.log(a[ok] / R[ok]) - np.log(p[ok] / R[ok])
            res = res - np.average(res, weights=R[ok])
            rows.append(dict(held_out_region=r, family=f, n_units=int(ok.sum()), predicted_sd_from_other_regions=float(sw.loc[f, 'sd_unit_total']),
                             realised_sd_in_region=float(np.sqrt(np.average(res ** 2, weights=R[ok])))))
    out = pd.DataFrame(rows)
    out['ratio_realised_to_predicted'] = out.realised_sd_in_region / out.predicted_sd_from_other_regions
    return out


def run(ufv, panel, prev_id, curr_id):
    prep = prepare(ufv, panel, prev_id, curr_id)
    return dict(b1=b1_geography_methods(prep), b2=b2_new_list_geography(prep), b3=b3_leave_region_out(prep, panel, ufv, prev_id, curr_id),
                n_units=len(prep['units']), continuing=prep['cont'], new=prep['new'])
