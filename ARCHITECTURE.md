# Architecture — Serbian parliamentary election 2026 forecast

This document is the analytical specification. It says, for each of the 14 stages, what is estimated, from which data, by which code, how it is checked, what comes out and what it cannot do. Every claim of the form "X is verified" refers to the `verification_status` column of `config/cfg_parameters.csv` or of the `ext_*` file concerned.

Contents: 1 principles · 2 data flow · 3 stages 0–13 · 4 what is missing · 5 identification limits · 6 testing

---

## 1. Principles

| Principle | How it is enforced |
|---|---|
| **Three sequential forecasts** | Stage 1 (votes and shares) → Stage 2 (seats under the electoral law) → Stage 3 (majorities and governments, conditional on explicit assumption sets). All three are computed from the *same* Monte Carlo draws, so the seat and coalition probabilities carry the vote uncertainty through. |
| **No hard-coded observations** | Election results, municipality names, registers, polls, events, market quotes and mandates are read from BigQuery tables or from `ext_*` tables. Python and SQL contain no vote share, no municipality code and no poll value. The suite includes a lint test (`tests/test_sql_lint.py`) and a mutation test (`tests/test_mutations.py`) that corrupts the data and checks that Stage 0 notices. |
| **Assumptions are data, not code** | Legal parameters, priors, scenario definitions, the list roster, the list-to-family map, the geography weights and the coalition definitions live in `config/*.csv` and are loaded as `cfg_*` tables, each with a `verification_status`. Changing an assumption never requires editing code. |
| **External data are manual imports** | `ext_polls`, `ext_events`, `ext_markets`, `ext_mandates`, `ext_local_election_registry`, `ext_poll_transitions`, `ext_register_2026` are created empty if missing and are **never overwritten** by the pipeline. The files in `data_to_import/` are a compilation from secondary media reports and say so. |
| **No fabrication** | Where data are missing the stage reports the gap (`s0_readiness_matrix`) and the model falls back to a *named, parameterised* assumption or stops. It does not fill in. |
| **Neutral wording** | The student list and the SNS-led list are treated by the same code paths. The few asymmetries (which family a list's geography follows, which coalitions are listed) are rows in config tables that you can read and change. |
| **Reproducible** | One seed (`random_seed`) fans out into independent streams per component (turnout, polls, events, other lists, minority lists). Two scenarios with the same seed use common random numbers, so differences between them are due to the scenario, not to Monte Carlo noise. |

## 2. Data flow

```
BigQuery tables (your package)            config/*.csv  ->  cfg_* tables        data_to_import/*.csv -> ext_* tables
 election_totals, list_votes, territories,  (law, priors, roster, family map,       (polls, events, market quotes, mandates,
 paired_changes_13, polling stations ...     geography weights, coalitions)           local-election registry; templates for
        |                                            |                                 transitions and 2026 municipal registers)
        v                                            v                                          v
  Stage 0   s0_* checks, inventory, municipality status, readiness matrix  <------------------- (counts only)
  Stage 1   s1_* family map gate, baseline by family, national swing
  Stage 2   s2_unit_panel   (units x turnout/register baseline)
  Stage 4   s4_local_swing_panel
  Stage 5   s5_poll_panel, s5_event_panel, s5_market_panel
  Stage 6   s6_unit_geography_base          Stage 7   s7_minority_base
        \________________________ read into Python (src/simulate.py: Model) ________________________/
                                                  |
        Stage 3 turnout draws -> Stage 5 poll posterior + event mixture -> Stage 7 minority votes ->
        Stage 6/8 closure of valid votes (shares sum to 1) -> Stage 9 threshold + D'Hondt -> Stage 10 coalitions
                                                  |
        Stage 6 unit layer (municipalities) <- same national draws, calibrated so units add up to the national totals
                                                  |
        Stage 12 backtests + sensitivities      Stage 13 CSV A-F, charts, run_metadata.json
```

**Package tables read by the pipeline:** `election_totals`, `list_votes`, `territories`, `polling_stations_2023` (Stage 0 reconciliation), `paired_changes_13` (Stage 4 and readiness) and `data_dictionary` (schema contract). **Not read:** `model_panel_13`, `coalition_bridge`, `context_series`, `municipality_context_2022`, `quality_issues`, `source_manifest` — `model_panel_13` and `coalition_bridge` are the sources of `paired_changes_13` (per the package README), so Stage 4 reads the derived table. `municipality_context_2022` (census structure) and `context_series` (age, education, earnings, employment) are **deliberately not used as predictors**: with one national election carrying turnout totals and 12–13 local cases, the effect of such covariates on *change* between elections is not identified, and adding them would give apparent precision without evidence. They are available if a later version has data to estimate those effects (for example several elections with unit-level totals). `quality_issues` documents the known discrepancies (e.g. Aranđelovac 2026, four votes) that Stage 0 re-detects from the data.

SQL builds tables inside the dataset (`CREATE OR REPLACE TABLE ... AS SELECT`, one statement per file, `{DS}` placeholder replaced by `project.dataset`). Everything that needs simulation, optimisation, Kalman filtering or the exact seat allocation is Python, reading those tables.

## 3. Stages

Stage → files at a glance:

| Stage | SQL (`sql/`) | Python (`src/`) | Main outputs |
|---|---|---|---|
| 0 | `stage0_01 … 05` | `pipeline.py`, `backend.py` | `s0_schema_contract`, `s0_integrity_checks`, `s0_election_inventory`, `s0_municipality_status`, `s0_readiness_matrix` |
| 1 | `stage1_01 … 03` | – | `s1_family_map_gate`, baseline by family, national baseline and swing |
| 2 | `stage2_01` | `turnout.py` | `s2_unit_panel`, `D_municipal_turnout.csv` |
| 3 | – | `turnout.py`, `simulate.py` | turnout draws, ballots/valid per voter grid, `F_diag_turnout_methods_*` |
| 4 | `stage4_01` | `local_swing.py`, `simulate.py` | `s4_local_swing_panel`, `F_diag_local_elections.csv`, `D_municipal_alpha_grid_local_units.csv` |
| 5 | `stage5_01 … 03` | `polls.py`, `simulate.py` | `s5_*` panels, `F_diag_polls.csv`, `E_forecast_timeline_polls.csv`, market validation |
| 6 | `stage6_01` | `voteshare.py`, `simulate.py` | `s6_unit_geography_base`, `D_municipal_list_shares_alpha0.csv` |
| 7 | `stage7_01` | `minority.py` | `s7_minority_base`, minority vote draws |
| 8 | – | `simulate.py` | `A_national_votes_shares_seats.csv` |
| 9 | – | `electoral_law.py`, `allocation.py` | `B_*` |
| 10 | – | `coalitions.py` | `C_*` |
| 11 | – | `simulate.py`, `report.py` | all draws, `E_scenario_comparison.csv` |
| 12 | – | `backtest.py`, `report.py` | `F_backtest_*`, `E_threshold_sweeps.csv`, `E_municipal_geography_sensitivity.csv` |
| 13 | – | `report.py`, `charts.py` | `OUTPUT_MANIFEST.csv`, `fig_*.png`, `run_metadata.json` |

---

### Stage 0 — Inventory, source verification, query inspection, data-quality checks

**Objective.** Establish, on the user's own BigQuery copy, which data exist, which accounting identities hold, which municipalities had recent local elections, and what is missing for each later stage.

**Input.** `election_totals`, `list_votes`, `polling_stations_2023`, `territories`, `paired_changes_13` and the other package tables; `cfg_parameters`, `cfg_required_columns`, `ext_*`.

**SQL.** `stage0_01_schema_contract` (columns required by later stages exist, from `cfg_required_columns` and `INFORMATION_SCHEMA.COLUMNS`), `stage0_02_integrity_checks` (19 checks C01–C19: unique keys; disjoint leaf units add up to the national row; polling stations add up to the national row; list votes add up to valid votes; published shares match recomputed shares within tolerance; every local-election municipality is a leaf unit with a national baseline; elections with list votes but without totals; negative counts; at least one national election with totals), `stage0_03_election_inventory`, `stage0_04_municipality_status`, `stage0_05_readiness_matrix`.

**Explanation.** The package's data tables are the only source of electoral observations. The package's own `analysis.sql` (control totals, matched-pair panels, cohort descriptions on `model_panel_13` / `paired_changes_13`) is not part of the pipeline: it describes those panels, while Stage 0 re-derives the accounting identities from the base tables. It is preserved in `reference/analysis_original_fixed.sql` with one change: the alias `AS cast` is a reserved word in BigQuery and became `ballots_cast_total`. DuckDB rejected the original; whether BigQuery does was not tested here.
*Municipality status* is computed from data, not listed: a leaf unit's `local_status` is one of `recent_local_results_in_dataset`, `older_local_results_in_dataset`, `recent_local_registered_no_results`, `older_local_registered_no_results`, `none_in_dataset_or_registry`, `special_electorate`, using the dates in the dataset or in `ext_local_election_registry` and `recent_local_max_age_months` (18) against the target date. A unit with no local election in either source is labelled "coverage unknown", never "no local election"; a local election known from the registry but without results is kept as its own status instead of being ignored.
*Readiness matrix* converts the counts into a table: for each requirement (turnout totals for ≥2 national elections, polls, poll cross-tabs, municipal registers, verified family map, verified minority status, etc.) it states `OK / THIN / PROVISIONAL / MISSING`, the evidence, and the action needed.

**Python.** `pipeline.run_sql_file`, `load_config`, `import_external_csv`; `backend.BigQueryBackend` (real) and `tests/harness.DuckBackend` (offline stand-in).

**Validation.** Mutation tests change individual vote counts in the data and require the relevant check to fail. A published-data discrepancy (Aranđelovac 2026: list votes four below published valid ballots; C10, `info`) is kept as information, not repaired.

**Output.** The five `s0_*` tables. The notebook stops at the Stage 0 gate if any `error` check fails.

**Limitations.** Checks prove internal consistency of the package, not that the package equals the official record. All SQL was executed only on a DuckDB stand-in with a thin translation layer (`tests/harness.py`), plus a static lint for constructs that are known to differ in BigQuery. The first run in BigQuery may still reject a statement; the error message names the file.

---

### Stage 1 — Historical baseline and political-family harmonisation

**Objective.** Put the lists of different elections on a common footing so that "the SNS-led vote in 2023" and "the opposition vote in 2022" mean something comparable, and compute national and unit baselines.

**Input.** `list_votes`, `election_totals`, `cfg_list_family_map` (37 rows: list → family → bloc, with confidence and mapping status).

**SQL.** `stage1_01_family_map_gate` (every list of every national election has a map row; unreviewed rows are marked, not hidden), `stage1_02_baseline_by_family` (unit × family votes, shares of valid votes, votes per registered voter), `stage1_03_national_baseline_and_swing` (national family totals and 2022→2023 changes).

**Explanation.** A **family** is an analyst construct, not a party. Lists change names and composition between elections; the map is a proposal (`mapping_status = proposed`, 0 of 37 rows reviewed) with a stated basis for each row. All later geography depends on this map, so it is a visible input rather than buried logic; the readiness matrix reports it as PROVISIONAL until reviewed.

**Python.** None (SQL only).

**Validation.** The gate fails when a list lacks a map row (`test_removed_family_mapping_fails_the_gate`) and labels unreviewed rows PROVISIONAL (`test_unreviewed_mappings_are_labelled_provisional`); list votes of the units reconcile with the national list votes (C18).

**Output.** `s1_family_map_gate`, `s1_unit_family_votes`, `s1_national_family`, swing tables.

**Limitations.** The map is a judgement. Only two national elections (2022, 2023) have usable list votes by unit, and only 2023 has register/turnout totals (see §4).

---

### Stage 2 — Municipality-level turnout

**Objective.** A turnout panel for each of the disjoint leaf units (municipalities / city districts, plus the special electorates in the data), with the register, the baseline turnout rate, ballots per participant and the invalid-ballot rate.

**Input.** `election_totals` for the latest national election with totals, `territories`, `ext_register_2026` (optional), `cfg_parameters` (`register_total_2026`, `register_scaling_mode`, `special_electorate_mode`, `fixed_rate_region_ids`).

**SQL.** `stage2_01_unit_turnout_panel`.

**Explanation.** Municipal registers for 25 October 2026 are not in the data. If `ext_register_2026` has a row for a unit it is used; otherwise the baseline register is scaled by the national ratio (6,450,523 registered per the RIK report vs. the 2023 register). The scaling mode is a parameter; the panel records the `register_source` per unit. Special electorates (units without a residence-based register) keep their 2023 attendance rate; units listed in `fixed_rate_region_ids` (RS23, a very small unit with unstable rates) are held at their baseline rate and flagged `low_count_flag` when valid votes < 500.

**Python.** `turnout.estimate_unit_sd` gives an *empirical reference* for unit-level dispersion (robust SD of log-changes in valid votes 2022→2023); it mixes turnout change with register and boundary change, so it is a scale, not an estimate of turnout dispersion.

**Validation.** Unit sums reproduce the national totals of the baseline election exactly (C03); every unit has a baseline rate in [0, 1].

**Output.** `s2_unit_panel`; municipal turnout table `D_municipal_turnout.csv` (baseline and mean turnout, 95% interval, voters and valid votes, low-count flag, local status).

**Limitations.** One national election has turnout totals → the cross-sectional pattern of *change* in turnout is not identified from data. The model therefore moves units by a calibrated mechanism (Stage 3) and reports the spread between three mechanisms rather than choosing one.

---

### Stage 3 — National turnout calibration

**Objective.** Translate the user's scenario assumption (4.3–4.4 million voters) into unit-level turnout and into ballots cast and valid ballots, and carry the uncertainty to the threshold denominators.

**Input.** `turnout_voters_low = 4,300,000` and `turnout_voters_high = 4,400,000` (`verification_status = user_assumption`), the Stage 2 panel.

**SQL.** None.

**Python.** `turnout.calibrate` (root-finding so that unit voters add up to the target exactly), `turnout.simulate_calibrated` (idiosyncratic logit noise per unit, **re-calibrated in every draw** to that draw's national total), `turnout.ballots_and_valid`, `turnout.national_denominators`, `Model.turnout_grid`.

**Explanation.** The range is an *assumption*, not a forecast; the model draws national voters uniformly between the two values (`turnout_draw`), so a different range is a different scenario (`E_scenario_comparison.csv` includes low and high turnout cases outside the range, set by `turnout_sensitivity_offsets`). Three allocation mechanisms are implemented and reported (`logit_shift`, `abstainer_share`, `proportional`); the default is the logit shift because a uniform multiplier would push saturated units above 100%. The three candidate threshold denominators (voters who turned out, ballots cast, valid ballots) all follow from the same calibration, so the denominator ambiguity (Stage 9) needs no extra simulation.

**Validation.** Calibrated unit voters add up to the target (≤1e-6 relative); each mechanism stays within [0, 1]; feasibility errors are explicit (`target … is outside the feasible range`).

**Output.** Per-draw voters / ballots / valid; `F_diag_turnout_methods_by_region.csv`, `…_by_unit.csv`.

**Limitations.** Who the additional participants are (new voters, returning abstainers, mobilised opposition, diaspora) is not identified. Nothing in the data can say whether turnout in 2026 differs by region differently from 2023. A consequence worth stating: because polls are treated as shares among those who vote, the *level* of national turnout does not shift list shares or seats in this model. It changes municipal turnout, the three threshold denominators, the valid-vote pool and the minority lists' votes (through their turnout responsiveness φ). Differential mobilisation exists only as the named scenario `student_mobilization_up` (a stated shift in log-strength), which is a scenario and not an estimate. The scenario table's near-identical rows for `turnout_*` show this, they are not an error.

---

### Stage 4 — Recent local elections

**Objective.** Use municipalities with recent local elections as *information about geography and local mobilisation*, never as a substitute for parliamentary shares.

**Input.** `paired_changes_13` (local-election results paired with their 2023 baseline), `ext_local_election_registry`, `cfg_local_list_review` (65 local lists to classify, 0 verified), the baseline from Stage 1.

**SQL.** `stage4_01_local_swing_panel`: for each recent-local municipality, the change between the national baseline share of the families in the local lead coalition and the local lead list's share (outcome `proxy_change_pp_excl_joint_list`).

**Explanation.** Local lists are classified dynamically: an SNS-led or opposition-led local list is recognised through the `cfg_local_list_review` table (hints from list names are marked as hints; `verified_family` is empty until a human verifies it). The panel has 12 usable cases (THIN). With so few units, a regression with covariates, a difference-in-differences design or an event study is unidentified (no municipalities *without* a local election after the baseline in the same outcome), so the method is a hierarchical normal model with a closed-form Student-t posterior and predictive, plus a descriptive association with turnout change (leave-one-out).
The result enters the forecast only through a **transfer coefficient α ∈ {0, 0.5, 1}** (`local_transfer_alpha_values`): the share of the local deviation that is assumed to carry over to the parliamentary vote. α is **not identified** and is therefore a scenario; the default for headline results is α = 0. A **mobilisation shock** (mean 0, SD `local_mobilization_effect_sd` = 0.10 in log-odds) is added in recent-local units only.

**Python.** `local_swing.t_summary`, `predictive_draws`, `association`, `eb_random_effects`, `time_weight`; `simulate.simulate_units(alpha=…, mobilization=…)`.

**Validation.** Leave-one-out stability of the association is reported; with <3 cases the functions return missing values rather than a number.

**Output.** `F_diag_local_elections.csv`, `D_municipal_alpha_grid_local_units.csv`.

**Limitations.** Municipalities with local elections are not a random sample. Zaječar and Kosjerić (June 2025) are in the registry but their results are not in the package. The classification of local lists needs verified evidence.

---

### Stage 5 — Polls and political events

**Objective.** Convert polls into a probability distribution for list strengths at the election date, and handle realignment events (departures, joinings, endorsements, measured voter shifts) as *different* things.

**Input.** `ext_polls` (poll id, pollster, fieldwork dates, sample, base, mode, source URL, verification status), `ext_events` (event type from a controlled vocabulary), `ext_markets`, `cfg_event_scenarios`, `cfg_parameters`.

**SQL.** `stage5_01_poll_panel` (one row per poll × list; the share base is recorded; the poll date is the end of fieldwork, falling back to the publication date, which is flagged `poll_date_is_proxy` and used only to order polls in time), `stage5_02_event_panel`, `stage5_03_market_panel`.

**Explanation.**
*Poll model.* Polls are noisy measures of list *strength* and are not shares to be averaged. On additive log-ratios against a reference list, `y = θ(t) + house effect + sampling error`: θ follows a random walk (`poll_rw_sd_per_day`), each pollster has a house effect with SD `max(poll_house_sd_floor, between-house SD)`, sampling error is the multinomial delta-method covariance with a design effect (`poll_design_effect`), and a shared election-day polling miss (`poll_election_error_sd`) is added. A Kalman filter on the stacked state estimates it exactly. The random-walk, house and election shocks are independent shocks to *each list's* log strength, so the ratio coordinates have covariance `v(I + 11′)/2`; this makes the result independent of which list is the reference (tested). The between-house SD used as a default is pooled over all list pairs for the same reason.
*Identification limits (reported, not hidden).* With few polls the average house effect is not identified; the prior says the average pollster is unbiased. the `poll_leave_out::<pollster>` scenarios show the dependence on each pollster; lists covered by only one pollster are held at their full-sample posterior in those runs.
*Realignment.* `ext_events.event_type` separates `left_party`, `expelled`, `joined_organization`, `endorsed_list`, `list_withdrawn`, `list_proclaimed`, `new_party_announced`, `measured_voter_shift`, `other`. None of the first four is a measure of voter switching. A named scenario in `cfg_event_scenarios` (e.g. `sps_none`, `sps_moderate`, `sps_strong`: Beta-distributed share of the SPS-led list's polled strength moving to the student list) is **activated only if** `ext_events` contains an activation-type event for the trigger entity dated *after the last poll* (the polls cannot have captured it). The three SPS scenarios have equal baseline weights (1/3) — an analyst choice, shown on every output. Other scenarios (student mobilisation, SNS retention, opposition fragmentation/consolidation) are *sensitivity* scenarios added on top of the baseline.
*Markets.* Quotes are stored with platform, market question and resolution criteria and compared with model quantities in `F_diag_market_*`. `market_prices_are_inputs = false`: they are never an input, so there is no double counting with the polls they themselves reflect.

**Python.** `polls.prepare_log_ratios`, `kalman_polls`, `predict_at`, `aggregate`, `draws_to_shares`, `moment_house_sd`, `alr_cov`; `simulate.Model.poll_for`, `Model` event mixture.

**Validation.** `tests/test_polls.py`: invariance to the reference list; recovery of known shares from synthetic polls (empirical coverage of the 90% interval above 80%); house effects widen the uncertainty when pollsters disagree. Poll vs structural plausibility: `F_diag_poll_vs_structural.csv`, `F_diag_implied_flows*.csv`.

**Output.** `s5_poll_panel`, `s5_event_panel`, `s5_market_panel`, `F_diag_polls.csv`, `E_forecast_timeline_polls.csv` (poll-based strength over time with uncertainty band).

**Limitations.** The leave-one-pollster-out scenarios move the picture materially: dropping Faktor plus puts the student list clearly ahead, dropping CRTA puts the SNS-led list ahead (`E_scenario_comparison.csv`). The near-tie in the baseline is a consequence of averaging disagreeing pollsters, not evidence that voters are evenly split. 5 polls from 3 pollsters in `data_to_import`, taken from media reports with fieldwork details partly missing; two lists (Evropska Srbija, Autentična desnica) are covered by one poll. A poll cross-tab (`ext_poll_transitions`) is the only legitimate source for a voter-transition matrix: **the table exists and is checked by the readiness matrix, but no estimator reads it yet** (§4). Until then, transitions are *scenario assumptions* (Beta transfers) and `F_diag_implied_flows` is an accounting plausibility check, explicitly not a transition matrix.

---

### Stage 6 — Vote shares: SNS-led list, student list, SPS-led list, others

**Objective.** Vote shares of the polled lists (national level from Stage 5), distributed over municipalities in a way that adds up to the national totals.

**Input.** `s6_unit_geography_base` (2023 votes per registered voter by origin family), `cfg_origin_weights` (which families a 2026 list's geography follows), swing dispersion 2022→2023.

**SQL.** `stage6_01_geography_base`.

**Explanation.** **National level** (top-down): from the poll posterior, the event mixture and the closure (Stage 8). **Geography** (downscaling): unit weights `W[u,k] = Σ_o weight[k,o] × votes-per-registered[u,o]`; the unit votes of list k are `R_u × W[u,k] a_k / Σ_j W[u,j] a_j` with `a` fitted by iterative proportional fitting so that unit votes add up to the national total of every list (checked to 1e-12). An additive-swing alternative (`additive_fit`) is run beside it, and `E_municipal_geography_sensitivity.csv` reports how much municipal results depend on this choice. Unit noise is log-normal with SD taken from the observed 2022→2023 swing dispersion (capped at `swing_sd_cap`), at unit and region level, then re-calibrated so totals still hold. Mobilisation and α from Stage 4 enter here.

**Python.** `voteshare.build_unit_weights`, `rake`, `additive_fit`, `swing_dispersion`, `list_sigmas`; `simulate.simulate_units`.

**Validation.** Unit shares sum to 1 in each unit; unit votes sum to the national draw; the rake agrees with a scalar reference implementation; `tests/test_voteshare.py`, `tests/test_simulate.py`.

**Output.** `D_municipal_list_shares_alpha0.csv` (p10/p50/p90 by unit and list), `D_unit_contributions_to_national_change.csv`.

**Limitations.** Geography weights are an analyst mapping (`mapping_status`), not an estimate. A list with no precedent (the student list) inherits the geography of the families assigned to it; the backtests in Stage 12 show how well that works for a *known* 2023 case, not for 2026.

---

### Stage 7 — National-minority lists

**Objective.** Model minority lists separately because they enter the allocation below the 3% threshold and with a 1.35 multiplier.

**Input.** `cfg_list_registry_2026` (19 rows; `minority_status_reported`), `cfg_minority_roster_map` (list → group, analog family, role, unit pattern), `s7_minority_unit_base` (2023 votes of the analog families by unit).

**SQL.** `stage7_01_minority_base` → `s7_minority_unit_base`.

**Explanation.** Votes of each minority list are built **bottom-up** from the pools of its group in the baseline: pool × turnout responsiveness φ ~ U(`minority_turnout_responsiveness_low`, `…_high`) × a group-level log-normal shock (`minority_group_shock_sdlog`). New entrants (a minority list with no analog in 2023) get a Beta share of a pool they plausibly compete for (`minority_new_entrant_capture_*`); lists with no usable precedent are prior-only log-normal (`minority_prior_only_votes_*`). Whether a list is minority is **the RIK's per-list decision** (`minority_status_decider`); it is an input in `cfg_list_registry_2026`, never inferred, and `minority_status_sensitivity_keys` re-runs the allocation with the status of selected lists flipped. The student list is *not* a minority list.

**Python.** `minority.build_structures`, `minority.simulate_votes`.

**Validation.** Votes are non-negative integers; per-unit capacity is respected (water-filling); `tests/test_minority.py`.

**Output.** Minority vote draws, `C_minority_pivotality.csv`.

**Limitations.** Statuses and the roster rest on media reports of the RIK's decisions (all rows `verification_status = secondary_media_report__verify_against_RIK_collective_list_and_minority_decisions`). Three lists are new entrants without a 2023 analog (modelled from their group's pool) and one (Slovak) is prior-only, with no usable precedent.

---

### Stage 8 — National aggregation (closure)

**Objective.** Make the national result internally consistent: lists' votes must sum to valid votes in every draw.

**Explanation.** `valid` (Stage 3) = minority lists (Stage 7) + other non-minority lists (log-normal share, median `other_nonminority_share_median`, split by a Dirichlet) + polled lists (poll posterior shares × the *remaining* pool). Closure fails loudly (`ValueError`) if the minority and other lists exceed valid votes in any draw. Votes are rounded to integers before allocation.

**Python.** `simulate.draw_national`, `simulate.summarize_lists`.

**Validation.** Sum of list votes = valid votes in every draw (`tests/test_simulate.py`).

**Output.** `A_national_votes_shares_seats.csv` (median/mean, 80% and 95% intervals of votes, shares and seats; P(takes part in the allocation); P(at least one seat); **P(most votes)**).

**Limitations.** "Other non-minority lists" has a prior, not data. Lists polled only in aggregate cannot be separated.

---

### Stage 9 — Threshold and seat allocation

**Objective.** Apply the Serbian electoral law exactly: 250 seats, one national constituency, 3% threshold, minority lists admitted below the threshold with quotients ×1.35, largest-quotient (D'Hondt) allocation, last-seat tie to the list with more votes, fallback if no list reaches the threshold.

**Input.** Votes per list, minority flags, threshold denominators; parameters `seats_total`, `threshold_share`, `minority_quotient_multiplier`, `tie_break`, `fallback_if_no_list_reaches_threshold` — all `verified_primary`.

**Explanation.** Two points are not settled by the text and are *parameters with a sensitivity run*: `threshold_denominator` (which count is "voters who voted": turned-out voters (default), ballots cast, valid votes) and `minority_uplift_scope` (uplift for all minority lists, or only those below the threshold). Both are run from the same draws and reported in `B_threshold_sensitivity.csv`; `E_threshold_sweeps.csv` shifts one list's strength to show where it crosses the threshold (SPS-led list, Evropska Srbija, Autentična desnica by default). The text used is the 2020 consolidation; the 2022 law and the May 2026 amendments were not article-checked (source S02).

**Python.** `electoral_law.allocate_seats` / `allocate_seats_exact` (exact `Fraction` reference), `allocation.allocate_batch` (vectorised; falls back to the exact function on ties).

**Validation.** The batch allocator equals the exact one on every draw; the 2023 result reproduces the official 2023 mandate list (`ext_mandates_2023.csv`, 250 seats); seats sum to 250 in all draws (`tests/test_allocation.py`, `tests/test_electoral_law.py`).

**Output.** `B_seat_distribution_polled_lists.csv`, `B_seat_majority_probabilities.csv`, `B_threshold_sensitivity.csv`, `B_threshold_votes.csv`, `E_conditional_on_threshold.csv`.

**Limitations.** The legal parameters were checked against a secondary host and the RIK explainer, not against the Official Gazette (only 9 of 72 parameters are `verified`).

---

### Stage 10 — Coalition and government-formation probabilities

**Objective.** Probability of seat majorities and of government formation, *conditional on explicit assumptions about who can govern with whom*.

**Input.** `cfg_coalitions` (C01–C09: member lists with tokens `@minority`, `@all_except_incumbent`, `@all_except_student`; the assumption set under which the coalition is plausible; status), `incumbent_bloc_list_keys`, `student_list_key`.

**Explanation.** For each draw the seat total of every coalition is computed and compared with the majority (126, derived). Mathematical majority (`mathematical_only`) is reported separately from conditional formation: a coalition counts as *formed* only under its assumption set (`incumbent_anchored` or `student_anchored`). Both anchors are reported, together with "both" and "neither" outcomes; the order of invitation and bargaining are **not modelled**. `C_minority_pivotality.csv` shows the share of draws in which the minority lists' seats decide who has a majority.

**Python.** `coalitions.expand_members`, `evaluate`, `formation_table`; `simulate.coalition_results`, `kingmaker_table`.

**Validation.** Coalition seats = sum of members' seats; expansions are disjoint and complete; `tests/test_simulate.py`.

**Output.** `C_coalitions.csv`, `C_government_formation_conditional.csv`, `C_bloc_seat_quantiles.csv`, `C_minority_pivotality.csv`.

**Limitations.** Compatibility is an assumption, not an estimate; the SPS has governed with the SNS before, and that is the only precedent encoded. No model of post-election bargaining, early dissolution or the constitutional timetable.

---

### Stage 11 — Monte Carlo

**Objective.** Propagate all uncertainty jointly.

**Explanation.** Per draw: turnout (uniform in the user range), poll strengths (multivariate normal on log-ratios, so shares are compositional and correlated), event-scenario component and Beta transfers, other-list share and split, minority votes (φ, group shock, new-entrant capture), rounding; then threshold and allocation. A second layer draws municipal results for `n_unit_draws` of the national draws. Defaults: 20,000 national draws, 400 unit draws, seed 20261014. The **scenario set** (`report.scenario_set`, built entirely from `cfg_*` rows) reuses the same seed so scenarios differ only through their definition: `baseline`; `polls_only` (no realignment mixture); each realignment component alone (`event_sps_none`, `event_sps_moderate`, `event_sps_strong`); the sensitivity scenarios of `cfg_event_scenarios` (student mobilisation up, SNS retention up, opposition fragmentation, opposition consolidation); poll design effect and election-day error variants; leave-one-pollster-out; turnout shifted by `turnout_sensitivity_offsets` and fixed at the low or high end; minority responsiveness φ and new-entrant capture variants; minority status of selected lists flipped. Outcomes that are not scenarios but conditional views of the same draws are separate tables: threshold denominator and uplift scope (`B_threshold_sensitivity`), "SPS-led list below / above the threshold" (`E_conditional_on_threshold`), coalition assumption sets (`C_government_formation_conditional`), and the municipal-method and dispersion grid (`E_municipal_geography_sensitivity`).

**Python.** `simulate.draw_national`, `seats_for`, `simulate_units`, `report.run_scenarios`.

**Validation.** Seats sum to 250 in all draws; common-random-number tests; shares sum to 1; results are reproducible for a fixed seed.

**Output.** `E_scenario_comparison.csv`, the A/B/C tables for the baseline.

**Limitations.** Monte Carlo error is small relative to the structural uncertainty and is not reported separately. Intervals describe the *model*, conditional on the priors in `cfg_parameters`.

---

### Stage 12 — Backtesting, model comparison, sensitivity

**Objective.** Test what can be tested without leakage and say what cannot.

**What is backtested.** The geography module: predicting the 2023 unit results from the 2022 unit results *given the known 2023 national margins* — three downscaling methods (carry-forward, proportional swing, additive swing), a new-list-geography test (B2) and a leave-region-out dispersion check (B3). This uses no 2023 information that a real forecast would not have in the corresponding situation.

**What cannot be backtested.** National polls → result: the package has no past polls; turnout: there is one national election with totals; seats from votes: validated against the official 2023 mandates (accounting, not a forecast test). The report says so (`F_backtest_*`, readiness matrix, `fig_12_backtest.png`).

**Sensitivity.** Turnout range, poll design effect and election error, leave-one-pollster-out, geography method (proportional vs additive) and dispersion multipliers, minority responsiveness and capture, minority status, threshold denominator, uplift scope, local α, and the geography assumptions for new lists (backtest B2). Alternatives to the family map itself are not run; the map is flagged PROVISIONAL instead.

**Python.** `backtest.run` and its parts; `report.threshold_sweeps`, `diag_*`.

**Limitations.** One backtest transition (2022→2023). Metrics (RMSE of unit shares, bias, coverage) describe geography only.

---

### Stage 13 — Final forecast, visualisation, reporting

**Output tables (all in `OUTPUT_MANIFEST.csv`).**

| Group | Content |
|---|---|
| A | national votes and shares with intervals; P(most votes); seats |
| B | threshold probabilities; denominator and uplift-scope sensitivity; seat distributions; majority probabilities |
| C | coalition seat distributions; mathematical vs conditional formation; minority pivotality |
| D | municipal turnout; municipal list shares with 80% and 95% intervals and P(first); α grid for recent-local units; units driving national change |
| E | scenario comparison (turnout, mobilisation, retention, SPS defection/below 3%, consolidation/fragmentation, minority outcomes); threshold sweeps; municipal-method sensitivity; poll timeline |
| F | diagnostics and backtests; figures `fig_*.png`; `run_metadata.json` (seed, simulation sizes, turnout range, threshold settings, last poll date, whether the realignment mixture was active, pollsters, Python / platform / numpy / pandas versions) |

**Python.** `report.run_all`, `charts.make_all` (stable list colours from a neutral palette; the same list has the same colour in every figure). The notebook adds interactive Plotly charts (national shares, municipal scatter) when Plotly is installed, as it is in Colab.

**Limitations.** Forecasts are conditional on the assumptions printed with them. They are not predictions of what *will* happen and are not advice to any party.

---

## 4. What is missing (precise list)

| Missing input | Why it matters | Where it enters if supplied |
|---|---|---|
| Poll cross-tabs / transition tables (`ext_poll_transitions`) | Only legitimate source for 2022/2023 → 2026 voter transitions. **No estimator reads this table yet**; if data are supplied, the intended use is to replace the Beta transfer moments of the corresponding scenario. | Stage 5/6 |
| Municipal registers for 25 Oct 2026 (`ext_register_2026`) | Replaces national-ratio scaling | Stage 2 (already read by SQL) |
| Past polls paired with results | Needed to estimate house effects, design effects and the election-day error; today these are analyst priors | Stage 5/12 |
| Turnout totals for more than one national election | To identify how municipal turnout changes | Stage 2/3 |
| RIK decisions on minority status and the final collective list (primary) | Roster and statuses rest on media reports | Stage 7/9 |
| Verified family map (0/37 reviewed) and local-list classification (0/65) | Geography and local deviation depend on them | Stage 1/4 |
| Local-election results for Zaječar and Kosjerić (June 2025) and other municipalities | Larger sample for Stage 4 | Stage 4 |
| Diaspora registrations (about 111,000 are mentioned in an interview, unverified) | Possible additional electorate | Stage 3 |
| Primary pollster releases (fieldwork dates, bases, sample sizes) | Many metadata fields are missing | Stage 5 |
| Official Gazette text of the law as amended in 2022 and 2026 | The legal parameters are checked against a 2020 consolidation | Stage 9 |

## 5. Identification limits

* The **level** of the average pollster bias is not identified from polls alone. Intervals reflect only the assumed prior spread.
* Voter **transitions** are not identified; scenarios define them.
* Local-election effects on parliamentary voting (**α**) are not identified; α ∈ {0, 0.5, 1} is shown.
* The **geography of a new list** is an assumption (origin weights); the backtest quantifies method error on a known case.
* **Turnout composition** is not identified.
* **Coalition formation** is an assumption set, not a behavioural model.

## 6. Testing

`python3 -I -m pytest tests -q` → 183 tests: electoral law (exact vs vectorised, tie handling, the 2023 reproduction), allocation, vote-share downscaling (rake and additive fit: margins, positivity, batching), minority module, poll model (reference invariance, recovery), simulation (closure, seats = 250, common random numbers, dtype handling of BigQuery nullable types), backtest, report, static SQL lint (including a rule against sub-queries inside JOIN conditions, which BigQuery rejects), and mutation tests on the data. Tests need the extracted package (`--pkg path`). They run on a DuckDB stand-in; **they do not prove that BigQuery accepts the SQL** (a real BigQuery run found one statement the stand-in accepted and BigQuery did not; it was fixed and a lint rule added).
