"""Generates Step1_Load_Data_to_BigQuery.ipynb: loads the Serbia_Elections_BigQuery package into BigQuery from Colab.
Run: python3 -I tools/build_loader_notebook.py"""
import pathlib
import nbformat as nbf

import os
ROOT = pathlib.Path(__file__).resolve().parents[1]
TOKENS = {'@@VERSION@@': (ROOT / 'VERSION').read_text().strip()}
nb = nbf.v4.new_notebook()
C = []


def _tok(s):
    for k, v in TOKENS.items():
        s = s.replace(k, v)
    return s


def md(s):
    C.append(nbf.v4.new_markdown_cell(_tok(s).strip('\n')))


def code(s):
    C.append(nbf.v4.new_code_cell(_tok(s).strip('\n')))


md(r"""
# Step 1 — Load the Serbia elections data into BigQuery

This notebook copies the 12 tables of `Serbia_Elections_BigQuery.zip` into your own BigQuery dataset. It uses the same settings as the
`load_to_bigquery.sh` script in the package (CSV, header row skipped, UTF-8, the package's own schema files, zero bad records allowed).
It is safe to run twice: an existing table of the same name is replaced.

**You need:** a Google account, a Google Cloud project (its *Project ID*), and the file `Serbia_Elections_BigQuery.zip` on your computer.
""")

md("## 1. Fill in three values, then run the cell")
code(r"""
import os
import getpass
import re

def _private_setting(name, prompt):
    value = os.environ.get(name, '').strip()
    if not value:
        value = getpass.getpass(prompt).strip()
    if not value:
        raise ValueError('A connection setting is missing; enter it when prompted.')
    return value

# Enter identifiers at runtime; do not write them into a shared notebook.
_use_bigquery = os.environ.get('SERBIA_BACKEND', 'bigquery') == 'bigquery'
PROJECT_ID = _private_setting('SERBIA_PROJECT', 'Google Cloud project ID (hidden): ') if _use_bigquery else ''
DATASET = _private_setting('SERBIA_DATASET', 'BigQuery dataset ID (hidden): ') if _use_bigquery else ''
if _use_bigquery and (not re.fullmatch(r'[a-z][a-z0-9-]*[a-z0-9]', PROJECT_ID)
                      or not re.fullmatch(r'[A-Za-z0-9_]+', DATASET)):
    raise ValueError('Invalid identifier format. Use the Project ID and dataset ID shown in BigQuery.')
LOCATION   = "EU"                   # <- "EU" or "US". Use the same value in the forecast notebook (Step 2).
""")

md("## 2. Sign in and choose the zip file (a pop-up asks for your permission, then a file picker appears)")
code(r"""
import pathlib, zipfile
from google.colab import auth, files

auth.authenticate_user()                       # click Allow in the pop-up window
print("Choose Serbia_GitHub_Ready.zip (it contains the CSV data), or the original data ZIP:")
uploaded = files.upload()
zip_name = next(iter(uploaded))
dest = pathlib.Path("/content/serbia_package")
dest.mkdir(exist_ok=True)
zipfile.ZipFile(zip_name).extractall(dest)
hits = list(dest.rglob("election_totals.csv"))
if not hits:
    raise SystemExit("election_totals.csv not found in that zip. Did you choose Serbia_Elections_BigQuery.zip?")
PKG_DIR = hits[0].parent
print("package folder:", PKG_DIR)
""")

md("## 3. Load the 12 tables (takes about a minute)")
code(r"""
import csv, json
from google.cloud import bigquery

TABLES = ["territories", "polling_stations_2023", "election_totals", "list_votes", "context_series", "municipality_context_2022",
          "coalition_bridge", "model_panel_13", "paired_changes_13", "source_manifest", "quality_issues", "data_dictionary"]


def csv_data_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return sum(1 for _ in csv.reader(fh)) - 1          # minus the header row


def load_package(client, pkg_dir, project, dataset, location):
    pkg_dir = pathlib.Path(pkg_dir)
    ds = bigquery.Dataset(f"{project}.{dataset}")
    ds.location = location
    client.create_dataset(ds, exists_ok=True)
    rows = []
    for t in TABLES:
        with open(pkg_dir / "schemas" / f"{t}.schema.json", encoding="utf-8") as fh:
            schema = [bigquery.SchemaField.from_api_repr(f) for f in json.load(fh)]
        cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, encoding="UTF-8", field_delimiter=",",
            quote_character='"', max_bad_records=0, schema=schema, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        with open(pkg_dir / f"{t}.csv", "rb") as fh:
            job = client.load_table_from_file(fh, f"{project}.{dataset}.{t}", job_config=cfg)
        job.result()                                                   # waits; raises an error with the reason if the load fails
        n_bq = client.get_table(f"{project}.{dataset}.{t}").num_rows
        n_csv = csv_data_rows(pkg_dir / f"{t}.csv")
        status = "OK" if n_bq == n_csv else "ROW COUNT DIFFERS"
        rows.append((t, n_csv, n_bq, status))
        print(f"{status:>18}  {t:<28} rows in file: {n_csv:>7}   rows in BigQuery: {n_bq:>7}")
    return rows


client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
report = load_package(client, PKG_DIR, PROJECT_ID, DATASET, LOCATION)
bad = [r for r in report if r[3] != "OK"]
print()
print("ALL 12 TABLES LOADED. Next: open Step 2 (Serbia_Election_Forecast_2026.ipynb)." if not bad else f"PROBLEM with: {[r[0] for r in bad]}")
print("Data loaded into your selected BigQuery dataset.")
""")

md(r"""
## What the numbers should be
`territories` 236 · `polling_stations_2023` 8,273 · `election_totals` 247 · `list_votes` 8,723 · `context_series` 98,304 ·
`municipality_context_2022` 236 · `coalition_bridge` 37 · `model_panel_13` 26 · `paired_changes_13` 13 · `source_manifest` 24 ·
`quality_issues` 7 · `data_dictionary` 255 (counts from the package README).

## If something goes wrong
* **`Access Denied` / `403`** — your Google account lacks permission on that project. Use a project you own, or ask the owner for the roles
  *BigQuery Data Editor* and *BigQuery Job User*.
* **`Not found: Project …`** — `PROJECT_ID` is the project *name*, not the *ID*. The ID is shown in the project picker at the top of the Google Cloud console.
* **`Location … does not match`** — the dataset already exists in the other location. Change `LOCATION` to match, or change `DATASET` to a new name.
* **Anything else** — copy the last lines of the red error message and send them.
""")

nb["cells"] = C
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nb.metadata["colab"] = {"provenance": []}
out = ROOT / os.environ.get('NB_OUT', 'Step1_Load_Data_to_BigQuery.ipynb')
nbf.write(nb, out)
print("wrote", out, len(C), "cells")
