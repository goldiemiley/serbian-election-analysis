-- STAGE 6.1  Geography base: the observed 2023 pattern that shapes WHERE each list's votes fall.
-- Objective : express each leaf unit's baseline as votes per registered voter for every family, plus two pseudo-origins:
--             ABSTAIN (share of the register that did not vote) and REGISTERED (constant per registered voter).
--             cfg_origin_weights then combines these into a unit-level weight for every 2026 list. The national LEVEL of each
--             list is never taken from here: it is calibrated to the poll-based target (see src/voteshare.py).
-- Input     : s1_unit_family_votes, s2_unit_panel, cfg_parameters
-- Output    : {DS}.s6_unit_geography_base
CREATE OR REPLACE TABLE `{DS}.s6_unit_geography_base` AS
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
fam AS (
  SELECT u.geo_id, u.family AS origin, SAFE_DIVIDE(u.votes, p.registered_baseline) AS per_registered
  FROM `{DS}.s1_unit_family_votes` AS u
  JOIN `{DS}.s2_unit_panel` AS p ON p.geo_id = u.geo_id
  JOIN base_election AS b ON b.election_id = u.election_id
),
pseudo AS (
  SELECT geo_id, 'ABSTAIN' AS origin, 1 - turnout_rate_baseline AS per_registered FROM `{DS}.s2_unit_panel`
  UNION ALL
  SELECT geo_id, 'REGISTERED' AS origin, 1.0 AS per_registered FROM `{DS}.s2_unit_panel`
)
SELECT geo_id, origin, per_registered FROM fam
UNION ALL
SELECT geo_id, origin, per_registered FROM pseudo
ORDER BY geo_id, origin;
