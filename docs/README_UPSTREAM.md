> Documentation supplied in the uploaded v3 package. Claims and settings below have not been reverified as part of privacy preparation. Relative links refer to the repository root. Use the root README for current file instructions.

# Serbian parliamentary election, 25 October 2026 — forecasting pipeline

A modular, parameterised, scenario-conditional forecast built on the `Serbia_Elections_BigQuery` package you loaded into BigQuery. It produces three linked forecasts from the same Monte Carlo draws:

1. **Votes and shares** per list, with turnout, municipal geography and uncertainty.
2. **Seats** under the Serbian electoral law (250 seats, 3% threshold, minority-list quotient ×1.35, largest-quotient method).
3. **Majorities and government formation**, conditional on explicit coalition-compatibility assumptions.

Read `ARCHITECTURE.md` first if you want to know *what* each stage does and *what it cannot do*.

## Read this before using the numbers

* **The SQL was developed on a DuckDB stand-in, then corrected from real BigQuery runs.** It was written and tested against the real package on DuckDB (with a small translation layer, `tests/harness.py`) and a static lint for known dialect differences. The first real BigQuery run (project `YOUR_PROJECT_ID`, EU) ran Stages 0–6 and rejected one statement, `stage7_01_minority_base.sql` (a sub-query inside a JOIN condition, which BigQuery does not allow and DuckDB does); that is fixed and a lint rule now blocks the construct. Every SQL file has now been accepted by BigQuery except the corrected one, which is verified to give identical output on the stand-in but has not itself been seen running on BigQuery. The Python stages after the SQL (simulation, scenarios, reports, charts) are tested on BigQuery-style data types but have not run against a live BigQuery project. If BigQuery rejects anything else, the error names the file.
* **The 4.3–4.4 million turnout range is your scenario assumption.** The model draws turnout uniformly between the two values. It is not a forecast.
* **Polls are few and heterogeneous.** `data_to_import` holds 5 polls from 3 pollsters, compiled from media reports, with dates, samples and bases partly missing. The pollster (house) effect is the largest uncertainty in the poll aggregate, and Evropska Srbija and Autentična desnica are covered by a single poll.
* **The headline race is close and depends on which pollster is trusted.** Dropping one pollster at a time moves the picture a lot (see `poll_leave_out::*` rows of `E_scenario_comparison.csv`): without Faktor plus the student list is clearly ahead, without CRTA the SNS-led list is. The aggregate sits near a tie because the pollsters disagree, and the intervals reflect that.
* **Turnout level hardly moves list shares.** Polls are treated as shares among those who vote, and nothing in the data says whom additional voters would support. The 4.3–4.4 million range therefore affects municipal turnout, the threshold denominators and minority vote counts, but not the national shares or seats. Differential mobilisation is represented only by the explicit `student_mobilization_up` scenario.
* **Transitions between parties are not estimated.** No poll cross-tabs are available. Realignment (for example SPS voters moving to the student list) enters as *named scenarios* with stated weights, and only if events dated after the last poll exist.
* **Most parameters are analyst choices, not estimates.** `config/cfg_parameters.csv` has 72 parameters, each with a `verification_status`; 9 are verified against a primary or multiple sources (election date, 250 seats, single national unit, 3% threshold, ×1.35 quotient, tie rule, fallback rule, RIK as decider of minority status, ODIHR July register). The rest are choices, priors, user assumptions or derived values and are labelled so.
* **The student list is not a minority list.** Minority status is the RIK's decision per list and is an input (`cfg_list_registry_2026`), based on media reports of those decisions.
* **Prediction markets are never an input.** They appear beside the model for validation only.

## Quick start (Google Colab + BigQuery)

1. **Load the data into BigQuery:** open `Step1_Load_Data_to_BigQuery.ipynb` in Colab, fill in your Project ID, a dataset name and a location, and run it (it asks you to choose `Serbia_Elections_BigQuery.zip`). It does the same as the package's `load_to_bigquery.sh` and checks the row counts. Skip this step if the 12 tables are already in BigQuery. Note the project, dataset and location.
2. In Colab, open `Serbia_Election_Forecast_2026.ipynb` (upload it from this folder). The setup cell asks for `serbia_forecast.zip` and unpacks it to `/content/serbia_forecast`.
3. Edit **only** the configuration cell: `PROJECT_ID`, `DATASET`, `BQ_LOCATION`. Leave `IMPORT_EXTERNAL = True` to load the compiled polls/events/market quotes/registry/mandates, or set `False` to supply your own (see `data_to_import/README.md`).
4. Run all. The notebook authenticates (`auth.authenticate_user()`), runs a **pre-flight check** (are the 7 package tables there, non-empty, with the columns the SQL reads? If not it says which and stops), builds `cfg_*` tables from `config/`, creates `ext_*` tables if missing, runs Stage 0 (stops if an error-level check fails), then each stage with its own markdown (Objective, Input, SQL, Explanation, Python, Validation, Output, Limitations).
5. Results are written to `forecast_outputs/` (and zipped for download). `WRITE_RESULTS_TO_BIGQUERY = True` also writes the main tables to the dataset as `out_*`.

The account needs permission to create and replace tables in the dataset. All tables are small (the largest is the unit × family panel, about 5,600 rows).

Runtime on a laptop-class CPU with the defaults (20,000 national draws, 400 unit draws, 25 scenarios): a few minutes.

## Offline dry run (no BigQuery)

```
pip install duckdb
SERBIA_BACKEND=duckdb_standin SERBIA_PKG_DIR=/path/to/extracted/Serbia_Elections_BigQuery \
SERBIA_OUT_DIR=out jupyter nbconvert --to notebook --execute Serbia_Election_Forecast_2026.ipynb
```

This is the same notebook on the DuckDB stand-in. `sample_outputs/` was produced this way.

## Folder map

| Path | Content |
|---|---|
| `Step1_Load_Data_to_BigQuery.ipynb` | Step 1: loads the package's 12 tables into your BigQuery dataset (generated by `tools/build_loader_notebook.py`; the loading logic was tested offline against the real package; it has been used to load the data in BigQuery) |
| `Serbia_Election_Forecast_2026.ipynb` | Step 2: the forecast notebook (generated by `tools/build_notebook.py`) |
| `ARCHITECTURE.md` | Specification of all 14 stages, missing inputs, identification limits |
| `RESEARCH_LEADS.md` | What to obtain from primary sources to improve each stage |
| `sql/` | One BigQuery statement per file (`CREATE OR REPLACE TABLE … AS SELECT`), `{DS}` = `project.dataset` |
| `src/` | Python: `pipeline.py` (run SQL, load config/ext), `backend.py`, `polls.py`, `turnout.py`, `voteshare.py`, `minority.py`, `electoral_law.py`, `allocation.py`, `coalitions.py`, `simulate.py`, `local_swing.py`, `backtest.py`, `report.py`, `charts.py` |
| `config/` | The assumptions as CSV: parameters, list roster 2026, family map, origin weights, minority roster, event scenarios, coalitions, local-list review, source register |
| `data_to_import/` | Manual external inputs and empty templates (see its README) |
| `reference/` | Your `analysis.sql` with the one reserved-word alias fixed (not part of the pipeline) |
| `tests/` | 183 tests (see below) |
| `sample_outputs/` | Outputs of one full run on the stand-in (all files listed in `OUTPUT_MANIFEST.csv`) |

## Changing assumptions

* **Edit `src/build_config.py`, then run `python3 -I src/build_config.py <package dir>`** — it regenerates `config/*.csv` and the empty templates, and it **overwrites** hand edits of the CSVs. If you prefer to edit the CSVs directly, do not re-run it.
* Each parameter has a `verification_status`. When you verify one against a primary source, change the status and `source`/`source_date`.
* The most consequential editable inputs: `cfg_list_family_map` (which family each historical list belongs to), `cfg_origin_weights` (whose geography a 2026 list follows), `cfg_list_registry_2026` (roster and minority status), `cfg_event_scenarios` (realignment scenarios and weights), `cfg_coalitions` (who can govern with whom), the turnout range, and the poll-model priors (`poll_*`).
* Nothing numeric about an election lives in Python or SQL. If you find a number there, it is a bug.

## Outputs

`OUTPUT_MANIFEST.csv` lists each file with its stage. Groups: **A** national votes, shares, seats, P(most votes) · **B** threshold probabilities and sensitivity, seat distributions, majority probabilities · **C** coalitions, conditional government formation, minority pivotality · **D** municipal turnout, list shares, local-election α grid, units driving national change · **E** scenario comparison, threshold sweeps, municipal-method sensitivity, poll timeline · **F** diagnostics and backtests · `fig_*.png` charts · `run_metadata.json`.

## Tests

```
python3 -I -m pytest tests -q --pkg /path/to/extracted/Serbia_Elections_BigQuery
```

The suite passes on Python 3.13 / pandas 3 and on Python 3.12 / pandas 2.2 / numpy 2.0 (close to Colab). The tests cover the electoral law (exact vs vectorised allocation, ties, reproduction of the 2023 allocation), vote-share downscaling, the minority module, poll-model invariance and recovery, simulation closure (list votes add up to valid votes; seats add up to 250), dtype handling of BigQuery's nullable types, backtests, reporting, a static SQL lint, and mutation tests that corrupt the data and require Stage 0 to notice. They need `pytest`, `duckdb`, `numpy`, `pandas`, `scipy`.

## Not covered

No behavioural model of coalition bargaining or the constitutional timetable; no individual-level survey microdata; no estimate of voter transitions; no use of census, earnings or employment series as predictors; no diaspora module (registrations are unknown); no treatment of fraud, disqualification or post-election legal disputes.
