-- STAGE 7.1  Minority-list base: observed 2023 votes of the minority families that 2026 minority lists continue.
-- Objective : the historical anchor for minority-list forecasts, by unit, with the unit's baseline valid votes.
--             Which family a 2026 list continues is read from cfg_minority_roster_map (analyst-editable, unreviewed).
-- Input     : s1_unit_family_votes, cfg_minority_roster_map, s2_unit_panel
-- Output    : {DS}.s7_minority_unit_base  (unit x analog family)
CREATE OR REPLACE TABLE `{DS}.s7_minority_unit_base` AS
WITH prm AS (
  SELECT MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
base_election AS (
  SELECT t.election_id
  FROM `{DS}.election_totals` AS t, prm
  WHERE t.geo_level = 'national' AND t.election_id LIKE CONCAT(prm.nat_prefix, '%')
  QUALIFY ROW_NUMBER() OVER (ORDER BY t.election_date DESC) = 1
),
fams AS (
  SELECT DISTINCT analog_family FROM `{DS}.cfg_minority_roster_map` WHERE analog_family IS NOT NULL
),
-- BigQuery does not allow a subquery inside a JOIN condition, so the baseline election is selected here, before the join.
base_votes AS (
  SELECT u.geo_id, u.family, u.votes
  FROM `{DS}.s1_unit_family_votes` AS u
  WHERE u.election_id IN (SELECT election_id FROM base_election)
)
SELECT p.geo_id, p.region_id, f.analog_family AS family,
       COALESCE(u.votes, 0) AS votes_baseline, p.valid_baseline AS unit_valid_baseline, p.registered_baseline
FROM `{DS}.s2_unit_panel` AS p
CROSS JOIN fams AS f
LEFT JOIN base_votes AS u
  ON u.geo_id = p.geo_id AND u.family = f.analog_family
ORDER BY p.geo_id, f.analog_family;
