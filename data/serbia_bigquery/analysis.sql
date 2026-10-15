-- Standard SQL. Replace PROJECT_ID.DATASET_ID with your loaded dataset.

-- National control totals: one station row per station; no overlapping municipal aggregates.
SELECT COUNT(*) AS stations,
  SUM(registered_voters) AS registered,
  SUM(voters_turned_out) AS attendance,
  SUM(ballots_cast) AS cast,
  SUM(invalid_ballots) AS invalid,
  SUM(valid_ballots) AS valid
FROM `PROJECT_ID.DATASET_ID.polling_stations_2023`;

-- Complete matched pairs whose counts reconcile. Excludes both Aranđelovac rows.
CREATE OR REPLACE VIEW `PROJECT_ID.DATASET_ID.analysis_panel` AS
SELECT p.* FROM `PROJECT_ID.DATASET_ID.model_panel_13` p
JOIN (
  SELECT geo_id FROM `PROJECT_ID.DATASET_ID.model_panel_13`
  GROUP BY geo_id HAVING COUNT(*) = 2 AND MIN(eligible_for_default_model) = 1
) ok USING (geo_id);

-- Complete pairs with documented coalition-family scenarios and reconciled counts.
CREATE OR REPLACE VIEW `PROJECT_ID.DATASET_ID.proxy_analysis_panel` AS
SELECT p.* FROM `PROJECT_ID.DATASET_ID.model_panel_13` p
JOIN (
  SELECT geo_id FROM `PROJECT_ID.DATASET_ID.model_panel_13`
  GROUP BY geo_id HAVING COUNT(*) = 2 AND MIN(eligible_for_proxy_model) = 1
) ok USING (geo_id);

-- Descriptive cohort changes. Weighting is within the observed sample, not national projection.
SELECT IF(cohort_nov2025 = 1, 'november_2025', 'march_2026') AS cohort,
  COUNT(*) AS municipalities,
  AVG(lead_share_change_pp) AS mean_raw_lead_change_pp,
  SAFE_DIVIDE(SUM(lead_share_change_pp * baseline_2023_registered_weight),
              SUM(baseline_2023_registered_weight)) AS electorate_weighted_raw_change_pp,
  AVG(turnout_change_pp) AS mean_turnout_change_pp
FROM `PROJECT_ID.DATASET_ID.paired_changes_13`
WHERE eligible_for_default_model = 1
GROUP BY cohort;

-- Describe the selection difference in the 2023 baseline. Keep geographical leaves only.
SELECT t.sample_13, COUNT(DISTINCT t.geo_id) AS electoral_units,
  SUM(t.registered_voters) AS registered,
  SAFE_DIVIDE(SUM(v.votes), SUM(t.valid_ballots_reported)) AS sns_led_list_valid_share,
  SAFE_DIVIDE(SUM(t.voters_turned_out), SUM(t.registered_voters)) AS turnout
FROM `PROJECT_ID.DATASET_ID.election_totals` t
JOIN `PROJECT_ID.DATASET_ID.list_votes` v
  USING (election_id, geo_id)
WHERE t.election_id = 'parliamentary_2023' AND t.is_2023_leaf = 1
  AND v.list_id = 'NP202301'
GROUP BY t.sample_13;

-- Published local arithmetic mismatch; expected one row (Aranđelovac, -4).
SELECT geo_name, election_id, valid_ballots_reported, valid_ballots_from_lists,
  list_sum_minus_reported_valid
FROM `PROJECT_ID.DATASET_ID.election_totals`
WHERE list_sum_minus_reported_valid != 0;

-- Wage examples: dated 2026 July net earnings, with source status retained.
SELECT geo_id, geo_name, value AS average_net_earnings_rsd, source_status
FROM `PROJECT_ID.DATASET_ID.context_series`
WHERE metric = 'average_net_earnings' AND period = '202607';

-- Do not specify both post_2023 and is_local_election in the panel regression.
-- First descriptive specification: intercept + 12 mun_<code> columns
-- + is_round_nov2025 + is_round_mar2026. Do not feed every CSV column to a model.
