"""Poll aggregation: invariance to the reference list, sensible behaviour with house effects, and a recovery test on synthetic polls."""
import numpy as np
import pandas as pd

import polls as PO


def _synthetic(seed=0, n_polls=12, true=(0.45, 0.35, 0.10, 0.06, 0.04), houses=('A', 'B', 'C'), house_sd=0.12):
    rng = np.random.default_rng(seed)
    keys = ['k0', 'k1', 'k2', 'k3', 'k4']
    h = {x: rng.normal(0, house_sd, size=5) for x in houses}
    rows = []
    for i in range(n_polls):
        hs = houses[i % len(houses)]
        n = 1000
        logp = np.log(np.array(true)) + h[hs]
        p = np.exp(logp) / np.exp(logp).sum()
        counts = rng.multinomial(n, p)
        sh = counts / n
        for k, s in zip(keys, sh):
            rows.append(dict(poll_id=f'p{i}', pollster=hs, poll_date=pd.Timestamp('2026-08-01') + pd.Timedelta(days=3 * i), list_key=k, share=s, sample_size=n))
    return pd.DataFrame(rows), keys, h


def _agg(panel, ref, targets, **kw):
    return PO.aggregate(panel, ref, targets, pd.Timestamp('2026-10-25'), tau_h_floor=0.1, sigma_rw_per_day=0.004, sigma_election=0.1,
                        design_effect=1.0, default_sample=1000, prior_sd=3.0, **kw)


def _shares(agg, n=40000, seed=1):
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal(agg['mean'], agg['cov'], size=n)
    return PO.draws_to_shares(z), agg['reference'], agg['targets']


def test_invariance_to_reference_choice():
    panel, keys, _ = _synthetic()
    out = {}
    for ref in ('k0', 'k2'):
        targets = [k for k in keys if k != ref]
        sh, r, t = _shares(_agg(panel, ref, targets))
        order = [r] + t
        out[ref] = pd.Series(np.median(sh, axis=0), index=order).reindex(keys)
    assert np.allclose(out['k0'].values, out['k2'].values, atol=0.004), (out['k0'].values, out['k2'].values)


def test_variance_of_shares_is_invariant_too():
    panel, keys, _ = _synthetic(seed=2)
    sds = {}
    for ref in ('k1', 'k4'):
        sh, r, t = _shares(_agg(panel, ref, [k for k in keys if k != ref]))
        sds[ref] = pd.Series(sh.std(axis=0), index=[r] + t).reindex(keys)
    assert np.allclose(sds['k1'].values, sds['k4'].values, rtol=0.06)


def test_recovers_truth_within_uncertainty():
    hits, total = 0, 0
    for seed in range(15):
        panel, keys, _ = _synthetic(seed=seed, n_polls=15)
        sh, r, t = _shares(_agg(panel, 'k0', keys[1:]), n=4000)
        lo, hi = np.quantile(sh, [0.05, 0.95], axis=0)
        true = np.array((0.45, 0.35, 0.10, 0.06, 0.04))
        hits += int(((lo <= true) & (true <= hi)).sum())
        total += 5
    assert hits / total > 0.80        # nominal 90 percent central interval (the aggregate also adds election-day error)


def test_house_effects_widen_uncertainty_when_polls_disagree():
    panel, keys, _ = _synthetic(seed=3, house_sd=0.0)
    a = _agg(panel, 'k0', keys[1:])
    panel2, _, _ = _synthetic(seed=3, house_sd=0.4)
    b = _agg(panel2, 'k0', keys[1:])
    assert b['tau_h'] >= a['tau_h']
