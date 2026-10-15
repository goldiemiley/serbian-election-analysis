"""The batch allocator must reproduce the scalar (and exact) allocator draw by draw, including ties and threshold edges."""
import numpy as np

import allocation as AL
import electoral_law as EL

KW = dict(seats=250, threshold_share=0.03, minority_multiplier=1.35)


def _random_draws(n, rng):
    L = 14
    p = rng.dirichlet(np.array([30, 25, 4, 3, 2.5, 1, 1, .5, .4, .3, .3, .2, .2, .1]))
    votes = np.rint(rng.dirichlet(p * 60) * rng.uniform(4.0e6, 4.4e6, size=(n, 1)))
    is_min = np.array([False] * 6 + [True] * 8)
    return votes, is_min


def test_batch_equals_scalar_random():
    rng = np.random.default_rng(11)
    votes, is_min = _random_draws(600, rng)
    base = votes.sum(axis=1) * 1.01
    for scope in EL.UPLIFT_SCOPES:
        res = AL.allocate_batch(votes, is_min, base, uplift_scope=scope, **KW)
        for i in range(len(votes)):
            ref = EL.allocate_seats(votes[i], is_min, threshold_base=base[i], uplift_scope=scope, **KW)['seats']
            assert (res['seats'][i] == ref).all(), (scope, i)
        assert (res['seats'].sum(axis=1) == 250).all()


def test_batch_exact_ties():
    """Two identical lists: quotients tie at every level; the scalar tie-break must apply in the batch too."""
    votes = np.array([[1000., 1000., 500.], [1001., 1000., 500.], [3000., 2000., 1000.]])
    is_min = np.array([False, False, True])
    for seats in (2, 3, 7):
        kw = dict(KW, seats=seats)
        res = AL.allocate_batch(votes, is_min, np.array([5000., 5000., 7000.]), **kw)
        for i in range(3):
            ref = EL.allocate_seats(votes[i], is_min, threshold_base=[5000., 5000., 7000.][i], **kw)['seats']
            assert (res['seats'][i] == ref).all()


def test_nobody_reaches_threshold_fallback():
    votes = np.array([[10., 20., 5.]])
    res = AL.allocate_batch(votes, np.array([False] * 3), np.array([1000.]), **dict(KW, seats=10))
    assert res['seats'].sum() == 10 and res['eligible'].all()
