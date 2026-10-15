-- STAGE 0.3  Election inventory: what exactly is in the dataset, per election.
-- Objective : replace assumptions about "which elections exist" with a table read from the data.
-- Input     : election_totals, list_votes, polling_stations_2023, cfg_parameters
-- Output    : {DS}.s0_election_inventory
CREATE OR REPLACE TABLE `{DS}.s0_election_inventory` AS
WITH prm AS (
  SELECT MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
tot AS (
  SELECT election_id,
         MIN(election_date) AS election_date_totals,
         COUNT(*) AS n_total_rows,
         COUNT(DISTINCT geo_id) AS n_geographies_with_totals,
         MAX(CASE WHEN geo_level = 'national' THEN registered_voters END) AS national_registered,
         MAX(CASE WHEN geo_level = 'national' THEN voters_turned_out END) AS national_turned_out,
         MAX(CASE WHEN geo_level = 'national' THEN valid_ballots_reported END) AS national_valid_ballots,
         MAX(is_local_election) AS is_local_election
  FROM `{DS}.election_totals`
  GROUP BY election_id
),
lv AS (
  SELECT election_id,
         MIN(election_date) AS election_date_lists,
         COUNT(*) AS n_list_vote_rows,
         COUNT(DISTINCT geo_id) AS n_geographies_with_lists,
         COUNT(DISTINCT list_id) AS n_distinct_lists,
         COUNT(mandates) AS n_rows_with_official_mandates,
         MAX(CASE WHEN geo_level = 'national' THEN 1 ELSE 0 END) AS has_national_list_rows
  FROM `{DS}.list_votes`
  GROUP BY election_id
)
SELECT
  COALESCE(tot.election_id, lv.election_id) AS election_id,
  COALESCE(tot.election_date_totals, lv.election_date_lists) AS election_date,
  CASE WHEN COALESCE(tot.is_local_election, 0) = 1 THEN 'local'
       WHEN COALESCE(tot.election_id, lv.election_id) LIKE CONCAT(prm.nat_prefix, '%') THEN 'national_parliamentary'
       ELSE 'other' END AS election_type,
  tot.election_id IS NOT NULL AS has_totals,
  lv.election_id IS NOT NULL AS has_list_votes,
  COALESCE(lv.n_rows_with_official_mandates, 0) > 0 AS has_official_mandates,
  tot.n_geographies_with_totals,
  lv.n_geographies_with_lists,
  lv.n_distinct_lists,
  tot.national_registered,
  tot.national_turned_out,
  tot.national_valid_ballots,
  CASE WHEN tot.national_registered > 0 THEN tot.national_turned_out / tot.national_registered END AS national_turnout_rate,
  lv.has_national_list_rows = 1 AS has_national_list_rows
FROM tot
FULL OUTER JOIN lv ON lv.election_id = tot.election_id
CROSS JOIN prm
ORDER BY election_date, election_id;
