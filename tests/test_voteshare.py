"""Stage 6/8 downscaling: rows and columns must reconcile exactly with the national targets."""
import numpy as np
import pandas as pd

import voteshare as VS
from pipeline import CONFIG_DIR


def _inputs(backend_geo):
    panel = backend_geo.query("SELECT * FROM `{DS}.s2_unit_panel` ORDER BY geo_id")
    geo = backend_geo.query("SELECT * FROM `{DS}.s6_unit_geography_base`")
    ow = pd.read_csv(CONFIG_DIR / 'cfg_origin_weights.csv', keep_default_na=False)
    keys = list(ow.list_key.unique())
    W = VS.build_unit_weights(geo, ow, keys, panel.geo_id.tolist())
    return panel, W, keys


def test_weights_positive_and_complete(backend_geo):
    panel, W, keys = _inputs(backend_geo)
    assert W.shape == (len(panel), len(keys)) and (W > 0).all()


def test_rake_reconciles_single_and_batch(backend_geo):
    panel, W, keys = _inputs(backend_geo)
    R = panel.valid_baseline.values.astype(float) * 0.93
    rng = np.random.default_rng(7)
    T = rng.dirichlet(np.ones(len(keys)) * 3) * R.sum()
    V = VS.rake(W, R, T)
    assert np.abs(V.sum(1) - R).max() < 1e-6 and np.abs(V.sum(0) - T).max() / T.min() < 1e-9
    Tb = rng.dirichlet(np.ones(len(keys)) * 3, size=30) * R.sum()
    Vb = VS.rake(W, R, Tb)
    assert Vb.shape == (30, len(R), len(keys))
    assert np.abs(Vb.sum(2) - R[None]).max() < 1e-6
    assert (np.abs(Vb.sum(1) - Tb) / Tb).max() < 1e-9
    assert (Vb >= 0).all()


def test_rake_rejects_inconsistent_targets(backend_geo):
    import pytest
    panel, W, keys = _inputs(backend_geo)
    R = panel.valid_baseline.values.astype(float)
    with pytest.raises(ValueError):
        VS.rake(W, R, np.ones(len(keys)))
