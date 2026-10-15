-- STAGE 5.1  Poll panel: one row per poll x list, with the data-quality flags the aggregation will respect.
-- Objective : turn ext_polls (analyst-loaded) into a clean panel WITHOUT inventing anything: missing fieldwork dates stay
--             missing, and a proxy date (publication date) is used only to ORDER polls in time and is flagged.
-- Input     : ext_polls, cfg_list_registry_2026, cfg_parameters
-- Output    : {DS}.s5_poll_panel
-- Notes     : shares are proportions of the base named in share_base. Polls are noisy measurements with house effects; they are
--             not vote shares. Reader polls and model outputs must not be loaded into ext_polls.
CREATE OR REPLACE TABLE `{DS}.s5_poll_panel` AS
WITH prm AS (
  SELECT MAX(CASE WHEN param_key = 'election_target_date' THEN CAST(param_value AS DATE) END) AS target_date
  FROM `{DS}.cfg_parameters`
),
per_poll AS (
  SELECT poll_id, SUM(share) AS sum_reported_shares, COUNT(*) AS n_lists_reported
  FROM `{DS}.ext_polls` GROUP BY poll_id
)
SELECT
  p.poll_id, p.pollster, p.commissioned_by,
  p.fieldwork_start, p.fieldwork_end, p.publication_date,
  COALESCE(p.fieldwork_end, p.publication_date) AS poll_date,
  p.fieldwork_end IS NULL AS poll_date_is_proxy,
  DATE_DIFF(prm.target_date, COALESCE(p.fieldwork_end, p.publication_date), DAY) AS days_before_target,
  p.sample_size, p.population_base, p.mode, p.undecided_share, p.turnout_intention_share,
  p.list_key, p.list_label_reported, r.list_name_reported AS roster_name,
  (r.list_key IS NOT NULL) AS list_on_2026_roster,
  p.share, p.share_base,
  pp.sum_reported_shares, pp.n_lists_reported,
  1 - pp.sum_reported_shares AS unreported_remainder,
  pp.sum_reported_shares > 1.0005 AS shares_exceed_one,
  p.reported_margin_of_error, p.methodology_notes, p.source_url, p.verification_status,
  (CASE WHEN p.fieldwork_end IS NULL THEN 0 ELSE 1 END + CASE WHEN p.sample_size IS NULL THEN 0 ELSE 1 END
   + CASE WHEN p.mode IS NULL THEN 0 ELSE 1 END + CASE WHEN p.share_base IS NULL THEN 0 ELSE 1 END
   + CASE WHEN p.commissioned_by IS NULL THEN 0 ELSE 1 END) AS metadata_fields_present_of_5
FROM `{DS}.ext_polls` AS p
CROSS JOIN prm
JOIN per_poll AS pp ON pp.poll_id = p.poll_id
LEFT JOIN `{DS}.cfg_list_registry_2026` AS r ON r.list_key = p.list_key
ORDER BY poll_date, p.poll_id, p.share DESC;
