-- STAGE 4.1  Local-election swing panel (observed pairs, no modelling).
-- Objective : one row per municipality with a recent local election, holding the OBSERVED change between the national
--             baseline and the local election, in the three comparable ways the package provides:
--               (a) lead_share_change_pp          local lead-list share minus the baseline SNS-led list share  [composition mismatch]
--               (b) proxy_change_pp_*              local lead-list share minus the baseline share of the SAME electoral families
--                                                 (documented coalition members), with the joint Dveri/Zavetnici list excluded or included
--               (c) turnout_change_pp              local turnout rate minus baseline national-election turnout rate
--             Local-vs-parliamentary differences are NOT a national swing: different contest, different lists, different electorate.
-- Input     : paired_changes_13, s0_municipality_status (dynamic classification), cfg_parameters
-- Output    : {DS}.s4_local_swing_panel
-- Use       : eligibility columns decide who enters Stage 4 models; nothing here is imputed.
CREATE OR REPLACE TABLE `{DS}.s4_local_swing_panel` AS
SELECT
  p.geo_id, p.municipality, ms.region_id, ms.local_status, ms.months_before_target,
  p.baseline_date, p.local_election_date,
  p.baseline_2023_registered_weight AS baseline_registered,
  p.lead_share_valid_2023, p.lead_share_valid_local,
  p.turnout_rate_2023, p.turnout_rate_local,
  p.lead_share_change_pp,
  p.proxy_share_change_pp_excluding_mixed AS proxy_change_pp_excl_joint_list,
  p.proxy_share_change_pp_including_mixed AS proxy_change_pp_incl_joint_list,
  p.turnout_change_pp,
  p.mapping_status, p.local_quality_status,
  p.eligible_for_default_model, p.eligible_for_proxy_model,
  p.cohort_nov2025, p.cohort_mar2026,
  CASE WHEN p.eligible_for_proxy_model = 1 THEN 'proxy_model'
       WHEN p.eligible_for_default_model = 1 THEN 'default_only_coalition_members_incomplete'
       ELSE 'excluded_reconciliation_failure' END AS use_class
FROM `{DS}.paired_changes_13` AS p
LEFT JOIN `{DS}.s0_municipality_status` AS ms ON ms.geo_id = p.geo_id
ORDER BY p.local_election_date, p.geo_id;
