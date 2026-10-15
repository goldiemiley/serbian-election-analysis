"""Mutation tests: corrupt a loaded copy of the package on purpose and require the Stage 0 / Stage 1 gates to FAIL.
A check that cannot fail proves nothing; these tests show each gate can."""
import pytest

from harness import DuckBackend, load_package
from pipeline import load_config, run_sql_file


@pytest.fixture()
def fresh(pkg_dir):
    con, _ = load_package(pkg_dir)
    be = DuckBackend(con)
    load_config(be, verbose=False)
    return be


def _checks(be):
    run_sql_file(be, 'stage0_02_integrity_checks.sql')
    return be.query("SELECT check_id, status, n_violations FROM `{DS}.s0_integrity_checks`").set_index('check_id')


def _leaf_row(be):
    return be.query("SELECT election_id, geo_id FROM election_totals WHERE is_2023_leaf = 1 AND election_id LIKE 'parliamentary%' LIMIT 1").iloc[0]


def test_pristine_package_passes_all_error_checks(fresh):
    c = _checks(fresh)
    assert c.loc[[i for i in c.index if i in ('C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C11', 'C12', 'C16', 'C17')], 'status'].eq('PASS').all()


def test_leaf_valid_ballots_corruption_is_caught(fresh):
    r = _leaf_row(fresh)
    fresh.con.execute(f"UPDATE election_totals SET valid_ballots_reported = valid_ballots_reported + 1 WHERE election_id = '{r.election_id}' AND geo_id = '{r.geo_id}'")
    assert _checks(fresh).loc['C03', 'status'] == 'FAIL'


def test_duplicate_key_is_caught(fresh):
    fresh.con.execute("INSERT INTO election_totals SELECT * FROM election_totals LIMIT 1")
    assert _checks(fresh).loc['C01', 'status'] == 'FAIL'


def test_list_votes_corruption_is_caught(fresh):
    fresh.con.execute("UPDATE list_votes SET votes = votes + 7 WHERE rowid IN (SELECT rowid FROM list_votes WHERE geo_level = 'national' AND election_id = 'parliamentary_2023' LIMIT 1)")
    c = _checks(fresh)
    assert 'FAIL' in (c.loc['C05', 'status'], c.loc['C06', 'status'])
    assert c.loc['C18', 'status'] == 'WARN'


def test_unit_list_votes_of_an_election_without_totals_are_checked(fresh):
    """The 2022 election has list votes but no totals rows, so C05/C06 cannot see it; C18 does."""
    fresh.con.execute("UPDATE list_votes SET votes = votes + 11 WHERE rowid IN (SELECT rowid FROM list_votes WHERE geo_level = 'national' AND election_id = 'parliamentary_2022' LIMIT 1)")
    c = _checks(fresh)
    assert c.loc['C18', 'status'] == 'WARN' and c.loc['C18', 'n_violations'] >= 1


def test_list_missing_from_units_is_an_error(fresh):
    fresh.con.execute("DELETE FROM list_votes WHERE geo_level != 'national' AND election_id = 'parliamentary_2023' AND list_id = (SELECT MIN(list_id) FROM list_votes WHERE election_id = 'parliamentary_2023')")
    assert _checks(fresh).loc['C19', 'status'] == 'FAIL'


def test_empty_national_rows_cannot_pass_silently(fresh):
    fresh.con.execute("DELETE FROM election_totals WHERE geo_level = 'national'")
    assert _checks(fresh).loc['C17', 'status'] == 'FAIL'


def test_unknown_geography_is_caught(fresh):
    fresh.con.execute("UPDATE election_totals SET geo_id = 'ZZZ' WHERE rowid IN (SELECT rowid FROM election_totals WHERE is_2023_leaf = 1 LIMIT 1)")
    assert _checks(fresh).loc['C11', 'status'] == 'FAIL'


def test_negative_counts_raise_a_warning(fresh):
    r = _leaf_row(fresh)
    fresh.con.execute(f"UPDATE election_totals SET invalid_ballots = -1 WHERE election_id = '{r.election_id}' AND geo_id = '{r.geo_id}'")
    assert _checks(fresh).loc['C15', 'status'] == 'WARN'


def test_removed_family_mapping_fails_the_gate(fresh):
    fresh.con.execute("DELETE FROM cfg_list_family_map WHERE rowid IN (SELECT rowid FROM cfg_list_family_map WHERE election_id LIKE 'parliamentary%' LIMIT 1)")
    for f in ('stage1_01_family_map_gate.sql',):
        run_sql_file(fresh, f)
    g = fresh.query("SELECT * FROM `{DS}.s1_family_map_gate`")
    assert (g.gate_status == 'FAIL').any(), g.to_string()


def test_unreviewed_mappings_are_labelled_provisional(fresh):
    run_sql_file(fresh, 'stage1_01_family_map_gate.sql')
    g = fresh.query("SELECT * FROM `{DS}.s1_family_map_gate`")
    assert set(g.gate_status) <= {'PROVISIONAL', 'PASS'} and (g.gate_status == 'PROVISIONAL').any()
