"""Stage 7: minority module draws are non-negative, group pools respond to turnout as configured, structure sums to one."""
import numpy as np
import pandas as pd

import minority as MI
from pipeline import CONFIG_DIR


def _struct(backend_geo):
    panel = backend_geo.query("SELECT * FROM `{DS}.s2_unit_panel` ORDER BY geo_id")
    mb = backend_geo.query("SELECT * FROM `{DS}.s7_minority_unit_base`")
    rm = pd.read_csv(CONFIG_DIR / 'cfg_minority_roster_map.csv', keep_default_na=False)
    rm['analog_family'] = rm.analog_family.replace('', np.nan)
    return panel, MI.build_structures(rm, mb, panel.geo_id.tolist(), panel.region_id.values, panel.registered_baseline.values), rm


def test_patterns_sum_to_one_and_continuing_shares(backend_geo):
    panel, st, rm = _struct(backend_geo)
    assert np.allclose(st['patterns'].sum(axis=1), 1.0)
    for g, sub in rm.groupby('minority_group'):
        cont = sub.index[sub.role == 'continuing']
        if len(cont):
            assert abs(st['cont_share'][cont].sum() - 1) < 1e-12


def test_pool_follows_phi(backend_geo, params):
    panel, st, rm = _struct(backend_geo)
    rng = np.random.default_rng(5)
    up = MI.simulate_votes(st, 4000, np.full(4000, np.log(1.2)), params, rng, phi=1.0)[0]
    flat = MI.simulate_votes(st, 4000, np.full(4000, np.log(1.2)), params, rng, phi=0.0)[0]
    i = rm.index[rm.list_key == 'svm_pastor'][0]
    assert abs(np.median(up[:, i]) / np.median(flat[:, i]) - 1.2) < 0.03
    assert (up >= 0).all() and np.isfinite(up).all()


def test_no_votes_without_basis(backend_geo, params):
    """A list with role new_entrant in a group with no 2023 base draws nothing; prior-only lists follow their prior."""
    panel, st, rm = _struct(backend_geo)
    v = MI.simulate_votes(st, 2000, np.zeros(2000), params, np.random.default_rng(1))[0]
    slovak = rm.index[rm.minority_group == 'Slovak']
    assert (v[:, slovak[rm.role[slovak] == 'new_entrant']] == 0).all()
    po = rm.index[rm.role == 'prior_only']
    assert abs(np.median(v[:, po[0]]) / params['minority_prior_only_votes_median'] - 1) < 0.15
