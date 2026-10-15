"""Vectorised seat allocation for Monte Carlo draws.

The scalar rules live in electoral_law.py (tested against the official 2023 distribution and against exact arithmetic).
This module applies the same rules to thousands of draws at once:

    per draw:   eligible lists -> effective votes (x multiplier for minority lists) -> the `seats` largest quotients
                v_eff / d, d = 1..seats, win a seat each.
    batch rule: the `seats`-th largest quotient is the cut-off; a list's seats = number of its quotients >= cut-off.
                If more than `seats` quotients reach the cut-off (an exact tie at the last seat) the draw is re-run through the
                scalar function, which breaks the tie by total votes exactly as the statute-based rule in electoral_law.py does.
"""
import numpy as np

import electoral_law as EL


def allocate_batch(votes, is_minority, threshold_base, *, seats, threshold_share, minority_multiplier,
                   uplift_scope='all_minority', fallback_if_none_reach=True, chunk=1500):
    """votes (n, L) non-negative integers-as-floats; is_minority (L,) bool; threshold_base (n,) = voters counted by the
    threshold rule in every draw. Returns dict(seats (n, L) int, eligible (n, L) bool, threshold_votes (n,), n_fallback int)."""
    votes = np.asarray(votes, float)
    n, L = votes.shape
    is_minority = np.asarray(is_minority, bool)
    thr = threshold_share * np.asarray(threshold_base, float)
    if EL.UPLIFT_SCOPES.count(uplift_scope) == 0:
        raise ValueError(f'uplift_scope must be one of {EL.UPLIFT_SCOPES}')
    passes = votes >= thr[:, None]
    if fallback_if_none_reach:
        none = ~passes.any(axis=1)
        passes[none] = votes[none] > 0
    eligible = passes | (is_minority[None, :] & (votes > 0))
    if uplift_scope == 'all_minority':
        uplift = np.broadcast_to(is_minority[None, :], votes.shape)
    else:
        uplift = is_minority[None, :] & (votes < thr[:, None])
    eff = np.where(uplift, votes * minority_multiplier, votes)
    divisors = np.arange(1, seats + 1, dtype=float)
    out = np.zeros((n, L), dtype=np.int32)
    n_fallback = 0
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        q = np.where(eligible[a:b, :, None], eff[a:b, :, None] / divisors[None, None, :], -1.0)   # (c, L, S)
        flat = q.reshape(b - a, L * seats)
        kth = L * seats - seats
        cutoff = np.partition(flat, kth, axis=1)[:, kth]
        ge = q >= cutoff[:, None, None]
        s = ge.sum(axis=2)
        total = s.sum(axis=1)
        bad = (total != seats) | (cutoff <= 0)
        out[a:b] = s
        for i in np.flatnonzero(bad):
            r = EL.allocate_seats(votes[a + i], is_minority, seats=seats, threshold_share=threshold_share,
                                  threshold_base=threshold_base[a + i] if np.ndim(threshold_base) else threshold_base,
                                  minority_multiplier=minority_multiplier, uplift_scope=uplift_scope,
                                  fallback_if_none_reach=fallback_if_none_reach)
            out[a + i] = r['seats']
            n_fallback += 1
    return dict(seats=out, eligible=eligible, threshold_votes=thr, n_fallback=n_fallback)
