import os
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'src'))

PKG = pathlib.Path(os.environ.get('SERBIA_PKG_DIR', 'Serbia_Elections_BigQuery'))   # or pass --pkg


def pytest_addoption(parser):
    parser.addoption('--pkg', default=str(PKG), help='directory with the extracted Serbia_Elections_BigQuery package')


@pytest.fixture(scope='session')
def pkg_dir(request):
    p = pathlib.Path(request.config.getoption('--pkg'))
    if not (p / 'schemas').exists():
        pytest.skip(f'package not found at {p}')
    return p


@pytest.fixture(scope='session')
def backend(pkg_dir):
    from harness import DuckBackend, load_package
    from pipeline import load_config, run_sql_file
    con, _ = load_package(pkg_dir)
    be = DuckBackend(con)
    load_config(be, verbose=False)
    for f in ('stage0_01_schema_contract.sql', 'stage0_02_integrity_checks.sql', 'stage0_03_election_inventory.sql',
              'stage0_04_municipality_status.sql', 'stage0_05_readiness_matrix.sql',
              'stage1_01_family_map_gate.sql', 'stage1_02_baseline_by_family.sql',
              'stage1_03_national_baseline_and_swing.sql', 'stage2_01_unit_turnout_panel.sql'):
        run_sql_file(be, f)
    return be


@pytest.fixture(scope='session')
def backend_geo(backend):
    """Adds the Stage 6.1 / 7.1 base tables on top of the Stage 0-2 backend."""
    from pipeline import run_sql_file
    for f in ('stage6_01_geography_base.sql', 'stage7_01_minority_base.sql'):
        run_sql_file(backend, f)
    return backend


@pytest.fixture(scope='session')
def params(backend):
    df = backend.query("SELECT param_key, param_value, value_type FROM `{DS}.cfg_parameters`")
    out = {}
    for r in df.itertuples():
        out[r.param_key] = float(r.param_value) if r.value_type in ('float', 'int') else r.param_value
    return out


@pytest.fixture(scope='session')
def backend_geo_ext(pkg_dir):
    """DuckDB stand-in with Stage 0-7 SQL run and the analyst-loaded external inputs from data_to_import/."""
    import contextlib
    import io
    from harness import DuckBackend, load_package
    from pipeline import ROOT, import_external_csv, load_config, run_sql_file
    con, _ = load_package(pkg_dir)
    be = DuckBackend(con)
    with contextlib.redirect_stdout(io.StringIO()):
        load_config(be, verbose=False)
        for t, f in [('ext_polls', 'ext_polls_2026.csv'), ('ext_events', 'ext_events_2026.csv'), ('ext_markets', 'ext_markets_2026.csv'),
                     ('ext_local_election_registry', 'ext_local_election_registry.csv'), ('ext_mandates', 'ext_mandates_2023.csv')]:
            import_external_csv(be, t, ROOT / 'data_to_import' / f)
    for f in ('stage0_01_schema_contract.sql', 'stage0_02_integrity_checks.sql', 'stage0_03_election_inventory.sql',
              'stage0_04_municipality_status.sql', 'stage0_05_readiness_matrix.sql', 'stage1_01_family_map_gate.sql',
              'stage1_02_baseline_by_family.sql', 'stage1_03_national_baseline_and_swing.sql', 'stage2_01_unit_turnout_panel.sql',
              'stage4_01_local_swing_panel.sql', 'stage5_01_poll_panel.sql', 'stage5_02_event_panel.sql', 'stage5_03_market_panel.sql',
              'stage6_01_geography_base.sql', 'stage7_01_minority_base.sql'):
        run_sql_file(be, f)
    return be


@pytest.fixture(scope='session')
def model(backend_geo_ext):
    import simulate as SM
    return SM.Model(backend_geo_ext)
