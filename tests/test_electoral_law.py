"""Seat-allocation module: reproduces the official 2023 distribution and agrees with an exact-arithmetic reference."""
import itertools

import numpy as np
import pandas as pd

import electoral_law as el

LAW = dict(seats=250, threshold_share=0.03, minority_multiplier=1.35)


def _national_2023(backend):
    return backend.query("""
        SELECT v.list_id, v.votes, m.is_minority_proposed AS is_minority
        FROM `{DS}.list_votes` AS v JOIN `{DS}.cfg_list_family_map` AS m
          ON m.election_id = v.election_id AND m.list_id = v.list_id
        WHERE v.election_id = 'parliamentary_2023' AND v.geo_level = 'national' ORDER BY v.list_id""")


def _official(pkg_root):
    df = pd.read_csv(pkg_root / 'data_to_import' / 'ext_mandates_2023.csv')
    return df.set_index('list_id').mandates_official


def test_reproduces_official_2023_allocation_under_every_denominator_and_uplift_scope(backend):
    root = __import__('pathlib').Path(__file__).resolve().parents[1]
    nat = _national_2023(backend)
    tot = backend.query("SELECT voters_turned_out, ballots_cast, valid_ballots_reported FROM `{DS}.election_totals` "
                        "WHERE election_id = 'parliamentary_2023' AND geo_level = 'national'").iloc[0]
    bases = {'voters_turned_out': tot.voters_turned_out, 'ballots_cast': tot.ballots_cast, 'valid_ballots': tot.valid_ballots_reported}
    official = _official(root).reindex(nat.list_id).values
    assert official.sum() == 250
    for (bname, base), scope in itertools.product(bases.items(), el.UPLIFT_SCOPES):
        res = el.allocate_seats(nat.votes.values, nat.is_minority.astype(bool).values, threshold_base=base, uplift_scope=scope, **LAW)
        assert res['seats'].sum() == 250
        assert (res['seats'] == official).all(), (bname, scope, dict(zip(nat.list_id, res['seats'])))


def test_threshold_votes_for_each_denominator_are_the_documented_values(backend):
    tot = backend.query("SELECT voters_turned_out, ballots_cast, valid_ballots_reported FROM `{DS}.election_totals` "
                        "WHERE election_id = 'parliamentary_2023' AND geo_level = 'national'").iloc[0]
    assert round(0.03 * tot.voters_turned_out) == 114622
    assert round(0.03 * tot.ballots_cast) == 114450
    assert round(0.03 * tot.valid_ballots_reported) == 111329


def test_float_and_exact_implementations_agree_on_random_inputs():
    rng = np.random.default_rng(12345)
    for _ in range(300):
        k = int(rng.integers(3, 16))
        votes = rng.integers(1_000, 2_000_000, size=k)
        mino = rng.random(k) < 0.4
        base = int(votes.sum() * rng.uniform(1.0, 1.15))
        for scope in el.UPLIFT_SCOPES:
            a = el.allocate_seats(votes, mino, threshold_base=base, uplift_scope=scope, **LAW)['seats']
            b = el.allocate_seats_exact(votes, mino, threshold_base=base, uplift_scope=scope, **LAW)
            assert list(a) == b
            assert a.sum() == 250


def test_tie_on_last_seat_goes_to_list_with_more_total_votes():
    votes = np.array([600, 300, 100])
    # quotients: A 600, 300 ... ; B 300 ... ; with 2 seats the 2nd seat is a tie between A(300) and B(300)
    res = el.allocate_seats(votes, np.zeros(3, bool), seats=2, threshold_share=0.0, threshold_base=1000, minority_multiplier=1.35)
    exact = el.allocate_seats_exact(votes, np.zeros(3, bool), seats=2, threshold_share=0.0, threshold_base=1000, minority_multiplier=1.35)
    assert list(res['seats']) == exact == [2, 0, 0]          # A has more total votes than B
    # with 3 seats there is no tie at the last seat: the three largest quotients are 600, 300, 300
    res3 = el.allocate_seats(votes, np.zeros(3, bool), seats=3, threshold_share=0.0, threshold_base=1000, minority_multiplier=1.35)
    assert list(res3['seats']) == [2, 1, 0]


def test_fallback_when_no_list_reaches_threshold():
    votes = np.array([100, 90, 80])
    res = el.allocate_seats(votes, np.zeros(3, bool), seats=10, threshold_share=0.5, threshold_base=1000, minority_multiplier=1.35)
    assert res['seats'].sum() == 10 and (res['seats'] > 0).all()
    res2 = el.allocate_seats(votes, np.zeros(3, bool), seats=10, threshold_share=0.5, threshold_base=1000,
                             minority_multiplier=1.35, fallback_if_none_reach=False)
    assert res2['seats'].sum() == 0


def test_minority_list_below_threshold_competes_with_uplift_and_non_minority_does_not():
    votes = np.array([1_000_000, 500_000, 20_000, 20_000])
    base = votes.sum()
    mino = np.array([False, False, True, False])
    res = el.allocate_seats(votes, mino, threshold_base=base, **LAW)
    assert res['seats'][2] > 0 and res['seats'][3] == 0
    # same votes, no uplift: the quotient 20_000*1.35 = 27_000 beats the 250th quotient only through the uplift
    res_plain = el.allocate_seats(votes, mino, threshold_base=base, **{**LAW, 'minority_multiplier': 1.0})
    assert res['seats'][2] >= res_plain['seats'][2]


def test_uplift_scope_changes_result_only_when_a_minority_list_clears_the_threshold():
    votes = np.array([1_500_000, 600_000, 200_000])      # third list is a minority list ABOVE 3%
    mino = np.array([False, False, True])
    base = votes.sum()
    a = el.allocate_seats(votes, mino, threshold_base=base, uplift_scope='all_minority', **LAW)['seats']
    b = el.allocate_seats(votes, mino, threshold_base=base, uplift_scope='below_threshold_only', **LAW)['seats']
    assert a[2] > b[2]
    votes2 = np.array([1_500_000, 600_000, 20_000])      # below 3%: identical
    a2 = el.allocate_seats(votes2, mino, threshold_base=votes2.sum(), uplift_scope='all_minority', **LAW)['seats']
    b2 = el.allocate_seats(votes2, mino, threshold_base=votes2.sum(), uplift_scope='below_threshold_only', **LAW)['seats']
    assert list(a2) == list(b2)


def test_threshold_is_inclusive_at_exactly_three_percent():
    votes = np.array([9_700, 300])
    res = el.allocate_seats(votes, np.zeros(2, bool), seats=250, threshold_share=0.03, threshold_base=10_000, minority_multiplier=1.35)
    assert res['eligible'].all()
    res2 = el.allocate_seats(np.array([9_701, 299]), np.zeros(2, bool), seats=250, threshold_share=0.03, threshold_base=10_000,
                             minority_multiplier=1.35)
    assert list(res2['eligible']) == [True, False]


def test_invalid_scope_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        el.allocate_seats([1, 2], [False, False], threshold_base=3, uplift_scope='nope', **LAW)
