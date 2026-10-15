"""Stage 10: scenario-conditional government formation arithmetic.

What is computed  : for each named coalition in cfg_coalitions, whether its members' seats reach the majority threshold in each draw.
What is NOT known : which coalitions are politically feasible. cfg_coalitions labels every coalition with an assumption set
                    and a plausibility label; the labels are analyst scenario definitions and are reported as such.
Government formation is reported CONDITIONALLY on an assumption set:
      incumbent_anchored : a government forms if some incumbent-anchored coalition has a majority
      student_anchored   : ... if some student-anchored coalition has a majority
      both / neither     : the joint outcomes, so nothing is hidden by an ordering assumption (who is invited first is not modelled)
"""
import numpy as np
import pandas as pd

TOKENS = ('@minority', '@all_except_incumbent', '@all_except_student')


def expand_members(members, list_keys, is_minority, incumbent_keys, student_key):
    """Members string 'a;b;@minority' -> boolean mask over list_keys. Unknown keys raise (never silently dropped)."""
    keys = list(list_keys)
    mask = np.zeros(len(keys), bool)
    for tok in [m.strip() for m in str(members).split(';') if m.strip()]:
        if tok == '@minority':
            mask |= np.asarray(is_minority, bool)
        elif tok == '@all_except_incumbent':
            mask |= ~np.isin(keys, list(incumbent_keys))
        elif tok == '@all_except_student':
            mask |= np.asarray(keys) != student_key
        elif tok in keys:
            mask[keys.index(tok)] = True
        else:
            raise KeyError(f'coalition member {tok!r} is neither a list key of the roster nor one of {TOKENS}')
    return mask


def evaluate(seats, list_keys, is_minority, coalitions, *, majority, incumbent_keys, student_key):
    """seats (n, L). Returns (per_coalition DataFrame, flags DataFrame (n, n_coalitions) of majority booleans, seat matrix)."""
    rows, flags, tot = [], {}, {}
    for c in coalitions.itertuples():
        m = expand_members(c.members, list_keys, is_minority, incumbent_keys, student_key)
        s = seats[:, m].sum(axis=1)
        anchor_ix = list(list_keys).index(c.anchor)
        tot[c.coalition_id] = s
        flags[c.coalition_id] = s >= majority
        rows.append(dict(coalition_id=c.coalition_id, coalition_name=c.coalition_name, assumption_set=c.plausibility_assumption_set,
                         plausibility=c.plausibility, n_member_lists=int(m.sum()),
                         p_majority=float(np.mean(s >= majority)), seats_p05=float(np.percentile(s, 5)),
                         seats_median=float(np.median(s)), seats_p95=float(np.percentile(s, 95)),
                         p_anchor_largest_list=float(np.mean(seats[:, anchor_ix] == seats.max(axis=1))),
                         status=c.status))
    return pd.DataFrame(rows), pd.DataFrame(flags), pd.DataFrame(tot)


def formation_table(flags, coalitions):
    """Conditional government-formation probabilities by assumption set (see module docstring)."""
    sets = {}
    for c in coalitions.itertuples():
        sets.setdefault(c.plausibility_assumption_set, []).append(c.coalition_id)
    any_inc = flags[sets.get('incumbent_anchored', [])].any(axis=1) if sets.get('incumbent_anchored') else pd.Series(False, index=flags.index)
    any_stu = flags[sets.get('student_anchored', [])].any(axis=1) if sets.get('student_anchored') else pd.Series(False, index=flags.index)
    any_math = flags.any(axis=1)
    out = pd.DataFrame([
        ('incumbent-anchored coalition has a majority', float(any_inc.mean())),
        ('student-anchored coalition has a majority', float(any_stu.mean())),
        ('only an incumbent-anchored coalition has a majority', float((any_inc & ~any_stu).mean())),
        ('only a student-anchored coalition has a majority', float((~any_inc & any_stu).mean())),
        ('both kinds have a majority (order of invitation not modelled)', float((any_inc & any_stu).mean())),
        ('neither kind has a majority among the listed coalitions', float((~any_inc & ~any_stu).mean())),
        ('any listed coalition (incl. mathematical-only) has a majority', float(any_math.mean())),
    ], columns=['event', 'probability'])
    return out
