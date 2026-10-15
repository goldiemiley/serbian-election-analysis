"""Run pipeline SQL stages on the DuckDB stand-in against the real package. Usage: python3 -I tests/run_stage.py PKG_DIR [file ...]"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'src'))
from harness import DuckBackend, load_package  # noqa: E402
from pipeline import load_config, run_sql_file  # noqa: E402

pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 60)
pd.set_option('display.max_rows', 300)
pd.set_option('display.max_colwidth', 90)

if __name__ == '__main__':
    con, _ = load_package(sys.argv[1])
    be = DuckBackend(con)
    load_config(be)
    for f in sys.argv[2:]:
        print(f'\n=== {f}')
        print(run_sql_file(be, f).to_string())
