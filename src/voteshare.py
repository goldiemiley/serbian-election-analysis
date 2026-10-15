"""Stages 6 and 8: unit-level vote geography calibrated to national targets (top-down downscaling).

What is observed        : 2023 votes by family per unit (s6_unit_geography_base), 2022 -> 2023 swing dispersion.
What is assumed         : cfg_origin_weights (which families a 2026 list's geography follows) - analyst, unreviewed.
What is calibrated      : the national LEVEL of every list, to the poll-based target of the draw.
Compositionality        : a unit's list shares are w_uk a_k / sum_j w_uj a_j, so they sum to one in every unit by construction.
Consistency             : sum_u R_u s_uk = T_k for every list (R_u = non-minority valid votes of the unit), so unit votes add up to
                          the national totals exactly (checked in tests).
"""
import numpy as np
import pandas as pd


def build_unit_weights(base_long, origin_weights, list_keys, unit_ids, floor_rel=1e-4):
    """Weights W0[u, k] = sum_o weight_{k,o} * per_registered_{u,o}. Floored to keep every cell strictly positive."""
    piv = base_long.pivot_table(index='geo_id', columns='origin', values='per_registered', aggfunc='sum').reindex(unit_ids)
    W = np.zeros((len(unit_ids), len(list_keys)))
    for j, k in enumerate(list_keys):
        rows = origin_weights[origin_weights.list_key == k]
        for _, r in rows.iterrows():
            if r.origin in piv.columns:
                W[:, j] += float(r.weight) * piv[r.origin].fillna(0).values
    floor = floor_rel * max(W.mean(), 1e-12)
    return np.maximum(W, floor)


def rake(W, R, T, max_iter=500, tol=1e-12):
    """Iterative proportional fitting with row normalisation (batched over draws).

    W : (U, K) or (B, U, K) positive weights;  R : (U,) or (B, U) row masses;  T : (K,) or (B, K) column targets,
    with sum_k T = sum_u R in every draw. Returns votes shaped (U, K) or (B, U, K) whose rows sum to R and columns to T."""
    W = np.asarray(W, float)
    R = np.asarray(R, float)
    T = np.asarray(T, float)
    single = W.ndim == 2 and R.ndim == 1 and T.ndim == 1
    B = max(W.shape[0] if W.ndim == 3 else 1, R.shape[0] if R.ndim == 2 else 1, T.shape[0] if T.ndim == 2 else 1)
    W = np.broadcast_to(W if W.ndim == 3 else W[None], (B,) + W.shape[-2:])
    R = np.broadcast_to(R if R.ndim == 2 else R[None], (B, W.shape[1]))
    T = np.broadcast_to(T if T.ndim == 2 else T[None], (B, W.shape[2]))
    if not np.allclose(R.sum(axis=1), T.sum(axis=1), rtol=1e-8):
        raise ValueError('rake: column targets must sum to the row masses in every draw')
    a = np.ones((B, W.shape[2]))
    for _ in range(max_iter):
        M = W * a[:, None, :]
        S = M / M.sum(axis=2, keepdims=True)
        col = (S * R[:, :, None]).sum(axis=1)
        ratio = np.where(col > 0, T / np.maximum(col, 1e-300), 1.0)
        a = a * ratio
        if np.max(np.abs(ratio - 1)) < tol:
            break
    M = W * a[:, None, :]
    V = M / M.sum(axis=2, keepdims=True) * R[:, :, None]
    return V[0] if single else V


def additive_fit(W, R, T, iters=300, tol=1e-10):
    """Additive (uniform) swing on the shares implied by W: s_uk = max(S0_uk + d_k, 0), rows renormalised, d_k found iteratively so
    that column totals equal T. Same inputs/outputs as `rake` (batched). Provided as the structural alternative to proportional swing."""
    W = np.asarray(W, float)
    R = np.asarray(R, float)
    T = np.asarray(T, float)
    single = W.ndim == 2 and R.ndim == 1 and T.ndim == 1
    B = max(W.shape[0] if W.ndim == 3 else 1, R.shape[0] if R.ndim == 2 else 1, T.shape[0] if T.ndim == 2 else 1)
    W = np.broadcast_to(W if W.ndim == 3 else W[None], (B,) + W.shape[-2:])
    R = np.broadcast_to(R if R.ndim == 2 else R[None], (B, W.shape[1]))
    T = np.broadcast_to(T if T.ndim == 2 else T[None], (B, W.shape[2]))
    S0 = W / W.sum(axis=2, keepdims=True)
    d = np.zeros((B, W.shape[2]))
    tot = R.sum(axis=1, keepdims=True)
    for _ in range(iters):
        S = np.maximum(S0 + d[:, None, :], 0.0)
        S = S / S.sum(axis=2, keepdims=True)
        col = (S * R[:, :, None]).sum(axis=1)
        step = (T - col) / tot
        d += step
        if np.abs(step).max() < tol:
            break
    S = np.maximum(S0 + d[:, None, :], 0.0)
    V = S / S.sum(axis=2, keepdims=True) * R[:, :, None]
    return V[0] if single else V


def swing_dispersion(ufv, prev_id, curr_id, weights, region, free):
    """Vote-weighted SD, across units, of the log change in a family's share between two national elections, after removing the
    national weighted mean; plus the SD of region means. Computed for every family present in both elections.

    ufv     s1_unit_family_votes frame (election_id, geo_id, family, share_valid)
    weights Series geo_id -> weight (valid votes of the current election)
    region  Series geo_id -> region_id ;  free  Series geo_id -> bool (units whose swing is used)
    """
    a = ufv[ufv.election_id == prev_id].set_index(['geo_id', 'family']).share_valid
    b = ufv[ufv.election_id == curr_id].set_index(['geo_id', 'family']).share_valid
    d = pd.concat([a.rename('s0'), b.rename('s1')], axis=1).dropna()
    d = d[(d.s0 > 0) & (d.s1 > 0)].reset_index()
    d['lc'] = np.log(d.s1 / d.s0)
    d['w'] = d.geo_id.map(weights)
    d['free'] = d.geo_id.map(free).fillna(False).astype(bool)
    d['region'] = d.geo_id.map(region)
    out = {}
    for fam, g in d[d.free & d.w.notna()].groupby('family'):
        if len(g) < 30:
            continue
        mu = np.average(g.lc, weights=g.w)
        res = g.lc - mu
        sd_unit = float(np.sqrt(np.average(res ** 2, weights=g.w)))
        rm = g.assign(res=res).groupby('region').apply(lambda x: np.average(x.res, weights=x.w), include_groups=False)
        sd_region = float(rm.std(ddof=1)) if len(rm) >= 3 else np.nan
        out[fam] = dict(n_units=len(g), national_log_change=float(mu), sd_unit_total=sd_unit, sd_region_means=sd_region)
    return pd.DataFrame(out).T


def list_sigmas(origin_weights, list_keys, per_family_sd, default_sd):
    """SD of the unit-level multiplicative noise per list: weighted average of the swing SDs of the families it follows
    (pseudo-origins and families without an estimate use default_sd)."""
    out = []
    for k in list_keys:
        rows = origin_weights[origin_weights.list_key == k]
        sds, ws = [], []
        for _, r in rows.iterrows():
            sds.append(per_family_sd.get(r.origin, default_sd))
            ws.append(float(r.weight))
        out.append(float(np.average(sds, weights=ws)) if ws else default_sd)
    return np.array(out)
