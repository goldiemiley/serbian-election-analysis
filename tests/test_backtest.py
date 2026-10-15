"""Stage 12 backtest: no leakage, and the claims made about the methods hold on the real data."""
import numpy as np

import backtest as BT
import voteshare as VS


def _prep(model):
    return BT.prepare(model.ufv, model.panel, model.prev_id, model.curr_id)


def test_predictions_use_only_margins_and_earlier_election(model):
    """Replace the 2023 unit-level family votes by an arbitrary matrix with the SAME margins: predictions must not change."""
    prep = _prep(model)
    anchor = prep['s0']['OPP_BROAD'].values
    new_geo = {f: anchor for f in prep['new']}
    cols, p1 = BT.method_proportional(prep, new_geo)
    rng = np.random.default_rng(0)
    fake = VS.rake(rng.uniform(0.5, 1.5, size=(len(prep['R']), len(cols))), prep['R'], prep['T'][cols].values)
    prep2 = dict(prep)
    prep2['v1'] = prep['v1'].copy()
    prep2['v1'][cols] = fake
    cols2, p2 = BT.method_proportional(prep2, new_geo)
    assert cols == cols2 and np.allclose(p1, p2)


def test_margins_are_reproduced(model):
    prep = _prep(model)
    new_geo = {f: prep['s0']['OPP_BROAD'].values for f in prep['new']}
    for fn in (BT.method_proportional, BT.method_additive):
        cols, pred = fn(prep, new_geo)
        assert np.allclose(pred.sum(axis=1), prep['R'], rtol=1e-8)
        assert np.allclose(pred.sum(axis=0), prep['T'][cols].values, rtol=1e-6)


def test_national_calibration_beats_carry_forward(model):
    res = BT.b1_geography_methods(_prep(model))
    tot = res[res.family.str.startswith('ALL')].set_index('method')
    assert tot.loc['proportional_swing_IPF', 'mae_pp'] < 0.3 * tot.loc['carry_forward_2022_shares', 'mae_pp']


def test_new_list_geography_assumption_is_informative(model):
    b2 = BT.b2_new_list_geography(_prep(model))
    g = b2[b2.new_family == 'MI_GIN'].set_index('assumption')
    assert g.loc['follows_broad_opposition_2022', 'corr'] > 0.5
    assert g.loc['follows_broad_opposition_2022', 'mae_pp'] < g.loc['proportional_to_valid_votes (no geography)', 'mae_pp']


def test_additive_fit_batch_matches_single():
    rng = np.random.default_rng(2)
    W = rng.uniform(0.2, 1.0, size=(40, 5))
    R = rng.uniform(1e3, 5e3, size=40)
    T = rng.dirichlet(np.ones(5) * 4) * R.sum()
    single = VS.additive_fit(W, R, T)
    batch = VS.additive_fit(W, R, np.stack([T, T]))
    assert np.allclose(single, batch[0]) and np.allclose(single.sum(0), T, rtol=1e-6)
