"""Pipeline helpers shared by the Colab notebook and the local tests.

A `backend` is any object with:
    dataset_ref                              'project.dataset' (BigQuery) or a placeholder (DuckDB stand-in)
    query(sql)         -> pandas.DataFrame
    execute(sql)       -> None
    table_exists(name) -> bool
    create_empty_if_missing(name, cols)
    replace_table_from_df(name, df, cols)
"""
import pathlib
import re

import pandas as pd

from config_schemas import CFG_TABLES, EXT_KEYS, EXT_TABLES
from coerce import coerce_df

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / 'config'
SQL_DIR = ROOT / 'sql'


def load_config(backend, config_dir=CONFIG_DIR, verbose=True):
    """Rebuild every cfg_* table from config/*.csv and create the ext_* tables EMPTY if they do not exist.
    ext_* tables are never overwritten: they hold external observations loaded by the analyst."""
    config_dir = pathlib.Path(config_dir)
    for name, cols in CFG_TABLES.items():
        df = pd.read_csv(config_dir / f'{name}.csv', dtype=str, keep_default_na=False)
        backend.replace_table_from_df(name, df, cols)
        if verbose:
            print(f'  cfg  {name:28s} {len(df):4d} rows (rebuilt from config/{name}.csv)')
    for name, cols in EXT_TABLES.items():
        created = backend.create_empty_if_missing(name, cols)
        if verbose:
            n = int(backend.query(f'SELECT COUNT(*) AS n FROM `{{DS}}.{name}`').n[0])
            print(f'  ext  {name:28s} {n:4d} rows ({"created empty" if created else "kept: analyst-loaded data"})')


def read_sql(name, sql_dir=SQL_DIR):
    return (pathlib.Path(sql_dir) / name).read_text()


def run_sql_file(backend, name, sql_dir=SQL_DIR):
    """Run one SQL file. A file holds exactly one statement (CREATE OR REPLACE TABLE ... AS SELECT, or a SELECT).

    If the database rejects the statement, the error names the file, so that the message can be copied and sent for diagnosis."""
    sql = read_sql(name, sql_dir)
    body = re.sub(r'--[^\n]*', '', sql).strip().rstrip(';')
    stripped = re.sub(r"'[^']*'", "''", body)            # ignore ';' inside string literals
    if ';' in stripped:
        raise ValueError(f'{name}: more than one statement; split the file')
    try:
        if re.match(r'(?is)\s*CREATE\s+(OR\s+REPLACE\s+)?(TABLE|VIEW)', body):
            backend.execute(sql)
            m = re.search(r'(?is)CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+`\{DS\}\.([A-Za-z0-9_]+)`', body)
            return backend.query(f'SELECT * FROM `{{DS}}.{m.group(1)}`')
        return backend.query(sql)
    except Exception as e:
        raise RuntimeError(f"\n\nSQL FILE '{name}' WAS REJECTED BY THE DATABASE.\n"
                           f"Copy this whole message (from 'SQL FILE' to the end) and send it.\n\n{type(e).__name__}: {e}") from e


def required_columns(config_dir=CONFIG_DIR):
    """{table: [columns]} that the pipeline's SQL reads from the package tables (config/cfg_required_columns.csv)."""
    df = pd.read_csv(pathlib.Path(config_dir) / 'cfg_required_columns.csv', dtype=str)
    return {t: list(g.column_name) for t, g in df.groupby('table_name', sort=False)}


def preflight(backend, config_dir=CONFIG_DIR, verbose=True):
    """Plain-language check BEFORE any SQL runs: do the package tables exist, are they non-empty, and do they carry the columns
    this pipeline reads? Returns a list of problems (empty = fine). Typed checks (column types) are done by Stage 0."""
    problems = []
    for table, cols in required_columns(config_dir).items():
        if not backend.table_exists(table):
            problems.append(f"Table '{table}' is not in the dataset. Run Step 1 (load the data) into THIS dataset first.")
            continue
        head = backend.query(f'SELECT * FROM `{{DS}}.{table}` LIMIT 1')
        missing = [c for c in cols if c not in head.columns]
        if missing:
            problems.append(f"Table '{table}' lacks column(s) {missing}. It was probably loaded with automatic schema detection or "
                            f"without its schema file. Reload it with Step 1.")
        elif len(head) == 0:
            problems.append(f"Table '{table}' is empty. Reload it with Step 1.")
        elif verbose:
            print(f'  ok  {table}')
    return problems


def import_external_csv(backend, table, path, replace_all=False):
    """Analyst-invoked import of an external observation file into an ext_* table.

    Upsert on the table's natural key (config_schemas.EXT_KEYS): a new row replaces an existing row with the same key.
    Pass replace_all=True to discard the table's current content first. Nothing is imported automatically."""
    cols = EXT_TABLES[table]
    new = coerce_df(pd.read_csv(path, dtype=str, keep_default_na=False), cols)
    backend.create_empty_if_missing(table, cols)
    if replace_all:
        merged = new
    else:
        old = coerce_df(backend.query(f'SELECT * FROM `{{DS}}.{table}`'), cols)
        keys = EXT_KEYS[table]
        old_keys = set(map(tuple, old[keys].astype(str).values.tolist()))
        new_keys = set(map(tuple, new[keys].astype(str).values.tolist()))
        keep = old[[tuple(r) not in new_keys for r in old[keys].astype(str).values.tolist()]]
        merged = pd.concat([keep, new], ignore_index=True)
        print(f'  {table}: {len(new)} rows imported ({len(new_keys & old_keys)} replaced existing keys), {len(merged)} rows now')
    backend.replace_table_from_df(table, merged, cols)
    return len(merged)
