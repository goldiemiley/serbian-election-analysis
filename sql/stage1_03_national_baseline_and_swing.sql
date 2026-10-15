-- STAGE 1.3  National baseline by family and swing between consecutive national elections.
-- Objective : national shares by family per election (sum of disjoint units) and the change from the previous national
--             election. A swing is a difference of aggregate shares: it is NOT evidence about individual voters.
-- Input     : s1_unit_family_votes, cfg_list_family_map
-- Output    : {DS}.s1_national_family  (election x family; share, previous share, change in percentage points)
-- Caveats   : a family that did not run in one election has ran_* = false and a NULL share, not zero; families are
--             PROPOSED groupings (see s1_family_map_gate for how much of the vote rests on unreviewed mappings).
CREATE OR REPLACE TABLE `{DS}.s1_national_family` AS
WITH nat AS (
  SELECT election_id, election_date, family, MAX(bloc) AS bloc, SUM(votes) AS votes, MAX(n_lists) AS n_lists
  FROM `{DS}.s1_unit_family_votes`
  GROUP BY election_id, election_date, family
),
tot AS (
  SELECT election_id, SUM(votes) AS valid_votes FROM nat GROUP BY election_id
),
shares AS (
  SELECT n.election_id, n.election_date, n.family, n.bloc, n.votes, n.n_lists, t.valid_votes,
         SAFE_DIVIDE(n.votes, t.valid_votes) AS share_valid
  FROM nat AS n JOIN tot AS t ON t.election_id = n.election_id
),
elections AS (SELECT DISTINCT election_id, election_date FROM shares),
grid AS (   -- every family x every election, so that "did not run" is explicit
  SELECT e.election_id, e.election_date, f.family
  FROM elections AS e CROSS JOIN (SELECT DISTINCT family FROM shares) AS f
),
full_grid AS (
  SELECT g.election_id, g.election_date, g.family, s.bloc, s.votes, s.n_lists, s.valid_votes, s.share_valid,
         s.election_id IS NOT NULL AS ran
  FROM grid AS g
  LEFT JOIN shares AS s ON s.election_id = g.election_id AND s.family = g.family
)
SELECT
  fg.election_id, fg.election_date, fg.family, fg.bloc, fg.ran, fg.n_lists, fg.votes, fg.valid_votes, fg.share_valid,
  LAG(fg.election_id) OVER (PARTITION BY fg.family ORDER BY fg.election_date) AS previous_election_id,
  LAG(fg.share_valid) OVER (PARTITION BY fg.family ORDER BY fg.election_date) AS previous_share_valid,
  LAG(fg.ran) OVER (PARTITION BY fg.family ORDER BY fg.election_date) AS ran_previous,
  100.0 * (fg.share_valid - LAG(fg.share_valid) OVER (PARTITION BY fg.family ORDER BY fg.election_date)) AS change_pp
FROM full_grid AS fg
ORDER BY fg.election_date, fg.share_valid DESC;
