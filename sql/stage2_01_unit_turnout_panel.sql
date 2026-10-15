-- STAGE 2.1  Unit turnout panel for the target election (baseline attendance + register scaling).
-- Objective : one row per disjoint 2023 electoral unit with the observed baseline and the register assumed for the
--             target election. This is the input to the turnout calibration (Stage 3, Python).
-- Input     : election_totals (latest national election, leaf units), territories, ext_register_2026, cfg_parameters,
--             s1_unit_family_votes (earlier election valid votes, for the volatility diagnostic)
-- Output    : {DS}.s2_unit_panel
-- Register  : if ext_register_2026 has a row for the unit it is used; otherwise the baseline register is scaled by
--             register_total_2026 / national baseline register (register_scaling_mode = national_ratio).
--             register_source records which. This is an ANALYST ASSUMPTION where the source is the ratio.
-- Rate fixing: units whose territories.region_id is in fixed_rate_region_ids, and special electorates, keep their
--             baseline attendance RATE in the calibration (fixed_rate = true). These lists live in cfg_parameters.
CREATE OR REPLACE TABLE `{DS}.s2_unit_panel` AS
WITH prm AS (
  SELECT
    MAX(CASE WHEN param_key = 'register_total_2026' THEN CAST(param_value AS FLOAT64) END) AS register_total_target,
    MAX(CASE WHEN param_key = 'fixed_rate_region_ids' THEN param_value END) AS fixed_regions,
    MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
base_election AS (
  SELECT t.election_id
  FROM `{DS}.election_totals` AS t, prm
  WHERE t.geo_level = 'national' AND t.election_id LIKE CONCAT(prm.nat_prefix, '%')
  QUALIFY ROW_NUMBER() OVER (ORDER BY t.election_date DESC) = 1
),
prior_election AS (   -- the national election before the baseline (list votes only is enough here)
  SELECT election_id FROM (
    SELECT DISTINCT election_id, election_date FROM `{DS}.s1_unit_family_votes`
  ) AS e
  WHERE e.election_id NOT IN (SELECT election_id FROM base_election)
  QUALIFY ROW_NUMBER() OVER (ORDER BY e.election_date DESC) = 1
),
leaf AS (
  SELECT t.geo_id, t.geo_name, t.registered_voters, t.voters_turned_out, t.ballots_cast, t.invalid_ballots,
         t.valid_ballots_reported, t.valid_ballots_from_lists
  FROM `{DS}.election_totals` AS t JOIN base_election AS b ON b.election_id = t.election_id
  WHERE t.is_2023_leaf = 1
),
nat_base AS (SELECT SUM(registered_voters) AS registered_total FROM leaf),
prior AS (
  SELECT u.geo_id, SUM(u.votes) AS valid_votes_prior
  FROM `{DS}.s1_unit_family_votes` AS u JOIN prior_election AS p ON p.election_id = u.election_id
  GROUP BY u.geo_id
)
SELECT
  l.geo_id, l.geo_name, tr.region_id, tr.is_special_electorate, tr.sample_13,
  l.registered_voters AS registered_baseline,
  l.voters_turned_out AS turned_out_baseline,
  l.ballots_cast AS ballots_cast_baseline,
  l.invalid_ballots AS invalid_baseline,
  l.valid_ballots_reported AS valid_baseline,
  SAFE_DIVIDE(l.voters_turned_out, l.registered_voters) AS turnout_rate_baseline,
  SAFE_DIVIDE(l.ballots_cast, l.voters_turned_out) AS ballots_per_turned_out_baseline,
  SAFE_DIVIDE(l.invalid_ballots, l.ballots_cast) AS invalid_rate_baseline,
  COALESCE(r.registered_voters, l.registered_voters * SAFE_DIVIDE(prm.register_total_target, nb.registered_total)) AS registered_target,
  CASE WHEN r.registered_voters IS NOT NULL THEN 'ext_register_2026' ELSE 'national_ratio_scaling' END AS register_source,
  (tr.is_special_electorate = 1
     OR CONCAT(',', prm.fixed_regions, ',') LIKE CONCAT('%,', COALESCE(tr.region_id, '#none#'), ',%')) AS fixed_rate,
  p.valid_votes_prior,
  SAFE_DIVIDE(l.valid_ballots_reported, p.valid_votes_prior) AS valid_ratio_baseline_over_prior
FROM leaf AS l
JOIN `{DS}.territories` AS tr ON tr.geo_id = l.geo_id
CROSS JOIN prm
CROSS JOIN nat_base AS nb
LEFT JOIN `{DS}.ext_register_2026` AS r ON r.geo_id = l.geo_id
LEFT JOIN prior AS p ON p.geo_id = l.geo_id
ORDER BY l.geo_id;
