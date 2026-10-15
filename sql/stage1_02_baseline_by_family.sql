-- STAGE 1.2  Historical baseline by family: national and per electoral unit.
-- Objective : the observed starting point of the whole forecast, in the same family space as the forecast lists.
-- Input     : list_votes (disjoint 2023 leaf units + national rows), cfg_list_family_map
-- Output    : {DS}.s1_unit_family_votes  (election x leaf unit x family)      <- consumed by Stages 2, 6, 7, 8
-- Design    : leaf units only (is_2023_leaf = 1) so overlapping aggregates are never double counted; the unit valid-vote
--             denominator is the sum of the unit's list votes, computed identically for every election
--             (election_totals does not exist for every election).
CREATE OR REPLACE TABLE `{DS}.s1_unit_family_votes` AS
WITH prm AS (
  SELECT MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
lv AS (
  SELECT v.election_id, v.election_date, v.geo_id, v.list_id, v.votes
  FROM `{DS}.list_votes` AS v, prm
  WHERE v.is_2023_leaf = 1 AND v.election_id LIKE CONCAT(prm.nat_prefix, '%')
),
fam AS (
  SELECT lv.election_id, lv.election_date, lv.geo_id, m.family, m.bloc, SUM(lv.votes) AS votes, COUNT(*) AS n_lists
  FROM lv
  JOIN `{DS}.cfg_list_family_map` AS m ON m.election_id = lv.election_id AND m.list_id = lv.list_id
  GROUP BY lv.election_id, lv.election_date, lv.geo_id, m.family, m.bloc
)
SELECT f.election_id, f.election_date, f.geo_id, f.family, f.bloc, f.votes, f.n_lists,
       SUM(f.votes) OVER (PARTITION BY f.election_id, f.geo_id) AS unit_valid_votes,
       SAFE_DIVIDE(f.votes, SUM(f.votes) OVER (PARTITION BY f.election_id, f.geo_id)) AS share_valid
FROM fam AS f
ORDER BY f.election_id, f.geo_id, f.family;
