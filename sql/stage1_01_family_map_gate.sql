-- STAGE 1.1  Gate on the list-family map (party/list harmonization).
-- Objective : every national list of every national election must map to exactly one family, and the dependence of the
--             baseline on UNREVIEWED mappings must be visible before any number is aggregated.
-- Input     : list_votes (national rows), cfg_list_family_map, cfg_parameters
-- Output    : {DS}.s1_family_map_gate  (one row per national election)
-- Gate      : FAIL  = unmapped lists, duplicate mappings or map rows without data (stop);
--             PROVISIONAL = every list mapped but some mappings are 'proposed_unreviewed' (continue, label outputs);
--             PASS  = every mapping reviewed.
CREATE OR REPLACE TABLE `{DS}.s1_family_map_gate` AS
WITH prm AS (
  SELECT MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
nat AS (
  SELECT v.election_id, v.list_id, v.votes, v.vote_share_valid
  FROM `{DS}.list_votes` AS v, prm
  WHERE v.geo_level = 'national' AND v.election_id LIKE CONCAT(prm.nat_prefix, '%')
),
map_n AS (
  SELECT election_id, list_id, COUNT(*) AS n_map_rows FROM `{DS}.cfg_list_family_map` GROUP BY election_id, list_id
),
joined AS (
  SELECT nat.election_id, nat.list_id, nat.vote_share_valid,
         m.family, m.confidence, m.mapping_status, m.is_minority_proposed, COALESCE(mn.n_map_rows, 0) AS n_map_rows
  FROM nat
  LEFT JOIN `{DS}.cfg_list_family_map` AS m ON m.election_id = nat.election_id AND m.list_id = nat.list_id
  LEFT JOIN map_n AS mn ON mn.election_id = nat.election_id AND mn.list_id = nat.list_id
),
orphans AS (
  SELECT m.election_id, COUNT(*) AS n_orphan_map_rows
  FROM `{DS}.cfg_list_family_map` AS m
  WHERE NOT EXISTS (SELECT 1 FROM nat WHERE nat.election_id = m.election_id AND nat.list_id = m.list_id)
  GROUP BY m.election_id
),
agg AS (
  SELECT j.election_id,
         COUNT(*) AS n_lists,
         SUM(CASE WHEN j.n_map_rows = 0 THEN 1 ELSE 0 END) AS n_unmapped,
         SUM(CASE WHEN j.n_map_rows > 1 THEN 1 ELSE 0 END) AS n_duplicate_mappings,
         SUM(CASE WHEN j.mapping_status = 'reviewed' THEN 1 ELSE 0 END) AS n_reviewed,
         SUM(CASE WHEN j.mapping_status != 'reviewed' OR j.mapping_status IS NULL THEN 1 ELSE 0 END) AS n_not_reviewed,
         SUM(CASE WHEN j.confidence = 'low' THEN j.vote_share_valid ELSE 0 END) AS share_valid_low_confidence,
         SUM(CASE WHEN j.family = 'UNCLASSIFIED' THEN j.vote_share_valid ELSE 0 END) AS share_valid_unclassified,
         SUM(CASE WHEN j.is_minority_proposed THEN j.vote_share_valid ELSE 0 END) AS share_valid_minority_proposed,
         SUM(j.vote_share_valid) AS sum_share_valid
  FROM joined AS j
  GROUP BY j.election_id
)
SELECT a.election_id, a.n_lists, a.n_unmapped, a.n_duplicate_mappings, COALESCE(o.n_orphan_map_rows, 0) AS n_orphan_map_rows,
       a.n_reviewed, a.n_not_reviewed,
       a.share_valid_low_confidence, a.share_valid_unclassified, a.share_valid_minority_proposed, a.sum_share_valid,
       CASE WHEN a.n_unmapped > 0 OR a.n_duplicate_mappings > 0 OR COALESCE(o.n_orphan_map_rows, 0) > 0 THEN 'FAIL'
            WHEN a.n_not_reviewed > 0 THEN 'PROVISIONAL'
            ELSE 'PASS' END AS gate_status
FROM agg AS a
LEFT JOIN orphans AS o ON o.election_id = a.election_id
ORDER BY a.election_id;
