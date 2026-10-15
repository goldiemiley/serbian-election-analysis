-- STAGE 0.2  Integrity checks on the observed data.
-- Objective : prove the package's own accounting identities hold in YOUR loaded copy, and record every known
--             limitation as a check row instead of a silent assumption.
-- Input     : election_totals, list_votes, polling_stations_2023, territories, cfg_parameters
-- Output    : {DS}.s0_integrity_checks  (check_id, severity, description, n_violations, detail, status)
--             status: PASS | FAIL (severity error) | WARN (severity warn) | INFO (severity info, informational)
-- Design    : election_id values are read from cfg_parameters (national_election_prefix) and from the data;
--             tolerances come from cfg_parameters. Strings in this file avoid type keywords on purpose.
CREATE OR REPLACE TABLE `{DS}.s0_integrity_checks` AS
WITH prm AS (
  SELECT
    MAX(CASE WHEN param_key = 'share_sum_tolerance' THEN CAST(param_value AS FLOAT64) END) AS tol,
    MAX(CASE WHEN param_key = 'national_election_prefix' THEN param_value END) AS nat_prefix
  FROM `{DS}.cfg_parameters`
),
-- national elections that have BOTH a national totals row and station data are the ones the leaf identity applies to
nat_el AS (
  SELECT DISTINCT t.election_id
  FROM `{DS}.election_totals` AS t, prm
  WHERE t.election_id LIKE CONCAT(prm.nat_prefix, '%') AND t.geo_level = 'national'
),
leaf AS (
  SELECT t.election_id,
         COUNT(*) AS n_leaf,
         SUM(t.registered_voters) AS registered,
         SUM(t.voters_turned_out) AS turned_out,
         SUM(t.ballots_cast) AS ballots_cast,
         SUM(t.valid_ballots_reported) AS valid
  FROM `{DS}.election_totals` AS t
  WHERE t.is_2023_leaf = 1 AND t.election_id IN (SELECT election_id FROM nat_el)
  GROUP BY t.election_id
),
nat AS (
  SELECT t.election_id, t.registered_voters AS registered, t.voters_turned_out AS turned_out,
         t.ballots_cast, t.valid_ballots_reported AS valid
  FROM `{DS}.election_totals` AS t
  WHERE t.geo_level = 'national' AND t.election_id IN (SELECT election_id FROM nat_el)
),
stn AS (
  SELECT election_id, COUNT(*) AS n_stations, SUM(registered_voters) AS registered, SUM(voters_turned_out) AS turned_out,
         SUM(ballots_cast) AS ballots_cast, SUM(valid_ballots) AS valid
  FROM `{DS}.polling_stations_2023`
  GROUP BY election_id
),
lv_geo AS (
  SELECT election_id, geo_id, SUM(votes) AS list_sum FROM `{DS}.list_votes` GROUP BY election_id, geo_id
),
unit_lists AS (   -- list votes summed over the disjoint leaf units, per national election and list
  SELECT v.election_id, v.list_id, SUM(v.votes) AS unit_sum
  FROM `{DS}.list_votes` AS v
  JOIN `{DS}.territories` AS tr ON tr.geo_id = v.geo_id
  WHERE tr.is_2023_leaf = 1 AND v.geo_level != 'national'
  GROUP BY v.election_id, v.list_id
),
nat_lists AS (
  SELECT v.election_id, v.list_id, v.votes AS nat_votes
  FROM `{DS}.list_votes` AS v, prm
  WHERE v.geo_level = 'national' AND v.election_id LIKE CONCAT(prm.nat_prefix, '%')
),
list_recon AS (
  SELECT n.election_id, n.list_id, n.nat_votes, u.unit_sum, COALESCE(u.unit_sum, 0) - n.nat_votes AS diff
  FROM nat_lists AS n LEFT JOIN unit_lists AS u ON u.election_id = n.election_id AND u.list_id = n.list_id
),
checks AS (
SELECT 'C01' AS check_id, 'error' AS severity,
  'election_totals key (election_id, geo_id) is unique' AS description,
  (SELECT COUNT(*) FROM (SELECT election_id, geo_id FROM `{DS}.election_totals` GROUP BY election_id, geo_id HAVING COUNT(*) > 1)) AS n_violations,
  CAST(NULL AS STRING) AS detail
UNION ALL
SELECT 'C02', 'error', 'list_votes key (election_id, geo_id, list_id) is unique',
  (SELECT COUNT(*) FROM (SELECT election_id, geo_id, list_id FROM `{DS}.list_votes` GROUP BY election_id, geo_id, list_id HAVING COUNT(*) > 1)),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C03', 'error', 'Disjoint leaf units (is_2023_leaf=1) sum exactly to the national row: registered, turned out, ballots cast, valid',
  (SELECT COUNT(*) FROM leaf JOIN nat USING (election_id)
   WHERE leaf.registered != nat.registered OR leaf.turned_out != nat.turned_out
      OR leaf.ballots_cast != nat.ballots_cast OR leaf.valid != nat.valid),
  (SELECT CONCAT('leaf units = ', CAST(MAX(n_leaf) AS STRING), '; national registered = ', CAST(MAX(nat.registered) AS STRING))
   FROM leaf JOIN nat USING (election_id))
UNION ALL
SELECT 'C04', 'error', 'Polling-station rows sum exactly to the national row (registered, turned out, ballots cast, valid)',
  (SELECT COUNT(*) FROM stn JOIN nat USING (election_id)
   WHERE stn.registered != nat.registered OR stn.turned_out != nat.turned_out
      OR stn.ballots_cast != nat.ballots_cast OR stn.valid != nat.valid),
  (SELECT CONCAT('stations = ', CAST(MAX(n_stations) AS STRING)) FROM stn)
UNION ALL
SELECT 'C05', 'error', 'List votes of every geography with totals sum to valid_ballots_from_lists (national parliamentary elections)',
  (SELECT COUNT(*) FROM `{DS}.election_totals` AS t JOIN lv_geo AS g USING (election_id, geo_id)
   WHERE t.election_id IN (SELECT election_id FROM nat_el) AND g.list_sum != t.valid_ballots_from_lists),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C06', 'error', 'National list votes sum to national valid ballots',
  (SELECT COUNT(*) FROM nat JOIN lv_geo AS g ON g.election_id = nat.election_id
   JOIN `{DS}.election_totals` AS t ON t.election_id = g.election_id AND t.geo_id = g.geo_id AND t.geo_level = 'national'
   WHERE g.list_sum != nat.valid),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C07', 'warn', 'ballots_cast = valid_ballots_reported + invalid_ballots (all rows with totals)',
  (SELECT COUNT(*) FROM `{DS}.election_totals` WHERE ballots_cast != valid_ballots_reported + invalid_ballots),
  (SELECT STRING_AGG(CONCAT(election_id, '/', geo_id), ', ') FROM `{DS}.election_totals`
   WHERE ballots_cast != valid_ballots_reported + invalid_ballots)
UNION ALL
SELECT 'C08', 'warn', 'voters_turned_out <= registered_voters',
  (SELECT COUNT(*) FROM `{DS}.election_totals` WHERE voters_turned_out > registered_voters),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C09', 'warn', 'Published vote_share_valid matches votes / valid ballots from lists within the configured tolerance (national elections)',
  (SELECT COUNT(*) FROM `{DS}.list_votes` AS v JOIN `{DS}.election_totals` AS t USING (election_id, geo_id), prm
   WHERE v.election_id IN (SELECT election_id FROM nat_el)
     AND ABS(v.votes / t.valid_ballots_from_lists - v.vote_share_valid) > prm.tol),
  (SELECT CONCAT('tolerance = ', CAST(MAX(tol) AS STRING)) FROM prm)
UNION ALL
SELECT 'C10', 'info', 'Rows where the published list sum differs from the published valid-ballot count (known source discrepancy; both values retained)',
  (SELECT COUNT(*) FROM `{DS}.election_totals` WHERE list_sum_minus_reported_valid != 0),
  (SELECT STRING_AGG(CONCAT(election_id, ' diff=', CAST(list_sum_minus_reported_valid AS STRING)), '; ')
   FROM `{DS}.election_totals` WHERE list_sum_minus_reported_valid != 0)
UNION ALL
SELECT 'C11', 'error', 'Every geography in election_totals and list_votes exists in territories',
  (SELECT COUNT(*) FROM (
     SELECT geo_id FROM `{DS}.election_totals` UNION DISTINCT SELECT geo_id FROM `{DS}.list_votes`) AS u
   LEFT JOIN `{DS}.territories` AS tr USING (geo_id) WHERE tr.geo_id IS NULL),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C12', 'error', 'Every local-election municipality is a 2023 leaf unit with a national-election baseline row',
  (SELECT COUNT(*) FROM `{DS}.election_totals` AS l
   WHERE l.is_local_election = 1
     AND NOT EXISTS (SELECT 1 FROM `{DS}.election_totals` AS b
                     WHERE b.geo_id = l.geo_id AND b.is_2023_leaf = 1 AND b.election_id IN (SELECT election_id FROM nat_el))),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C13', 'info', 'Elections with list votes but WITHOUT turnout/register totals (cannot be used for turnout modelling)',
  (SELECT COUNT(*) FROM (SELECT DISTINCT election_id FROM `{DS}.list_votes`) AS lv
   WHERE lv.election_id NOT IN (SELECT DISTINCT election_id FROM `{DS}.election_totals`)),
  (SELECT STRING_AGG(election_id, ', ') FROM (SELECT DISTINCT election_id FROM `{DS}.list_votes`) AS lv
   WHERE lv.election_id NOT IN (SELECT DISTINCT election_id FROM `{DS}.election_totals`))
UNION ALL
SELECT 'C14', 'info', 'Elections with list votes but WITHOUT official mandates in list_votes (cannot validate the seat allocation from the dataset alone)',
  (SELECT COUNT(*) FROM (SELECT election_id FROM `{DS}.list_votes`
                         WHERE election_id LIKE CONCAT((SELECT nat_prefix FROM prm), '%')
                         GROUP BY election_id HAVING COUNT(mandates) = 0)),
  (SELECT STRING_AGG(election_id, ', ') FROM (SELECT election_id FROM `{DS}.list_votes`
                         WHERE election_id LIKE CONCAT((SELECT nat_prefix FROM prm), '%')
                         GROUP BY election_id HAVING COUNT(mandates) = 0))
UNION ALL
SELECT 'C15', 'warn', 'No negative counts in election_totals',
  (SELECT COUNT(*) FROM `{DS}.election_totals`
   WHERE registered_voters < 0 OR voters_turned_out < 0 OR ballots_cast < 0 OR invalid_ballots < 0 OR valid_ballots_reported < 0),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C17', 'error', 'At least one national election has a national totals row (guards against checks passing on an empty set)',
  (SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END FROM nat),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C16', 'error', 'Number of leaf units equals the number of territories flagged is_2023_leaf',
  (SELECT ABS((SELECT COUNT(*) FROM `{DS}.territories` WHERE is_2023_leaf = 1) - (SELECT MAX(n_leaf) FROM leaf))),
  CAST(NULL AS STRING)
UNION ALL
SELECT 'C18', 'warn', 'List votes summed over the disjoint leaf units equal the national list votes (every national election, every list; covers elections without totals rows)',
  (SELECT COUNT(*) FROM list_recon WHERE diff != 0),
  (SELECT STRING_AGG(CONCAT(election_id, '/', list_id, ' diff=', CAST(diff AS STRING)), '; ') FROM list_recon WHERE diff != 0)
UNION ALL
SELECT 'C19', 'error', 'Every national list has votes in the leaf units (no list silently missing from the unit data)',
  (SELECT COUNT(*) FROM list_recon WHERE unit_sum IS NULL),
  CAST(NULL AS STRING)
)
SELECT check_id, severity, description, n_violations, detail,
  CASE WHEN n_violations = 0 THEN 'PASS'
       WHEN severity = 'error' THEN 'FAIL'
       WHEN severity = 'warn' THEN 'WARN'
       ELSE 'INFO' END AS status
FROM checks
ORDER BY check_id;
