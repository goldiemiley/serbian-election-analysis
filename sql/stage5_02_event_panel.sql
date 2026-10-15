-- STAGE 5.2  Event panel: reported political developments, kept as DISTINCT observation types.
-- Objective : (i) never treat a departure, a joining, an endorsement and a measured voter shift as the same thing;
--             (ii) mark which events can already be reflected in the polls and which happened after the last poll, so that the
--             scenario adjustments are applied only to the uncaptured part (guard against double counting).
-- Input     : ext_events, ext_polls, cfg_parameters
-- Output    : {DS}.s5_event_panel
-- captured_by_polls: 'yes'     event_date on or before the latest poll date
--                    'no'      event_date after the latest poll date
--                    'unknown' event_date missing (only a report date): treated as uncaptured, flagged
CREATE OR REPLACE TABLE `{DS}.s5_event_panel` AS
WITH last_poll AS (
  SELECT MAX(COALESCE(fieldwork_end, publication_date)) AS last_poll_date FROM `{DS}.ext_polls`
)
SELECT
  e.event_id, e.event_date, e.report_date, e.event_type, e.actor_name, e.actor_role, e.origin_entity, e.destination_entity,
  e.geo_id, e.scope, e.confidence, e.source_name, e.source_url, e.notes,
  lp.last_poll_date,
  CASE WHEN e.event_date IS NULL THEN 'unknown'
       WHEN lp.last_poll_date IS NULL THEN 'no'
       WHEN e.event_date <= lp.last_poll_date THEN 'yes' ELSE 'no' END AS captured_by_polls,
  CASE WHEN e.event_type IN ('left_party', 'expelled') THEN 'organizational_exit'
       WHEN e.event_type IN ('joined_organization', 'new_party_announced') THEN 'organizational_entry'
       WHEN e.event_type = 'endorsed_list' THEN 'public_endorsement'
       WHEN e.event_type = 'measured_voter_shift' THEN 'voter_level_evidence'
       WHEN e.event_type IN ('list_proclaimed', 'list_withdrawn') THEN 'ballot_access'
       ELSE 'other' END AS event_family,
  (e.event_type = 'measured_voter_shift') AS is_voter_level_evidence
FROM `{DS}.ext_events` AS e
CROSS JOIN last_poll AS lp
ORDER BY COALESCE(e.event_date, e.report_date), e.event_id;
