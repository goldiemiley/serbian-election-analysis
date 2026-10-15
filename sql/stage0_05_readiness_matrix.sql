-- STAGE 0.5  Readiness matrix: for every later stage, what is available, what is provisional, what is missing.
-- Objective : make the "implement when data suffices, otherwise state what is missing" rule executable.
-- Input     : s0_* tables, cfg_*, ext_*, observed tables
-- Output    : {DS}.s0_readiness_matrix  (stage, requirement, status, evidence, action_if_not_ready)
-- status vocabulary:
--   READY         the data is in the dataset and passed its checks
--   PROVISIONAL   usable, but rests on an unreviewed mapping, a secondary source or an analyst choice
--   USER_INPUT    a scenario value you supplied
--   THIN          present but too small for the use stated (a descriptive use only)
--   MISSING       not in the dataset: the stage cannot run on real data until it is loaded
CREATE OR REPLACE TABLE `{DS}.s0_readiness_matrix` AS
WITH prm AS (
  SELECT
    MAX(CASE WHEN param_key = 'election_target_date' THEN CAST(param_value AS DATE) END) AS target_date,
    MAX(CASE WHEN param_key = 'min_national_elections_for_backtest' THEN CAST(param_value AS INT64) END) AS min_bt,
    MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
inv AS (SELECT * FROM `{DS}.s0_election_inventory`, prm WHERE election_type = 'national_parliamentary'),
cnt AS (
  SELECT
    (SELECT COUNT(*) FROM `{DS}.s0_integrity_checks` WHERE status = 'FAIL') AS n_fail,
    (SELECT COUNT(*) FROM `{DS}.s0_schema_contract` WHERE status != 'OK') AS n_schema_bad,
    (SELECT COUNT(*) FROM inv) AS n_nat,
    (SELECT COUNT(*) FROM inv WHERE has_totals AND has_list_votes) AS n_nat_full,
    (SELECT COUNT(*) FROM inv WHERE has_official_mandates) AS n_nat_mandates,
    (SELECT MAX(min_bt) FROM inv) AS min_bt,
    (SELECT COUNT(*) FROM `{DS}.cfg_list_family_map`) AS n_map,
    (SELECT COUNT(*) FROM `{DS}.cfg_list_family_map` WHERE mapping_status = 'reviewed') AS n_map_reviewed,
    (SELECT COUNT(*) FROM `{DS}.cfg_local_list_review` WHERE review_status = 'reviewed') AS n_local_reviewed,
    (SELECT COUNT(*) FROM `{DS}.cfg_local_list_review`) AS n_local,
    (SELECT COUNT(*) FROM `{DS}.cfg_list_registry_2026` WHERE status = 'proclaimed') AS n_lists_2026,
    (SELECT COUNT(*) FROM `{DS}.cfg_list_registry_2026` WHERE status = 'proclaimed' AND minority_status_reported = 'yes') AS n_min_2026,
    (SELECT COUNT(*) FROM `{DS}.cfg_parameters` WHERE verification_status LIKE 'verified%') AS n_param_verified,
    (SELECT COUNT(*) FROM `{DS}.cfg_parameters`) AS n_param,
    (SELECT COUNT(*) FROM `{DS}.paired_changes_13` WHERE eligible_for_default_model = 1) AS n_pairs,
    (SELECT COUNT(*) FROM `{DS}.ext_polls`, prm WHERE fieldwork_end <= prm.target_date) AS n_polls,
    (SELECT COUNT(DISTINCT poll_id) FROM `{DS}.ext_polls`) AS n_polls_distinct,
    (SELECT COUNT(*) FROM `{DS}.ext_poll_transitions`) AS n_trans,
    (SELECT COUNT(*) FROM `{DS}.ext_events`) AS n_events,
    (SELECT COUNT(*) FROM `{DS}.ext_markets`) AS n_markets,
    (SELECT COUNT(*) FROM `{DS}.ext_mandates`) AS n_ext_mandates,
    (SELECT COUNT(*) FROM `{DS}.ext_register_2026`) AS n_reg_unit,
    (SELECT COUNT(*) FROM `{DS}.ext_local_election_registry`) AS n_local_registry,
    (SELECT COUNT(*) FROM `{DS}.cfg_parameters` WHERE param_key IN ('turnout_voters_low', 'turnout_voters_high')) AS n_turnout_params,
    (SELECT COUNT(*) FROM `{DS}.s0_municipality_status` WHERE local_status = 'recent_local_results_in_dataset') AS n_recent_local
)
SELECT 0 AS stage, 'Source tables load, columns and types match the package dictionary' AS requirement,
  CASE WHEN n_schema_bad = 0 THEN 'READY' ELSE 'MISSING' END AS status,
  CONCAT(CAST(n_schema_bad AS STRING), ' schema contract exceptions') AS evidence,
  'Reload the package with its schemas/*.schema.json' AS action_if_not_ready
FROM cnt
UNION ALL
SELECT 0, 'Accounting identities (leaf units, stations, list sums) hold',
  CASE WHEN n_fail = 0 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_fail AS STRING), ' failed error-level checks; see s0_integrity_checks'),
  'Fix the failing check before any model is run'
FROM cnt
UNION ALL
SELECT 1, 'National elections with totals AND list votes (baseline)',
  CASE WHEN n_nat_full >= 1 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_nat_full AS STRING), ' national elections with totals and list votes; ',
         CAST(n_nat - n_nat_full AS STRING), ' with list votes only'),
  'Load totals and list votes for the baseline election'
FROM cnt
UNION ALL
SELECT 1, 'List-family map reviewed by an analyst',
  CASE WHEN n_map > 0 AND n_map_reviewed = n_map THEN 'READY'
       WHEN n_map > 0 THEN 'PROVISIONAL' ELSE 'MISSING' END,
  CONCAT(CAST(n_map_reviewed AS STRING), ' of ', CAST(n_map AS STRING), ' mappings reviewed (rest are proposed, unreviewed)'),
  'Review config/cfg_list_family_map.csv and set mapping_status = reviewed'
FROM cnt
UNION ALL
SELECT 2, 'Municipal register for the target election',
  CASE WHEN n_reg_unit > 0 THEN 'READY' ELSE 'PROVISIONAL' END,
  CASE WHEN n_reg_unit > 0 THEN CONCAT(CAST(n_reg_unit AS STRING), ' unit registers in ext_register_2026')
       ELSE 'only the national total is available; 2023 unit registers are scaled by the national ratio' END,
  'Load municipal registers for the election date into ext_register_2026'
FROM cnt
UNION ALL
SELECT 3, 'National turnout scenario (participating voters)',
  CASE WHEN n_turnout_params = 2 THEN 'USER_INPUT' ELSE 'MISSING' END,
  CONCAT(CAST(n_turnout_params AS STRING), ' of 2 turnout bounds in cfg_parameters (user assumption, not a forecast)'),
  'Set turnout_voters_low and turnout_voters_high in config/cfg_parameters.csv'
FROM cnt
UNION ALL
SELECT 2, 'Turnout totals for more than one national election (turnout dynamics)',
  CASE WHEN n_nat_full >= 3 THEN 'READY' WHEN n_nat_full = 2 THEN 'THIN' ELSE 'MISSING' END,
  CONCAT(CAST(n_nat_full AS STRING), ' national elections with turnout totals'),
  'Add turnout totals for earlier national elections (2022 has list votes only)'
FROM cnt
UNION ALL
SELECT 4, 'Local-election cases for the municipal swing model',
  CASE WHEN n_pairs >= 30 THEN 'READY' WHEN n_pairs > 0 THEN 'THIN' ELSE 'MISSING' END,
  CONCAT(CAST(n_pairs AS STRING), ' eligible matched local/national pairs; lead-list shares only (not party shares)'),
  'Extend the local-election table; keep a registry in ext_local_election_registry'
FROM cnt
UNION ALL
SELECT 4, 'Verified classification of local-election lists (see cfg_local_list_review)',
  CASE WHEN n_local > 0 AND n_local_reviewed = n_local THEN 'READY' WHEN n_local > 0 THEN 'PROVISIONAL' ELSE 'MISSING' END,
  CONCAT(CAST(n_local_reviewed AS STRING), ' of ', CAST(n_local AS STRING), ' local lists reviewed'),
  'Review config/cfg_local_list_review.csv with primary sources'
FROM cnt
UNION ALL
SELECT 5, 'Polls with fieldwork dates, sample sizes and methods',
  CASE WHEN n_polls > 0 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_polls AS STRING), ' poll-list rows in ext_polls on or before the election date'),
  'Load published polls into ext_polls (header-only templates in data_to_import/templates)'
FROM cnt
UNION ALL
SELECT 6, 'Poll cross-tabs (previous vote by current intention) for the voter-transition model',
  CASE WHEN n_trans > 0 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_trans AS STRING), ' rows in ext_poll_transitions'),
  'Load published transition tables into ext_poll_transitions; without them transitions are scenario assumptions only'
FROM cnt
UNION ALL
SELECT 5, 'Dated event log (departures, expulsions, joinings, endorsements)',
  CASE WHEN n_events > 0 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_events AS STRING), ' rows in ext_events'),
  'Load events into ext_events with distinct event types; leads are in cfg_source_register'
FROM cnt
UNION ALL
SELECT 6, 'Roster of lists on the 2026 ballot',
  CASE WHEN n_lists_2026 > 0 THEN 'PROVISIONAL' ELSE 'MISSING' END,
  CONCAT(CAST(n_lists_2026 AS STRING), ' proclaimed lists (secondary sources)'),
  'Verify against the RIK collective list'
FROM cnt
UNION ALL
SELECT 7, 'Minority-list status for 2026 lists (decided by the RIK per list)',
  CASE WHEN n_min_2026 > 0 THEN 'PROVISIONAL' ELSE 'MISSING' END,
  CONCAT(CAST(n_min_2026 AS STRING), ' lists reported as minority lists (secondary sources)'),
  'Verify against the RIK minority-status decisions'
FROM cnt
UNION ALL
SELECT 5, 'Prediction-market snapshots with timestamps (signal and validation benchmark, never vote shares)',
  CASE WHEN n_markets > 0 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_markets AS STRING), ' rows in ext_markets'),
  'Capture snapshots from the platform into ext_markets; use them for validation only'
FROM cnt
UNION ALL
SELECT 9, 'Legal parameters with source and verification status',
  CASE WHEN n_param_verified >= 1 THEN 'PROVISIONAL' ELSE 'MISSING' END,
  CONCAT(CAST(n_param_verified AS STRING), ' of ', CAST(n_param AS STRING),
         ' parameters verified against a primary source; see cfg_parameters.verification_status'),
  'Verify the threshold denominator and uplift scope against the current law and RIK practice'
FROM cnt
UNION ALL
SELECT 9, 'Official mandates to validate the allocation module',
  CASE WHEN n_ext_mandates > 0 THEN 'READY' ELSE 'MISSING' END,
  CONCAT(CAST(n_ext_mandates AS STRING), ' rows in ext_mandates; list_votes carries ',
         CAST(n_nat_mandates AS STRING), ' elections with mandates'),
  'Load official mandate counts into ext_mandates'
FROM cnt
UNION ALL
SELECT 12, 'Backtest: enough national elections with totals, lists and mandates',
  CASE WHEN n_nat_full >= min_bt THEN 'READY' ELSE 'THIN' END,
  CONCAT(CAST(n_nat_full AS STRING), ' national elections; at least ', CAST(min_bt AS STRING), ' are required'),
  'A national polls-to-result backtest needs earlier national elections with totals, list votes, mandates AND the polls published before them; the pipeline runs only the downscaling backtest (Stage 12 B1-B3) until then'
FROM cnt
ORDER BY stage, requirement;
