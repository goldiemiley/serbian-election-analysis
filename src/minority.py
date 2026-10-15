"""Stage 7: minority lists modelled one by one, bottom-up, from their own 2023 votes (never merged into "Others").

For every 2026 minority list the config table cfg_minority_roster_map states which 2023 family (if any) it continues, the
minority group it competes in, and whether it is a continuing list, a new entrant, or prior-only.

  continuing list  votes = group pool x (1 - sum of entrant captures) x its share of the group's 2023 votes
  new entrant      votes = group pool x capture share (Beta prior: no history exists for the organisation)
  prior-only list  votes ~ LogNormal (no group base in the data)
  group pool       B_g x exp(phi x log(valid votes now / valid votes at baseline) + group shock)

phi (turnout responsiveness of the group), the shock SD, and the entrant/prior-only parameters are analyst priors (cfg_parameters,
category minority); they are NOT estimated because the dataset holds a single election with minority lists at unit level that
can be compared to a known turnout change. The effect of the 1.35 multiplier and of the 3 percent exemption is handled by
electoral_law.py, only for lists whose status in cfg_list_registry_2026 is 'yes'.
"""
import numpy as np
import pandas as pd


def build_structures(roster_map, base_long, unit_ids, unit_region, unit_registered):
    """Static structures: list order, group pools, shares inside groups and unit patterns."""
    rm = roster_map.reset_index(drop=True)
    fam_tot = base_long.groupby('family').votes_baseline.sum()
    fam_unit = base_long.pivot_table(index='geo_id', columns='family', values='votes_baseline', aggfunc='sum').reindex(unit_ids).fillna(0.0)
    groups = {}
    for g, sub in rm.groupby('minority_group'):
        cont = sub[(sub.role == 'continuing') & sub.analog_family.notna() & (sub.analog_family != '')]
        fams = list(dict.fromkeys(cont.analog_family))
        # families of the same group that are continued by any list in the group
        B = float(sum(fam_tot.get(f, 0.0) for f in fams))
        groups[g] = dict(families=fams, B=B,
                         unit_votes=fam_unit[fams].sum(axis=1).values if fams else np.zeros(len(unit_ids)))
    L = len(rm)
    patterns = np.zeros((L, len(unit_ids)))
    cont_share = np.zeros(L)
    base_votes = np.zeros(L)
    for i, r in rm.iterrows():
        g = groups[r.minority_group]
        if r.unit_pattern == 'analog_family' and r.analog_family:
            v = fam_unit[r.analog_family].values.astype(float)
            base_votes[i] = fam_tot.get(r.analog_family, 0.0)
            cont_share[i] = base_votes[i] / g['B'] if g['B'] > 0 else 0.0
        elif r.unit_pattern == 'group_pool':
            v = g['unit_votes'].astype(float)
        elif r.unit_pattern == 'region_uniform':
            v = np.where(np.asarray(unit_region) == 'RS12', np.asarray(unit_registered, float), 0.0)
        else:
            raise ValueError(f'unknown unit_pattern {r.unit_pattern!r} for {r.list_key}')
        patterns[i] = v / v.sum() if v.sum() > 0 else 0.0
    # continuing shares within a group must add to one among the group's continuing lists
    for g, sub in rm.groupby('minority_group'):
        idx = sub.index[(sub.role == 'continuing')]
        s = cont_share[idx].sum()
        if s > 0:
            cont_share[idx] = cont_share[idx] / s
    return dict(roster_map=rm, groups=groups, patterns=patterns, cont_share=cont_share, base_votes=base_votes)


def simulate_votes(struct, n, valid_ratio_log, params, rng, phi=None):
    """Draw minority-list votes. valid_ratio_log: array (n,) = log(valid votes of the draw / baseline valid votes)."""
    rm = struct['roster_map']
    L = len(rm)
    out = np.zeros((n, L))
    lo, hi = params['minority_turnout_responsiveness_low'], params['minority_turnout_responsiveness_high']
    phi_n = rng.uniform(lo, hi, size=n) if phi is None else np.full(n, float(phi))
    a = params['minority_new_entrant_capture_mean'] * params['minority_new_entrant_capture_concentration']
    b = (1 - params['minority_new_entrant_capture_mean']) * params['minority_new_entrant_capture_concentration']
    for g, sub in rm.groupby('minority_group'):
        B = struct['groups'][g]['B']
        shock = rng.normal(0.0, params['minority_group_shock_sdlog'], size=n)
        pool = B * np.exp(phi_n * valid_ratio_log + shock)
        ent = sub.index[sub.role == 'new_entrant']
        pi = rng.beta(a, b, size=(n, len(ent))) if len(ent) else np.zeros((n, 0))
        tot_pi = pi.sum(axis=1)
        scale = np.where(tot_pi > 0.8, 0.8 / np.maximum(tot_pi, 1e-12), 1.0)
        pi = pi * scale[:, None]
        rem = 1 - pi.sum(axis=1)
        for i in sub.index[sub.role == 'continuing']:
            out[:, i] = pool * rem * struct['cont_share'][i]
        for j, i in enumerate(ent):
            out[:, i] = pool * pi[:, j]
    for i in rm.index[rm.role == 'prior_only']:
        out[:, i] = np.exp(np.log(params['minority_prior_only_votes_median']) + rng.normal(0, params['minority_prior_only_votes_sdlog'], size=n))
    return np.rint(out), phi_n
