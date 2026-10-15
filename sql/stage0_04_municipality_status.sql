-- STAGE 0.4  Municipality status: which units have a recent local election, per the data and the analyst registry.
-- Objective : classify every 2023 leaf unit DYNAMICALLY. Nothing here names a municipality.
--             "Recent" = local election at most recent_local_max_age_months before election_target_date (cfg_parameters).
-- Input     : territories, election_totals, ext_local_election_registry, cfg_parameters
-- Output    : {DS}.s0_municipality_status
-- Caveat    : ABSENCE FROM THE DATASET IS NOT ABSENCE OF A LOCAL ELECTION. The dataset only contains the local
--             elections its authors transcribed; units outside it are labelled none_in_dataset_or_registry,
--             never "no local election". Register additional local elections in ext_local_election_registry.
CREATE OR REPLACE TABLE `{DS}.s0_municipality_status` AS
WITH prm AS (
  SELECT
    MAX(CASE WHEN param_key = 'election_target_date' THEN CAST(param_value AS DATE) END) AS target_date,
    MAX(CASE WHEN param_key = 'recent_local_max_age_months' THEN CAST(param_value AS INT64) END) AS max_age_months,
    MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
base_election AS (            -- most recent national election with totals = the baseline for unit attributes
  SELECT t.election_id, t.election_date
  FROM `{DS}.election_totals` AS t, prm
  WHERE t.geo_level = 'national' AND t.election_id LIKE CONCAT(prm.nat_prefix, '%')
  QUALIFY ROW_NUMBER() OVER (ORDER BY t.election_date DESC) = 1
),
base AS (
  SELECT t.geo_id, t.registered_voters AS registered_baseline, t.voters_turned_out AS turned_out_baseline,
         SAFE_DIVIDE(t.voters_turned_out, t.registered_voters) AS turnout_rate_baseline
  FROM `{DS}.election_totals` AS t JOIN base_election AS b ON b.election_id = t.election_id
  WHERE t.is_2023_leaf = 1
),
local_in_data AS (
  SELECT geo_id, election_id AS local_election_id, election_date AS local_date,
         is_round_nov2025, is_round_mar2026
  FROM `{DS}.election_totals`
  WHERE is_local_election = 1
  QUALIFY ROW_NUMBER() OVER (PARTITION BY geo_id ORDER BY election_date DESC) = 1
),
local_in_registry AS (
  SELECT geo_id, election_date AS registry_date, election_type AS registry_type, results_in_dataset AS registry_results_in_dataset
  FROM `{DS}.ext_local_election_registry`
  WHERE election_date IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (PARTITION BY geo_id ORDER BY election_date DESC) = 1
),
joined AS (
  SELECT
    tr.geo_id, tr.geo_name, tr.region_id, tr.is_special_electorate, tr.sample_13,
    base.registered_baseline, base.turned_out_baseline, base.turnout_rate_baseline,
    l.local_election_id, l.local_date, r.registry_date, r.registry_type,
    prm.target_date, prm.max_age_months,
    -- the later of the two sources is the "latest known" local election
    CASE WHEN l.local_date IS NULL THEN r.registry_date
         WHEN r.registry_date IS NULL THEN l.local_date
         WHEN r.registry_date > l.local_date THEN r.registry_date ELSE l.local_date END AS latest_local_date
  FROM `{DS}.territories` AS tr
  CROSS JOIN prm
  LEFT JOIN base ON base.geo_id = tr.geo_id
  LEFT JOIN local_in_data AS l ON l.geo_id = tr.geo_id
  LEFT JOIN local_in_registry AS r ON r.geo_id = tr.geo_id
  WHERE tr.is_2023_leaf = 1
)
SELECT
  j.geo_id, j.geo_name, j.region_id, j.is_special_electorate, j.sample_13,
  j.registered_baseline, j.turned_out_baseline, j.turnout_rate_baseline,
  j.local_election_id, j.local_date AS local_date_in_dataset, j.registry_date AS local_date_in_registry,
  j.latest_local_date,
  CASE WHEN j.latest_local_date IS NOT NULL THEN DATE_DIFF(j.target_date, j.latest_local_date, MONTH) END AS months_before_target,
  CASE
    WHEN j.is_special_electorate = 1 THEN 'special_electorate'
    WHEN j.local_date IS NOT NULL AND DATE_DIFF(j.target_date, j.local_date, MONTH) <= j.max_age_months THEN 'recent_local_results_in_dataset'
    WHEN j.local_date IS NOT NULL THEN 'older_local_results_in_dataset'
    WHEN j.registry_date IS NOT NULL AND DATE_DIFF(j.target_date, j.registry_date, MONTH) <= j.max_age_months THEN 'recent_local_registered_no_results'
    WHEN j.registry_date IS NOT NULL THEN 'older_local_registered_no_results'
    ELSE 'none_in_dataset_or_registry'
  END AS local_status,
  CASE WHEN j.is_special_electorate = 1 THEN 'not applicable'
       WHEN j.local_date IS NULL AND j.registry_date IS NULL THEN 'coverage unknown: local elections outside the dataset are not captured'
       WHEN j.local_date IS NULL THEN 'local election known from registry; results not in dataset'
       ELSE 'results available' END AS data_coverage_note
FROM joined AS j
ORDER BY j.geo_id;
