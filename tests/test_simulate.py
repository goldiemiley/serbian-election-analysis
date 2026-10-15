"""Engine invariants on the real package: closure, legal totals, reproducibility, common random numbers, municipal reconciliation."""
import copy

import numpy as np
import pytest

import simulate as SM

N = 3000


@pytest.fixture(scope='module')
def draws(model):
    return SM.draw_national(model, N)


def test_roster_is_consistent(model):
    assert len(set(model.keys)) == len(model.keys)
    assert set(model.minority_keys) == set(model.roster_map.list_key)
    assert model.polled[0] == model.P['poll_reference_list_key']
    assert not model.is_minority[:len(model.nonmin_keys)].any() and model.is_minority[len(model.nonmin_keys):].all()


def test_closure_votes_add_to_valid(draws):
    assert np.allclose(draws['votes_cont'].sum(axis=1), draws['valid'], rtol=1e-9)
    assert (draws['votes_cont'] >= 0).all()
    assert np.allclose(draws['poll_shares'].sum(axis=1), 1.0)


def test_turnout_within_user_range(model, draws):
    lo, hi = model.P['turnout_voters_low'], model.P['turnout_voters_high']
    assert draws['V'].min() >= lo and draws['V'].max() <= hi
    assert (draws['valid'] < draws['ballots']).all() and (draws['ballots'] <= draws['V'] * 1.001).all()


def test_seats_sum_to_total_and_follow_rules(model, draws):
    r = SM.seats_for(model, draws)
    assert (r['seats'].sum(axis=1) == model.P['seats_total']).all()
    # a non-minority list below the threshold never gets a seat
    nm = ~draws['is_minority']
    below = draws['votes'] < r['threshold_votes'][:, None]
    assert (r['seats'][below & nm[None, :]] == 0).all()


def test_reproducible_and_seed_sensitive(model):
    a = SM.draw_national(model, 500, seed=5)
    b = SM.draw_national(model, 500, seed=5)
    c = SM.draw_national(model, 500, seed=6)
    assert np.array_equal(a['votes'], b['votes']) and not np.array_equal(a['votes'], c['votes'])


def test_common_random_numbers_across_scenarios(model):
    base = SM.draw_national(model, 800, seed=9)
    sc = SM.Scenario(name='t', shift_log={model.targets[0]: 0.2})
    alt = SM.draw_national(model, 800, sc, seed=9)
    assert np.array_equal(base['V'], alt['V'])
    nm = len(model.nonmin_keys)
    assert np.array_equal(base['votes'][:, nm:], alt['votes'][:, nm:])          # minority block unaffected by a poll shift
    i = model.keys.index(model.targets[0])
    assert (alt['votes_cont'][:, i] > base['votes_cont'][:, i]).mean() > 0.95   # the shifted list gains in (almost) every draw


def test_event_mixture_requires_uncaptured_events(model):
    m2 = copy.copy(model)
    m2.events = model.events[model.events.event_date.fillna(model.events.report_date) <= model.last_poll_date]
    m2._build_events()
    assert not m2.mixture_active
    d = SM.draw_national(m2, 300, seed=1)
    assert (d['mixture_component'] == -1).all()
    assert model.mixture_active and len(model.uncaptured_events) > 0


def test_events_before_last_poll_are_not_triggers(model):
    assert (model.uncaptured_events.ref_date > model.last_poll_date).all()


def test_units_reconcile_with_national_draws(model, draws):
    for alpha in (0.0, 1.0):
        u = SM.simulate_units(model, draws, n_unit=120, alpha=alpha)
        c = u['checks']
        assert c['max_abs_unit_sum_error'] < 1e-6 and c['max_rel_list_total_error'] < 1e-9 and c['minority_clipped_fraction'] == 0.0
        assert (u['votes'] >= -1e-9).all()


def test_alpha_changes_geography_not_national_totals(model, draws):
    u0 = SM.simulate_units(model, draws, n_unit=100, alpha=0.0)
    u1 = SM.simulate_units(model, draws, n_unit=100, alpha=1.0)
    assert np.allclose(u0['votes'].sum(axis=1), u1['votes'].sum(axis=1))
    assert not np.allclose(u0['votes'], u1['votes'])


def test_coalition_flags_match_manual_sum(model, draws):
    r = SM.seats_for(model, draws)
    per, form, flags, tot = SM.coalition_results(model, draws, r)
    k = draws['keys']
    c01 = r['seats'][:, k.index('aleksandar_vucic_ujedinjena_srbija')]
    assert np.array_equal(tot['C01'].values, c01)
    assert np.array_equal(flags['C09'].values, tot['C09'].values >= model.P['majority_seats'])
    assert abs(form.set_index('event').probability['any listed coalition (incl. mathematical-only) has a majority'] - flags.any(axis=1).mean()) < 1e-12


class _NullableDtypeBackend:
    """Wraps the DuckDB stand-in but returns pandas NULLABLE dtypes, as the BigQuery client does (Int64, boolean, string, Float64)."""

    def __init__(self, be):
        self.be, self.dataset_ref, self.name = be, be.dataset_ref, 'duckdb+nullable-dtypes'

    def query(self, sql):
        import pandas as pd
        df = self.be.query(sql)
        for c in df.columns:
            if pd.api.types.is_bool_dtype(df[c]) and df[c].dtype == bool:
                df[c] = df[c].astype('boolean')
            elif pd.api.types.is_integer_dtype(df[c]):
                df[c] = df[c].astype('Int64')
            elif pd.api.types.is_float_dtype(df[c]):
                df[c] = df[c].astype('Float64')
            elif df[c].dtype == object and df[c].map(lambda v: isinstance(v, str) or v is None or (isinstance(v, float) and v != v)).all():
                df[c] = df[c].astype('string')
        return df


def test_model_is_dtype_agnostic(backend_geo_ext):
    """Same seed, same results whether the backend hands back numpy dtypes (DuckDB) or pandas nullable dtypes (BigQuery client)."""
    m1 = SM.Model(backend_geo_ext)
    m2 = SM.Model(_NullableDtypeBackend(backend_geo_ext))
    a, b = SM.draw_national(m1, 300, seed=3), SM.draw_national(m2, 300, seed=3)
    assert np.array_equal(a['votes'], b['votes'])
    ua, ub = SM.simulate_units(m1, a, n_unit=20), SM.simulate_units(m2, b, n_unit=20)
    assert np.allclose(ua['votes'], ub['votes'])
