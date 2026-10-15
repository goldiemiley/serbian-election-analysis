"""Pre-flight check, labelled SQL errors, and the external-import round trip with BigQuery-style dtypes."""
import pathlib

import pandas as pd
import pytest

import pipeline as PL
from backend import normalize_df
from harness import DuckBackend, load_package

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture()
def fresh(pkg_dir):
    con, _ = load_package(pkg_dir)
    return DuckBackend(con)


def test_preflight_passes_on_the_clean_package(fresh):
    assert PL.preflight(fresh, verbose=False) == []


def test_preflight_names_a_missing_table(fresh):
    fresh.con.execute('DROP TABLE territories')
    problems = PL.preflight(fresh, verbose=False)
    assert len(problems) == 1 and "'territories'" in problems[0] and 'Step 1' in problems[0]


def test_preflight_names_a_missing_column(fresh):
    fresh.con.execute('ALTER TABLE election_totals RENAME COLUMN geo_id TO geo_id_renamed')
    problems = PL.preflight(fresh, verbose=False)
    assert any("'election_totals'" in p and 'geo_id' in p for p in problems)


def test_preflight_flags_an_empty_table(fresh):
    fresh.con.execute('DELETE FROM paired_changes_13')
    assert any("'paired_changes_13'" in p and 'empty' in p for p in PL.preflight(fresh, verbose=False))


def test_sql_error_names_the_file(fresh, tmp_path):
    (tmp_path / 'stage9_99_broken.sql').write_text('CREATE OR REPLACE TABLE `{DS}.zz` AS SELECT nope FROM `{DS}.does_not_exist`')
    with pytest.raises(RuntimeError) as e:
        PL.run_sql_file(fresh, 'stage9_99_broken.sql', sql_dir=tmp_path)
    assert 'stage9_99_broken.sql' in str(e.value) and 'REJECTED' in str(e.value)


class _BigQueryStyle:
    """DuckDB behind the interface, handing results back the way the BigQuery client does (nullable Int64 / boolean, 'dbdate'),
    then through the project's own normalize_df, exactly as BigQueryBackend.query does."""

    def __init__(self, be):
        self.be, self.dataset_ref, self.name = be, be.dataset_ref, 'duckdb+bigquery-dtypes'

    def query(self, sql):
        df = self.be.query(sql)
        try:
            import db_dtypes  # noqa: F401
            have_dbdate = True
        except ImportError:
            have_dbdate = False
        for c in df.columns:
            if df[c].dtype == bool:
                df[c] = df[c].astype('boolean')
            elif pd.api.types.is_integer_dtype(df[c]):
                df[c] = df[c].astype('Int64')
            elif pd.api.types.is_datetime64_any_dtype(df[c]) and have_dbdate:
                df[c] = df[c].astype('dbdate')
        return normalize_df(df)

    def __getattr__(self, name):
        return getattr(self.be, name)


@pytest.mark.parametrize('table,fname', [('ext_polls', 'ext_polls_2026.csv'), ('ext_events', 'ext_events_2026.csv'),
                                         ('ext_markets', 'ext_markets_2026.csv'), ('ext_mandates', 'ext_mandates_2023.csv'),
                                         ('ext_local_election_registry', 'ext_local_election_registry.csv')])
def test_import_is_idempotent_with_bigquery_style_dtypes(fresh, table, fname):
    be = _BigQueryStyle(fresh)
    PL.load_config(be, verbose=False)
    path = ROOT / 'data_to_import' / fname
    n_file = len(pd.read_csv(path))
    n1 = PL.import_external_csv(be, table, path)
    n2 = PL.import_external_csv(be, table, path)           # second run reads the table back through BigQuery-style dtypes and upserts
    assert n1 == n2 == n_file
    back = be.query(f'SELECT COUNT(*) AS n FROM `{{DS}}.{table}`')
    assert int(back.n[0]) == n_file
