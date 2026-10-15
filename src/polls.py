"""Stage 5: polls as noisy measurements of national list strength (not as vote shares).

Model (applied to additive log-ratios against a reference list, so it is coherent when polls omit or lump the other lists):
    y_{p,k} = theta_k(t_p) + h_{j(p),k} + e_{p,k}
    theta_k(t)  random walk in time (daily SD sigma_rw)        <- real movement of opinion
    h_{j,k}     pollster ("house") effect, N(0, tau_h^2)        <- systematic pollster/mode/base differences
    The random-walk, house and election-day shocks are independent shocks to each LIST's log strength, so the ratio coordinates have
    covariance v (I + 11')/2 (see alr_cov); this makes the aggregate invariant to the choice of reference list.
    e_p         sampling error from the multinomial delta method with a design effect
    + at the election: independent N(0, sigma_E^2) polling miss shared by all houses.
Estimated with a Kalman filter on the augmented state [theta, h]; nothing is fitted by simulation.

Identification limits (reported, not hidden): with few polls, the level of the average house effect is not identified from
polls alone - the prior mean of zero says "the average pollster is unbiased". Leave-one-house-out runs show how much the
answer depends on each house. Prediction-market prices and local election results are NOT inputs here.
"""
import numpy as np
import pandas as pd


def alr_cov(d, v):
    """Covariance of d additive-log-ratio coordinates when the d+1 underlying log-strengths carry INDEPENDENT shocks.

    If every list's log strength gets an independent shock with variance v/2, the ratio to the reference has variance v and every
    pair of ratios has covariance v/2 (they share the reference's shock). This keeps the model invariant to the choice of reference
    list: treating the ratio coordinates themselves as independent would make the answer depend on that arbitrary choice."""
    return v * (np.eye(d) + np.ones((d, d))) / 2.0



def prepare_log_ratios(panel, reference, targets, default_sample=1000, design_effect=2.0, decided_fraction=1.0):
    """Turn s5_poll_panel rows into ALR observations.

    panel      DataFrame with poll_id, pollster, poll_date, list_key, share, sample_size
    reference  list_key used as denominator
    targets    ordered list of list_keys that form the coordinates
    Returns (obs, polls): obs is a list of dicts {poll_id, house, date, idx (coordinate indices observed), y, R}; polls a summary frame.
    """
    obs, rows = [], []
    for pid, g in panel.groupby('poll_id', sort=False):
        sh = g.set_index('list_key').share.astype(float)
        if reference not in sh.index or not (sh[reference] > 0):
            continue
        n = g.sample_size.iloc[0]
        n_missing = pd.isna(n)
        n_eff = (default_sample if n_missing else float(n)) * decided_fraction / design_effect
        idx, y = [], []
        for i, k in enumerate(targets):
            if k in sh.index and sh[k] > 0:
                idx.append(i)
                y.append(np.log(sh[k] / sh[reference]))
        if not idx:
            continue
        pc = sh[reference]
        pk = np.array([sh[targets[i]] for i in idx])
        # multinomial delta method: Var(log a/c) = (1-a)/(n a) + (1-c)/(n c) + 2/n ; Cov = 1/(n c)  (c = reference share)
        R = np.full((len(idx), len(idx)), 1.0 / (n_eff * pc))
        for a in range(len(idx)):
            R[a, a] = (1 - pk[a]) / (n_eff * pk[a]) + (1 - pc) / (n_eff * pc) + 2.0 / n_eff
        obs.append(dict(poll_id=pid, house=g.pollster.iloc[0], date=pd.Timestamp(g.poll_date.iloc[0]), idx=idx, y=np.array(y), R=R,
                        n_eff=n_eff, n_missing=bool(n_missing)))
        rows.append(dict(poll_id=pid, house=g.pollster.iloc[0], date=pd.Timestamp(g.poll_date.iloc[0]), n_eff=n_eff,
                         sample_missing=bool(n_missing), coords_observed=len(idx)))
    obs.sort(key=lambda o: o['date'])
    return obs, pd.DataFrame(rows)


def moment_house_sd(obs, coord=None):
    """Between-house SD of the house-average log-ratio (diagnostic and default for tau_h).

    coord=None (default): pooled over ALL pairs of lists, i.e. the root of the average between-house variance of log(share_a/share_b)
        over every pair (a, b) observed together. Under the model every pair difference has house-effect variance tau_h^2, and the pooled
        estimator does not depend on which list happens to be the reference.
    coord=i: only the i-th ALR coordinate (kept for diagnostics; it DOES depend on the reference choice).
    Returns (sd, number_of_houses_used)."""
    houses = sorted({o['house'] for o in obs})
    if coord is not None:
        per_house = {}
        for o in obs:
            if coord in o['idx']:
                per_house.setdefault(o['house'], []).append(o['y'][o['idx'].index(coord)])
        means = np.array([np.mean(v) for v in per_house.values()])
        return (float(np.std(means, ddof=1)) if len(means) >= 2 else np.nan), len(means)
    # log-strengths with the reference at 0; coordinate i is index i + 1, reference is index 0
    per_pair = {}
    for o in obs:
        z = {0: 0.0}
        for i, yv in zip(o['idx'], o['y']):
            z[i + 1] = float(yv)
        keys = sorted(z)
        for a in range(len(keys)):
            for b in range(a + 1, len(keys)):
                per_pair.setdefault((keys[a], keys[b]), {}).setdefault(o['house'], []).append(z[keys[a]] - z[keys[b]])
    variances, n_used = [], 0
    for _, byhouse in per_pair.items():
        if len(byhouse) >= 2:
            variances.append(float(np.var([np.mean(v) for v in byhouse.values()], ddof=1)))
            n_used = max(n_used, len(byhouse))
    if not variances:
        return np.nan, len({o['house'] for o in obs})
    return float(np.sqrt(np.mean(variances))), n_used


def kalman_polls(obs, d, tau_h, sigma_rw_per_day, prior_mean=None, prior_sd=2.0, exclude_house=None):
    """Filter polls forward in time. Returns dict with state mean/cov at the last poll date and the house list.
    State = [theta_0..theta_{d-1}] + [h_{j,0..d-1} for each house j]."""
    houses = sorted({o['house'] for o in obs if o['house'] != exclude_house})
    hidx = {h: i for i, h in enumerate(houses)}
    D = d * (1 + len(houses))
    m = np.zeros(D)
    if prior_mean is not None:
        m[:d] = prior_mean
    P = np.zeros((D, D))
    P[:d, :d] = alr_cov(d, prior_sd ** 2)
    for j in range(len(houses)):
        sl = slice(d * (1 + j), d * (2 + j))
        P[sl, sl] = alr_cov(d, tau_h ** 2)
    last_date, loglik = None, 0.0
    for o in obs:
        if o['house'] == exclude_house:
            continue
        if last_date is not None:
            dt = max((o['date'] - last_date).days, 0)
            P[:d, :d] += alr_cov(d, sigma_rw_per_day ** 2 * dt)
        last_date = o['date']
        k = len(o['idx'])
        H = np.zeros((k, D))
        j = hidx[o['house']]
        for r, i in enumerate(o['idx']):
            H[r, i] = 1.0
            H[r, d * (1 + j) + i] = 1.0
        S = H @ P @ H.T + o['R']
        K = P @ H.T @ np.linalg.inv(S)
        innov = o['y'] - H @ m
        loglik += -0.5 * (np.linalg.slogdet(2 * np.pi * S)[1] + innov @ np.linalg.solve(S, innov))
        m = m + K @ innov
        P = (np.eye(D) - K @ H) @ P
        P = (P + P.T) / 2
    return dict(mean=m, cov=P, last_date=last_date, houses=houses, loglik=loglik, d=d)


def predict_at(state, target_date, sigma_rw_per_day, sigma_election):
    """Predictive distribution of theta at the election date, plus the election-day polling miss."""
    d = state['d']
    dt = max((pd.Timestamp(target_date) - state['last_date']).days, 0)
    mean = state['mean'][:d].copy()
    cov = state['cov'][:d, :d] + alr_cov(d, sigma_rw_per_day ** 2 * dt + sigma_election ** 2)
    return mean, cov, dt


def aggregate(panel, reference, targets, target_date, *, tau_h_floor, sigma_rw_per_day, sigma_election, design_effect,
              default_sample, prior_sd=2.0, leave_out=None):
    """End-to-end poll aggregation. `leave_out` removes one pollster (sensitivity)."""
    obs, summary = prepare_log_ratios(panel, reference, targets, default_sample=default_sample, design_effect=design_effect)
    sd_est, n_h = moment_house_sd(obs)
    tau_h = max(tau_h_floor, sd_est if np.isfinite(sd_est) else 0.0)
    st = kalman_polls(obs, len(targets), tau_h, sigma_rw_per_day, prior_sd=prior_sd, exclude_house=leave_out)
    mean, cov, dt = predict_at(st, target_date, sigma_rw_per_day, sigma_election)
    return dict(mean=mean, cov=cov, tau_h=tau_h, tau_h_moment_estimate=sd_est, n_houses=n_h, days_to_election=dt,
                last_poll_date=st['last_date'], houses=st['houses'], targets=list(targets), reference=reference, summary=summary)


def draws_to_shares(z, include_reference=True):
    """ALR draws (n, d) -> shares over [reference] + targets that sum to one (softmax)."""
    z = np.asarray(z, float)
    e = np.exp(np.concatenate([np.zeros((len(z), 1)), z], axis=1) - np.max(np.concatenate([np.zeros((len(z), 1)), z], axis=1), axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)
