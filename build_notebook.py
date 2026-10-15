"""Generates Serbia_Election_Forecast_2026.ipynb (Colab-ready). Run: python3 -I tools/build_notebook.py"""
import pathlib
import nbformat as nbf

import os
ROOT = pathlib.Path(__file__).resolve().parents[1]
# Connection identifiers are entered at runtime. NB_OUT sets the output filename.
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
# Serbian parliamentary election 2026 — multi-stage, scenario-conditional forecast

**What this notebook does.** It reuses the tables you loaded into BigQuery (`election_totals`, `list_votes`, `territories`, `paired_changes_13`, …) and runs
the 14 stages of the brief: data checks → historical baseline → turnout → local elections → polls and events → vote shares by list → minority lists →
national aggregation → threshold and seats → coalitions → Monte Carlo → backtests → final outputs.

**How to read the results.**
* Every number is conditional on *stated* inputs. Observed data come from BigQuery. Assumptions live in `config/*.csv` (loaded as `cfg_*` tables) with a
  `verification_status`. External observations (polls, events, market quotes) are **manual imports** into `ext_*` tables and are marked as such.
* The 4.3–4.4 million turnout range is **your scenario assumption**, not an estimate.
* Polls are few, heterogeneous (different pollsters, bases, dates) and the aggregate is dominated by pollster differences; the intervals say so.
* The headline race depends on which pollster is trusted (see the `poll_leave_out::*` scenarios). National turnout level changes municipal turnout,
  thresholds and minority votes but not list shares: polls are shares among those who vote, and the data cannot say whom extra voters would support.
* Prediction-market quotes are **never** inputs. They are shown beside the model for validation only.
* The student list is **not** a minority list. Minority status of each list is the RIK's decision and is an input (`cfg_list_registry_2026`).
* The SQL was developed on a DuckDB stand-in and then corrected from real BigQuery runs; the Python stages after the SQL have not been seen on a live
  BigQuery project. Stage 0 below re-checks everything on *your* BigQuery copy; if a query is rejected, the error message names the file.

**Stage map.** 0 inventory/checks · 1 baseline & list families · 2 unit turnout · 3 national turnout calibration · 4 local elections · 5 polls & events ·
6 vote shares (SNS-led, student list, SPS, others) · 7 minority lists · 8 national aggregation · 9 threshold & seats · 10 coalitions · 11 Monte Carlo ·
12 backtest & sensitivity · 13 final outputs.
""")

md("## Configuration (edit this cell only)")
code(r"""
import os

# ---- your BigQuery dataset (the one the package was loaded into) --------------------------------------------------------
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
BQ_LOCATION = os.environ.get('SERBIA_LOCATION', 'EU')

# ---- manual external inputs --------------------------------------------------------------------------------------------
# True  : loads data_to_import/*.csv (polls, events, market quotes, local-election registry, 2023 official mandates) into the ext_* tables.
#         These files were compiled from secondary media reports and carry their own verification_status column: REVIEW THEM FIRST.
# False : leaves ext_* tables as they are (empty on a first run) and the forecast stops at Stage 5 with a message.
IMPORT_EXTERNAL = os.environ.get('SERBIA_IMPORT_EXTERNAL', '1') == '1'

# ---- run size (None = value of cfg_parameters: n_simulations / n_unit_draws) --------------------------------------------
N_SIMULATIONS = None
N_UNIT_DRAWS  = None

# ---- outputs ----------------------------------------------------------------------------------------------------------
OUT_DIR = os.environ.get('SERBIA_OUT_DIR', 'forecast_outputs')
WRITE_RESULTS_TO_BIGQUERY = False        # True: also writes the main output tables to the dataset as out_* (replaces them)

# ---- backend ------------------------------------------------------------------------------------------------------------
BACKEND = os.environ.get('SERBIA_BACKEND', 'bigquery')   # 'bigquery' (use this) | 'duckdb_standin' (offline dry run, needs the CSV package)
PKG_DIR = os.environ.get('SERBIA_PKG_DIR', '')           # only for 'duckdb_standin': folder with the extracted Serbia_Elections_BigQuery files
""")

md("## Setup: locate the project code, authenticate, connect")
code(r"""
import sys, pathlib, zipfile, subprocess

EXPECTED_VERSION = '@@VERSION@@'          # the project zip must carry this version, so an old copy left in Colab is never reused

def _version(p):
    try:
        return (p / 'VERSION').read_text().strip()
    except OSError:
        return None

def _find_root():
    for p in (pathlib.Path('/content/serbia_forecast'), pathlib.Path.cwd(), pathlib.Path.cwd().parent):
        if (p / 'src' / 'pipeline.py').exists() and _version(p) == EXPECTED_VERSION:
            return p
    # A GitHub source ZIP has a repository-name folder rather than serbia_forecast.
    content = pathlib.Path('/content')
    if content.exists():
        for p in sorted(content.iterdir()):
            if p.is_dir() and (p / 'src' / 'pipeline.py').exists() and _version(p) == EXPECTED_VERSION:
                return p
    return None

ROOT = _find_root()
if ROOT is None:                                  # Colab: upload the project zip once
    try:
        from google.colab import files
        print('Choose Serbia_GitHub_Ready.zip, or the ZIP downloaded from your repository:')
        up = files.upload()
        name = next(iter(up))
        zipfile.ZipFile(name).extractall('/content')
        ROOT = _find_root()
        if ROOT is None:
            raise SystemExit('The zip you chose is not version ' + EXPECTED_VERSION + ' (an older copy?). Choose Serbia_GitHub_Ready.zip and run this cell again.')
    except ImportError:
        raise SystemExit('Project folder not found. Open the notebook from inside the project folder.')
for _m in [m for m, mod in list(sys.modules.items()) if str(getattr(mod, '__file__', '') or '').startswith(str(ROOT))]:
    del sys.modules[_m]                            # forget project modules imported from an older copy in this session
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))          # harness for the offline dry run only
print('project root:', ROOT)

def _pip(*pkgs):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *pkgs], check=False)

try:
    import scipy, matplotlib, pandas, numpy          # Colab has these
except ImportError:
    _pip('scipy', 'matplotlib', 'pandas', 'numpy')
if BACKEND == 'bigquery':
    try:
        import google.cloud.bigquery, db_dtypes
    except ImportError:
        _pip('google-cloud-bigquery', 'db-dtypes', 'pyarrow')
""")
code(r"""
import pandas as pd, numpy as np
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 80)
from pipeline import load_config, run_sql_file, import_external_csv, ROOT as PROJECT_ROOT

if BACKEND == 'bigquery':
    from google.colab import auth
    auth.authenticate_user()
    from backend import BigQueryBackend
    be = BigQueryBackend(PROJECT_ID, DATASET, BQ_LOCATION)
elif BACKEND == 'duckdb_standin':
    from harness import DuckBackend, load_package
    con, _ = load_package(PKG_DIR)
    be = DuckBackend(con)
else:
    raise ValueError(BACKEND)
print('backend:', be.name, '| connection settings supplied privately')
""")

md("## Pre-flight check: is the data really in BigQuery?")
code(r"""
from pipeline import preflight
problems = preflight(be)
if problems:
    print('STOP. Fix this first:')
    for p_ in problems:
        print('  -', p_)
    raise SystemExit('Pre-flight failed: the data in this BigQuery dataset is not what the forecast needs (see above).')
print('Pre-flight passed: every package table is present with the columns the forecast reads.')
""")

md(r"""
## Stage 0 — Data inventory, source verification, query inspection, data-quality checks

**Objective.** Prove, on *your* copy, that the package's accounting identities hold and record every limitation as a check row instead of an assumption.
**Input.** `election_totals, list_votes, polling_stations_2023, territories, paired_changes_13, …` plus the `cfg_*` tables rebuilt from `config/`.
**SQL.** `sql/stage0_01…05`. **Output.** `s0_schema_contract, s0_integrity_checks, s0_election_inventory, s0_municipality_status, s0_readiness_matrix`.
**Limitations.** Checks prove internal consistency, not that the source is correct.
""")
code(r"""
print('Rebuilding cfg_* tables from config/*.csv and creating EMPTY ext_* tables where missing (ext_* data are never overwritten):')
load_config(be)
for f in ['stage0_01_schema_contract.sql', 'stage0_02_integrity_checks.sql', 'stage0_03_election_inventory.sql',
          'stage0_04_municipality_status.sql', 'stage0_05_readiness_matrix.sql']:
    print('\n===', f)
    out = run_sql_file(be, f)
    display(out if len(out) <= 60 else out.head(60))
""")
code(r"""
checks = be.query("SELECT * FROM `{DS}.s0_integrity_checks` ORDER BY check_id")
contract = be.query("SELECT status, COUNT(*) AS n FROM `{DS}.s0_schema_contract` GROUP BY status")
display(contract)
bad = checks[checks.status == 'FAIL']
bad_contract = contract[contract.status != 'OK']
if len(bad) or len(bad_contract):
    display(bad)
    raise SystemExit('Stage 0 gate FAILED: fix the data or the schema before forecasting (see the tables above).')
print('Stage 0 gate passed: no failed error-level check; WARN/INFO rows are limitations, read them:')
display(checks[checks.status.isin(['WARN', 'INFO'])][['check_id', 'status', 'description', 'n_violations', 'detail']])
""")

md(r"""
### External inputs (manual import) and the readiness matrix
The files in `data_to_import/` hold **externally sourced observations with provenance columns** (URL, retrieval date, verification status). Nothing is
imported unless `IMPORT_EXTERNAL=True` above. Imported rows are shown below so that nothing enters silently.
""")
code(r"""
import glob
EXT_FILES = {'ext_polls': 'ext_polls_2026.csv', 'ext_events': 'ext_events_2026.csv', 'ext_markets': 'ext_markets_2026.csv',
             'ext_local_election_registry': 'ext_local_election_registry.csv', 'ext_mandates': 'ext_mandates_2023.csv'}
if IMPORT_EXTERNAL:
    for table, fname in EXT_FILES.items():
        path = PROJECT_ROOT / 'data_to_import' / fname
        if path.exists():
            import_external_csv(be, table, path)
else:
    print('IMPORT_EXTERNAL=False: ext_* tables left untouched.')
for t in ['ext_polls', 'ext_events', 'ext_markets', 'ext_mandates', 'ext_local_election_registry', 'ext_poll_transitions', 'ext_register_2026']:
    n = int(be.query(f'SELECT COUNT(*) AS n FROM `{{DS}}.{t}`').n[0])
    print(f'  {t:30s} {n:4d} rows')
run_sql_file(be, 'stage0_05_readiness_matrix.sql')
ready = be.query("SELECT * FROM `{DS}.s0_readiness_matrix` ORDER BY 1")
display(ready)
""")
code(r"""
polls = be.query("SELECT poll_id, pollster, fieldwork_end, publication_date, sample_size, list_key, share, verification_status FROM `{DS}.ext_polls` ORDER BY fieldwork_end, poll_id, list_key")
display(polls)
if polls.empty:
    raise SystemExit('No polls in ext_polls: Stage 5 (and everything after it) needs at least one poll. Set IMPORT_EXTERNAL=True or insert your own rows.')
""")

md(r"""
## Stage 1 — Historical baseline and list harmonization
**Objective.** One comparable table of 2022 and 2023 results by *family* (successor lists grouped), unit by unit.
**Input.** `list_votes`, `election_totals`, `cfg_list_family_map` (37 proposed mappings, **unreviewed** → every output is labelled PROVISIONAL).
**Output.** `s1_family_map_gate, s1_national_family, s1_unit_family_votes`. **Limitations.** Mapping parties across elections is judgement; edit
`config/cfg_list_family_map.csv` and re-run to change it.
""")
code(r"""
for f in ['stage1_01_family_map_gate.sql', 'stage1_02_baseline_by_family.sql', 'stage1_03_national_baseline_and_swing.sql']:
    print('\n===', f)
    out = run_sql_file(be, f)
    display(out if len(out) <= 60 else out.head(60))
gate = be.query("SELECT * FROM `{DS}.s1_family_map_gate`")
assert not (gate.gate_status == 'FAIL').any(), 'family map gate failed: unmapped lists or orphan rows'
""")

md(r"""
## Stages 2–3 — Unit turnout and national turnout calibration
**Objective.** A turnout rate for each of the 192 disjoint units (190 municipalities/cities + abroad + institutions) consistent with a national
participation scenario. **Method.** Logit-shift calibration to the national voters total (your 4.3–4.4 M range, `cfg_parameters`), with two alternatives
(abstainer-share, proportional) shown for comparison; unit noise from the 2022→2023 change in valid votes; the register of 2026 is the 2023 register scaled
by the national ratio **unless** `ext_register_2026` provides municipal registers. **Limitations.** One national election with totals → the geography of
turnout *change* is not identified; the methods bracket it.
""")
code(r"""
run_sql_file(be, 'stage2_01_unit_turnout_panel.sql')
import report as RP, simulate as SM, turnout as TU
panel = be.query("SELECT * FROM `{DS}.s2_unit_panel` ORDER BY geo_id")
print('units:', len(panel), '| baseline register:', int(panel.registered_baseline.sum()), '| 2026 register used:', round(panel.registered_target.sum()),
      '| register source:', panel.register_source.value_counts().to_dict())
print('fixed-rate units (special electorates + regions in cfg fixed_rate_region_ids):', int(panel.fixed_rate.sum()))
""")

md(r"""
## Stage 4 — Recent municipal elections and local swing
**Objective.** Use what the 13 recent municipal elections can tell, without pretending it is more. **Dynamic classification.** `s0_municipality_status`
labels each municipality from the data (recent local results in dataset / registered but no results / none). Local results are **never substituted** for
parliamentary shares; the transfer coefficient α∈{0, 0.5, 1} that carries a municipality's local deviation into its parliamentary geography is **not
identified** and is therefore a scenario grid. DiD / event study are not identified (no comparison municipalities).
""")
code(r"""
run_sql_file(be, 'stage4_01_local_swing_panel.sql')
loc = be.query("SELECT * FROM `{DS}.s4_local_swing_panel` ORDER BY local_election_date, geo_id")
display(loc[['geo_id','municipality','local_status','local_election_date','lead_share_valid_2023','lead_share_valid_local','proxy_change_pp_excl_joint_list','turnout_change_pp','use_class']])
print(be.query("SELECT local_status, COUNT(*) AS n FROM `{DS}.s0_municipality_status` GROUP BY 1").to_string())
""")

md(r"""
## Stage 5 — Polls and political events
**Polls** are noisy measurements of list strength, aggregated on additive log-ratios with pollster ("house") effects, a random walk in time and a shared
election-day miss (Kalman filter; `src/polls.py`). **Events** (departures, expulsions, joinings, endorsements, measured voter shifts) are kept as
*different types*. A reported event whose effect the polls cannot yet reflect (dated **after the last poll**) triggers a **mixture of named
realignment scenarios** (`cfg_event_scenarios`) — never a single hard-coded transfer. **Markets** are validation-only.
""")
code(r"""
for f in ['stage5_01_poll_panel.sql', 'stage5_02_event_panel.sql', 'stage5_03_market_panel.sql']:
    print('\n===', f)
    out = run_sql_file(be, f)
    display(out if len(out) <= 40 else out.head(40))
""")

md(r"""
## Stages 6–7 — Geography base and minority lists
Vote *levels* come from the poll aggregate (Stage 5) and the minority module (Stage 7); Stage 6 only decides **where** each list's votes fall, from
`cfg_origin_weights` (which 2023 families a 2026 list's geography follows — a proposal, validated in Stage 12 on 2023 newcomers). Minority lists are modelled
one by one from their own 2023 votes (`cfg_minority_roster_map`), never merged into "others".
""")
code(r"""
for f in ['stage6_01_geography_base.sql', 'stage7_01_minority_base.sql']:
    out = run_sql_file(be, f)
    print(f, len(out), 'rows')
display(be.query("SELECT family, SUM(votes_baseline) AS votes_2023 FROM `{DS}.s7_minority_unit_base` GROUP BY 1 ORDER BY 1"))
""")

md("## Build the model and print every assumption that drives it")
code(r"""
model = SM.Model(be)
P = model.P
print('election date:', P['election_target_date'], '| seats:', P['seats_total'], '| threshold:', P['threshold_share'], 'of', P['threshold_denominator'],
      '| minority multiplier:', P['minority_quotient_multiplier'], '| uplift scope:', P['minority_uplift_scope'])
print('turnout scenario (user-specified):', f"{P['turnout_voters_low']:,.0f} - {P['turnout_voters_high']:,.0f} participating voters")
print('polls last dated:', model.last_poll_date.date(), '| days to election:', model.poll['days_to_election'], '| pollsters:', model.poll['houses'])
print('events after the last poll that trigger the realignment mixture:', len(model.uncaptured_events), '| mixture active:', model.mixture_active)
display(model.uncaptured_events[['event_id', 'event_type', 'actor_name', 'origin_entity', 'ref_date', 'confidence']] if len(model.uncaptured_events) else 'none')
prm = be.query("SELECT param_key, param_value, category, verification_status FROM `{DS}.cfg_parameters` ORDER BY category, param_key")
print('\nParameters by verification status:'); display(prm.groupby('verification_status').size().rename('n_parameters').to_frame())
display(prm[~prm.verification_status.str.startswith('verified')][['param_key', 'param_value', 'category', 'verification_status']])
""")

md(r"""
## Stages 8–13 — Simulation, seats, coalitions, scenarios, municipal layer, diagnostics, backtests, charts
`report.run_all` runs the Monte Carlo (`n_simulations` draws; correlated through the shared poll posterior and the single turnout draw; compositional by
construction; common random numbers across scenarios), applies the seat rules to **every draw** under the configured threshold base and, for sensitivity,
under all three bases × both uplift scopes, evaluates the named coalitions, and downscales a subset of the same draws to the 192 units.
""")
code(r"""
import time
t0 = time.time()
res = RP.run_all(model, OUT_DIR, n=N_SIMULATIONS, n_unit=N_UNIT_DRAWS, make_charts=True, verbose=True)
print(f'done in {time.time() - t0:.0f}s; files in {OUT_DIR}/ (see OUTPUT_MANIFEST.csv)')
display(pd.read_csv(f'{OUT_DIR}/OUTPUT_MANIFEST.csv'))
""")

md("## A–B. National votes, shares and seats")
code(r"""
tab = res['tab']
cols = ['list_name', 'is_minority', 'share_median', 'share_lo80', 'share_hi80', 'share_lo95', 'share_hi95', 'seats_median', 'seats_lo80', 'seats_hi80',
        'p_most_votes', 'p_takes_part_in_allocation', 'p_at_least_one_seat']
display(tab[cols].round(3))
from IPython.display import Image, display as idisplay
idisplay(Image(f'{OUT_DIR}/fig_A_national_shares.png')); idisplay(Image(f'{OUT_DIR}/fig_B_seat_distributions.png'))
print('Threshold sensitivity (same draws; base of the 3% rule x scope of the minority uplift):')
thr = pd.read_csv(f'{OUT_DIR}/B_threshold_sensitivity.csv')
display(thr[thr.list_key.isin(P.list('threshold_focus_list_keys'))].pivot_table(index=['threshold_denominator', 'uplift_scope'], columns='list_key', values='p_takes_part').round(3))
idisplay(Image(f'{OUT_DIR}/fig_B_threshold_sensitivity.png'))
""")

md("## C. Majority and coalition arithmetic (compatibility is an analyst assumption)")
code(r"""
display(res['coalitions'].round(3))
display(res['formation'].round(3))
display(pd.read_csv(f'{OUT_DIR}/C_minority_pivotality.csv').round(3))
idisplay(Image(f'{OUT_DIR}/fig_C_coalitions.png')); idisplay(Image(f'{OUT_DIR}/fig_F_outcome_probabilities.png'))
""")

md("## D. Municipal forecast (turnout, shares, local-election effects, units behind the national change)")
code(r"""
turn = pd.read_csv(f'{OUT_DIR}/D_municipal_turnout.csv', dtype={'geo_id': str})
display(turn.sort_values('registered_2026', ascending=False).head(15).round(3))
print('Units flagged low_count (shares rest on a handful of votes):', int(turn.low_count_flag.sum()))
display(pd.read_csv(f'{OUT_DIR}/D_municipal_alpha_grid_local_units.csv').round(3))
display(pd.read_csv(f'{OUT_DIR}/E_municipal_geography_sensitivity.csv').round(3))
idisplay(Image(f'{OUT_DIR}/fig_D_municipal.png')); idisplay(Image(f'{OUT_DIR}/fig_D_unit_contributions.png'))
""")

md("## E. Scenario comparison")
code(r"""
sc = pd.read_csv(f'{OUT_DIR}/E_scenario_comparison.csv')
short = lambda c: c.replace(P['poll_reference_list_key'], 'REF').replace(P['student_list_key'], 'STUDENT')
view = sc[['scenario'] + [c for c in sc.columns if c.startswith(('share_median__', 'p_takes_part__', 'p_incumbent', 'p_student', 'p_only', 'p_both'))]].copy()
view.columns = [short(c) for c in view.columns]
display(view.round(3))
display(pd.read_csv(f'{OUT_DIR}/E_conditional_on_threshold.csv').round(3))
display(pd.read_csv(f'{OUT_DIR}/E_threshold_sweeps.csv').round(3))
for f in ('fig_E_scenarios.png', 'fig_E_threshold_sweeps.png', 'fig_F_turnout_sensitivity.png', 'fig_F_forecast_timeline.png', 'fig_5_polls.png'):
    if (pathlib.Path(OUT_DIR) / f).exists():
        idisplay(Image(f'{OUT_DIR}/{f}'))
""")

md(r"""
## Stage 12 — Backtests and what could not be backtested
* **Possible here:** downscaling 2022→2023 given the true 2023 national margins; geography assumptions for lists that were *new* in 2023 (the student-list
  analogue); leave-one-region-out calibration of dispersion. No 2023 information enters a prediction except those margins (a test enforces this).
* **Not possible with the package:** the national polls→result stage (no past polls), turnout as a rate in 2022 (no 2022 register), a time-series backtest
  (two elections). `RESEARCH_LEADS.md` lists the data that would change this.
""")
code(r"""
bt = res['backtest']
display(bt['b1'].round(3)); display(bt['b2'].round(3)); display(bt['b3'].round(3))
idisplay(Image(f'{OUT_DIR}/fig_12_backtest.png'))
""")

md("## F. Diagnostics: poll panel, implied flows, markets (validation only), local-election evidence")
code(r"""
for f in ['F_diag_polls.csv', 'F_diag_poll_vs_structural.csv', 'F_diag_implied_flows.csv', 'F_diag_implied_flows_totals.csv',
          'F_diag_market_quotes.csv', 'F_diag_market_model_side.csv', 'F_diag_local_elections.csv']:
    p = pathlib.Path(OUT_DIR) / f
    if p.exists():
        print('\n##', f); display(pd.read_csv(p).round(3))
""")

md("## Interactive charts (plotly)")
code(r"""
try:
    import plotly.graph_objects as go
    d = tab[tab.share_median >= 0.008].sort_values('share_median')
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.share_median, y=d.list_name, mode='markers', name='median',
                             error_x=dict(type='data', symmetric=False, array=d.share_hi80 - d.share_median, arrayminus=d.share_median - d.share_lo80)))
    fig.update_layout(title='National shares of valid votes: median and 80% interval', xaxis_tickformat='.0%', height=120 + 36 * len(d))
    fig.show()
    mt = pd.read_csv(f'{OUT_DIR}/D_municipal_list_shares_alpha0.csv', dtype={'geo_id': str})
    a = mt[mt.list_key == P['poll_reference_list_key']].set_index('geo_id'); b = mt[mt.list_key == P['student_list_key']].set_index('geo_id')
    t = turn.set_index('geo_id').loc[a.index]
    sc2 = go.Figure(go.Scatter(x=a.share_mean, y=b.share_mean, mode='markers', text=t.geo_name + ' (' + t.region_id.fillna('special') + ')',
                               marker=dict(size=np.sqrt(t.registered_2026) / 6, opacity=0.6)))
    sc2.update_layout(title='Municipalities: expected share of the reference list (x) vs the student list (y)', xaxis_tickformat='.0%', yaxis_tickformat='.0%')
    sc2.show()
except ImportError:
    print('plotly not installed: static charts above are the same content.')
""")

md(r"""
## Save, download, update
Re-run after new information: add rows to `data_to_import/ext_polls_2026.csv` (or any `ext_*` CSV with the same columns), keep `IMPORT_EXTERNAL=True`, run again.
`E_forecast_timeline_polls.csv` shows how the poll-based forecast moved as each poll became public.
""")
code(r"""
import shutil
shutil.make_archive('forecast_outputs', 'zip', OUT_DIR)
if WRITE_RESULTS_TO_BIGQUERY and BACKEND == 'bigquery':
    for name in ['A_national_votes_shares_seats', 'C_coalitions', 'C_government_formation_conditional', 'E_scenario_comparison', 'D_municipal_turnout']:
        be.upload_df('out_' + name.lower(), pd.read_csv(f'{OUT_DIR}/{name}.csv'))
        print('written', 'out_' + name.lower())
try:
    from google.colab import files
    files.download('forecast_outputs.zip')
except ImportError:
    print('outputs in', OUT_DIR, 'and forecast_outputs.zip')
""")

nb['cells'] = C
nb['metadata'] = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                  'language_info': {'name': 'python'}, 'colab': {'provenance': []}}
out = ROOT / os.environ.get('NB_OUT', 'Serbia_Election_Forecast_2026.ipynb')
nbf.write(nb, out)
print('wrote', out, len(C), 'cells')
