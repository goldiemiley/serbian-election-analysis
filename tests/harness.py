"""Local test harness (NOT BigQuery).

Loads the user's package into an in-memory DuckDB using the package's own BigQuery schema JSON files, then
translates the small BigQuery-only surface used by the project's SQL so the SAME SQL text can be executed
locally:
    `PROJECT.DATASET.table`                    -> table
    `PROJECT.DATASET.INFORMATION_SCHEMA.COLUMNS` -> a table with BigQuery type names
    DATE_DIFF(a, b, MONTH)                     -> date_diff('month', b, a)
    FLOAT64 / INT64 / STRING                   -> DOUBLE / BIGINT / VARCHAR
    SAFE_DIVIDE, COUNTIF                       -> macros

Passing here means "valid in DuckDB and logically correct on the real data". It does NOT prove BigQuery
accepts the text; see tests/test_sql_lint.py for the extra static checks used as a guard.
"""
import json
import pathlib
import re
import sys

import duckdb
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from config_schemas import CFG_TABLES, EXT_TABLES  # noqa: E402,F401
from coerce import coerce_df  # noqa: E402

BQ2PD = {'STRING': 'string', 'INT64': 'Int64', 'INTEGER': 'Int64', 'FLOAT64': 'float64', 'FLOAT': 'float64',
         'NUMERIC': 'float64', 'BOOL': 'boolean', 'BOOLEAN': 'boolean', 'DATE': 'string', 'TIMESTAMP': 'string'}
BQ2DUCK = {'STRING': 'VARCHAR', 'INT64': 'BIGINT', 'FLOAT64': 'DOUBLE', 'BOOL': 'BOOLEAN',
           'DATE': 'DATE', 'TIMESTAMP': 'TIMESTAMP'}
DUCK2BQ = {'VARCHAR': 'STRING', 'BIGINT': 'INT64', 'INTEGER': 'INT64', 'DOUBLE': 'FLOAT64',
           'BOOLEAN': 'BOOL', 'DATE': 'DATE', 'TIMESTAMP': 'TIMESTAMP'}


def _split_top_level(args):
    parts, depth, cur = [], 0, ''
    for ch in args:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts]


def _translate_date_diff(sql):
    """DATE_DIFF(d1, d2, PART) -> date_diff('part', d2, d1). Handles nested calls in the date arguments."""
    out, i = '', 0
    pat = re.compile(r'DATE_DIFF\s*\(')
    while True:
        m = pat.search(sql, i)
        if not m:
            return out + sql[i:]
        out += sql[i:m.start()]
        j, depth = m.end(), 1
        while depth:
            depth += {'(': 1, ')': -1}.get(sql[j], 0)
            j += 1
        a, b, part = _split_top_level(sql[m.end():j - 1])
        out += f"date_diff('{part.lower()}', {_translate_date_diff(b)}, {_translate_date_diff(a)})"
        i = j


def load_package(pkg_dir):
    """Load every CSV in the package using its BigQuery schema. Returns (connection, {table: fields})."""
    pkg = pathlib.Path(pkg_dir)
    con = duckdb.connect(':memory:')
    con.execute("CREATE MACRO safe_divide(a, b) AS a / NULLIF(b, 0)")
    con.execute("CREATE MACRO countif(c) AS sum(CASE WHEN c THEN 1 ELSE 0 END)")
    tables = {}
    for sch in sorted((pkg / 'schemas').glob('*.schema.json')):
        name = sch.name.replace('.schema.json', '')
        fields = json.load(open(sch))
        dtypes = {f['name']: BQ2PD.get(f['type'], 'string') for f in fields}
        df = pd.read_csv(pkg / f'{name}.csv', dtype=dtypes)
        for f in fields:
            if f['type'] == 'DATE':
                df[f['name']] = pd.to_datetime(df[f['name']]).dt.date
            elif f['type'] == 'TIMESTAMP':
                df[f['name']] = pd.to_datetime(df[f['name']], utc=True).dt.tz_localize(None)
        con.register('_t', df)
        con.execute(f'CREATE TABLE {name} AS SELECT * FROM _t')
        con.unregister('_t')
        tables[name] = fields
    return con, tables


def refresh_information_schema(con):
    rows = con.execute("SELECT table_name, column_name, data_type FROM duckdb_columns() "
                       "WHERE schema_name = 'main' AND table_name <> 'information_schema_columns_bq'").fetchall()
    df = pd.DataFrame([(t, c, DUCK2BQ.get('TIMESTAMP' if d.startswith('TIMESTAMP') else d.split('(')[0], d)) for t, c, d in rows],
                      columns=['table_name', 'column_name', 'data_type'])
    con.register('_ic', df)
    con.execute("CREATE OR REPLACE TABLE information_schema_columns_bq AS SELECT * FROM _ic")
    con.unregister('_ic')


def bq(sql, ds='PROJECT.DATASET'):
    """BigQuery text -> DuckDB text (see module docstring)."""
    s = sql.replace('{DS}', ds)
    s = re.sub(r'`' + re.escape(ds) + r'\.INFORMATION_SCHEMA\.COLUMNS`', 'information_schema_columns_bq', s)
    s = re.sub(r'`' + re.escape(ds) + r'\.([A-Za-z0-9_]+)`', r'\1', s)
    s = _translate_date_diff(s)
    s = re.sub(r'\bFLOAT64\b', 'DOUBLE', s)
    s = re.sub(r'\bINT64\b', 'BIGINT', s)
    s = re.sub(r'\bSTRING\b', 'VARCHAR', s)
    return s


class DuckBackend:
    """Implements the project's Backend interface on DuckDB (see src/backend.py for the BigQuery one)."""
    dataset_ref = 'PROJECT.DATASET'
    name = 'duckdb-standin'

    def __init__(self, con):
        self.con = con
        refresh_information_schema(con)

    def query(self, sql):
        return self.con.execute(bq(sql, self.dataset_ref)).df()

    def execute(self, sql):
        self.con.execute(bq(sql, self.dataset_ref))
        refresh_information_schema(self.con)

    def table_exists(self, table):
        return bool(self.con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = ? AND schema_name = 'main'", [table]).fetchone()[0])

    def create_empty_if_missing(self, table, cols):
        if not self.table_exists(table):
            self.con.execute(f"CREATE TABLE {table} (" + ", ".join(f"{c} {BQ2DUCK[t]}" for c, t in cols) + ")")
            refresh_information_schema(self.con)
            return True
        return False

    def replace_table_from_df(self, table, df, cols):
        df = coerce_df(df, cols)
        self.con.register('_u', df)
        self.con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _u")
        self.con.unregister('_u')
        refresh_information_schema(self.con)


def q(con, sql, **kw):
    return con.execute(bq(sql, **kw)).df()
