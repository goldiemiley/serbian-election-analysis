"""Serbian parliamentary seat allocation as a pure, parameterised function.

Every legal parameter is an ARGUMENT. None is baked in: the pipeline reads them from cfg_parameters
(see config/cfg_parameters.csv, which records source and verification status of each value).

Rules implemented (Law on Election of MPs, consolidated text retrieved 2026-10-14; see cfg_parameters):
  Art. 81(1)  a list takes part in the allocation only if it has >= threshold_share of `threshold_base`
              (the number of voters who voted).
  Art. 81(2)  national-minority lists take part even below the threshold; in the largest-quotient
              calculation the quotients of minority lists are multiplied by 1.35.
  Art. 82     largest-quotient (D'Hondt) method: each list's votes are divided by 1..seats, the `seats`
              largest quotients win; a tie on the last seat goes to the list with more total votes.
  Art. 82(5)  if no list reaches the threshold, all lists with votes take part.

Two points the statute leaves open are exposed as options rather than hidden:
  * threshold_base      which count is "voters who voted" (turnout / ballots cast / valid ballots).
  * uplift_scope        the statutory text uplifts quotients of ALL minority lists; official explainers
                        describe the uplift for minority lists under 3%. Results differ only if a minority
                        list reaches the threshold.

Minority STATUS is decided by the RIK per list at proclamation. It is an input (`is_minority`), never inferred.
"""
from fractions import Fraction
import numpy as np

UPLIFT_SCOPES = ('all_minority', 'below_threshold_only')


def _effective_votes(votes, is_minority, thr_votes, multiplier, uplift_scope):
    if uplift_scope == 'all_minority':
        uplift = is_minority
    elif uplift_scope == 'below_threshold_only':
        uplift = is_minority & (votes < thr_votes)
    else:
        raise ValueError(f"uplift_scope must be one of {UPLIFT_SCOPES}, got {uplift_scope!r}")
    return np.where(uplift, votes * multiplier, votes)


def eligible_lists(votes, is_minority, *, threshold_share, threshold_base, fallback_if_none_reach=True):
    """Boolean mask of lists that take part in the allocation, and the threshold in votes."""
    votes = np.asarray(votes, float)
    is_minority = np.asarray(is_minority, bool)
    thr_votes = threshold_share * float(threshold_base)
    passes = votes >= thr_votes
    if fallback_if_none_reach and not passes.any():
        passes = votes > 0
    return passes | (is_minority & (votes > 0)), thr_votes


def dhondt(effective_votes, eligible, true_votes, seats):
    """Largest-quotient allocation. Ties are broken by true (un-uplifted) total votes."""
    effective_votes = np.asarray(effective_votes, float)
    eligible = np.asarray(eligible, bool)
    true_votes = np.asarray(true_votes, float)
    idx = np.flatnonzero(eligible)
    out = np.zeros(len(effective_votes), dtype=int)
    if idx.size == 0:
        return out
    divisors = np.arange(1, seats + 1, dtype=float)
    quot = (effective_votes[idx, None] / divisors[None, :]).ravel()
    owner = np.repeat(idx, seats)
    tiebreak = true_votes[owner]
    order = np.lexsort((-tiebreak, -quot))          # primary key: quotient desc; secondary: true votes desc
    winners = owner[order[:seats]]
    np.add.at(out, winners, 1)
    return out


def allocate_seats(votes, is_minority, *, seats, threshold_share, threshold_base,
                   minority_multiplier, uplift_scope='all_minority', fallback_if_none_reach=True):
    """Full allocation for one election outcome. Returns dict(seats, eligible, threshold_votes)."""
    votes = np.asarray(votes, float)
    is_minority = np.asarray(is_minority, bool)
    eligible, thr_votes = eligible_lists(votes, is_minority, threshold_share=threshold_share,
                                         threshold_base=threshold_base,
                                         fallback_if_none_reach=fallback_if_none_reach)
    eff = _effective_votes(votes, is_minority, thr_votes, minority_multiplier, uplift_scope)
    return dict(seats=dhondt(eff, eligible, votes, seats), eligible=eligible, threshold_votes=thr_votes)


# --------------------------------------------------------------------------------------------------
# Exact-arithmetic reference (slow). Used only by tests to confirm the float version never mis-assigns
# a seat because of floating-point rounding. Inputs must be integers (vote counts) and a Fraction-able
# multiplier such as "1.35".
def allocate_seats_exact(votes, is_minority, *, seats, threshold_share, threshold_base, minority_multiplier,
                         uplift_scope='all_minority', fallback_if_none_reach=True):
    votes = [int(v) for v in votes]
    is_minority = [bool(m) for m in is_minority]
    share = Fraction(str(threshold_share))
    mult = Fraction(str(minority_multiplier))
    thr = share * Fraction(int(threshold_base))
    passes = [Fraction(v) >= thr for v in votes]
    if fallback_if_none_reach and not any(passes):
        passes = [v > 0 for v in votes]
    eligible = [p or (m and v > 0) for p, m, v in zip(passes, is_minority, votes)]
    quotients = []
    for i, v in enumerate(votes):
        if not eligible[i]:
            continue
        if uplift_scope == 'all_minority':
            up = is_minority[i]
        else:
            up = is_minority[i] and Fraction(v) < thr
        base = Fraction(v) * (mult if up else 1)
        for d in range(1, seats + 1):
            quotients.append((base / d, v, i))
    quotients.sort(key=lambda t: (-t[0], -t[1]))
    out = [0] * len(votes)
    for _, _, i in quotients[:seats]:
        out[i] += 1
    return out
