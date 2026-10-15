"""BigQuery schemas for the configuration and external-input tables (single source of truth).

cfg_*  tables are rebuilt from config/*.csv on every run (they hold legal parameters, source register,
       the 2026 list roster and the proposed list-family map).
ext_*  tables are created EMPTY and are never overwritten by the pipeline. They hold external observations
       (polls, events, prediction-market snapshots, official mandates, local-election registry) that the
       analyst loads. Nothing in these tables is invented by this project.
"""

CFG_TABLES = {
    'cfg_parameters': [
        ('param_key', 'STRING'), ('param_value', 'STRING'), ('value_type', 'STRING'), ('category', 'STRING'),
        ('description', 'STRING'), ('source', 'STRING'), ('source_date', 'DATE'),
        ('verification_status', 'STRING'), ('used_in_stage', 'STRING')],
    'cfg_source_register': [
        ('source_id', 'STRING'), ('publisher', 'STRING'), ('title', 'STRING'), ('url', 'STRING'),
        ('publication_date', 'DATE'), ('source_type', 'STRING'), ('used_for', 'STRING'),
        ('reliability_note', 'STRING')],
    'cfg_list_registry_2026': [
        ('list_key', 'STRING'), ('list_name_reported', 'STRING'), ('ballot_number_reported', 'INT64'),
        ('submitter_reported', 'STRING'), ('components_stated', 'STRING'), ('minority_status_reported', 'STRING'),
        ('minority_group_reported', 'STRING'), ('signatures_reported', 'INT64'), ('candidates_reported', 'INT64'),
        ('status', 'STRING'), ('source_ids', 'STRING'), ('notes', 'STRING'),
        ('on_final_collective_list', 'STRING'), ('verification_status', 'STRING')],
    'cfg_list_family_map': [
        ('election_id', 'STRING'), ('list_id', 'STRING'), ('list_name_source', 'STRING'), ('family', 'STRING'),
        ('bloc', 'STRING'), ('is_minority_proposed', 'BOOL'), ('minority_group_proposed', 'STRING'),
        ('confidence', 'STRING'), ('mapping_status', 'STRING'), ('basis', 'STRING'), ('review_note', 'STRING')],
    'cfg_local_list_review': [
        ('election_id', 'STRING'), ('local_list_id', 'STRING'), ('geo_id', 'STRING'), ('geo_name', 'STRING'),
        ('list_name_source', 'STRING'), ('coalition_members_documented', 'STRING'),
        ('hint_student_in_name', 'BOOL'), ('hint_youth_in_name', 'BOOL'), ('hint_united_in_name', 'BOOL'),
        ('hint_sns_led_name_pattern', 'BOOL'), ('external_evidence_note', 'STRING'),
        ('verified_family', 'STRING'), ('verified_bloc', 'STRING'), ('verification_source_url', 'STRING'),
        ('verified_by', 'STRING'), ('verified_date', 'DATE'), ('review_status', 'STRING')],
    'cfg_required_columns': [
        ('table_name', 'STRING'), ('column_name', 'STRING'), ('needed_by', 'STRING')],
    # Geography of each 2026 list: which 2023 families (votes per registered voter) its unit-level pattern follows.
    # These weights shape WHERE a list's votes fall; the national LEVEL is calibrated to the poll-based target.
    'cfg_origin_weights': [
        ('list_key', 'STRING'), ('origin', 'STRING'), ('weight', 'FLOAT64'), ('mapping_status', 'STRING'), ('note', 'STRING')],
    'cfg_minority_roster_map': [
        ('list_key', 'STRING'), ('minority_group', 'STRING'), ('analog_family', 'STRING'), ('role', 'STRING'),
        ('unit_pattern', 'STRING'), ('mapping_status', 'STRING'), ('note', 'STRING')],
    # Named political-event scenarios. 'param' values are SCENARIO definitions chosen by the analyst, not estimates.
    'cfg_event_scenarios': [
        ('scenario_id', 'STRING'), ('scenario_name', 'STRING'), ('in_baseline_mixture', 'BOOL'), ('baseline_weight', 'FLOAT64'),
        ('trigger_origin_entity', 'STRING'), ('param', 'STRING'), ('from_list_key', 'STRING'), ('to_list_key', 'STRING'),
        ('value', 'FLOAT64'), ('description', 'STRING'), ('status', 'STRING')],
    'cfg_coalitions': [
        ('coalition_id', 'STRING'), ('coalition_name', 'STRING'), ('members', 'STRING'), ('anchor', 'STRING'),
        ('plausibility_assumption_set', 'STRING'), ('plausibility', 'STRING'), ('evidence', 'STRING'), ('status', 'STRING')],
}

EXT_TABLES = {
    'ext_polls': [
        ('poll_id', 'STRING'), ('pollster', 'STRING'), ('commissioned_by', 'STRING'),
        ('fieldwork_start', 'DATE'), ('fieldwork_end', 'DATE'), ('publication_date', 'DATE'),
        ('sample_size', 'INT64'), ('population_base', 'STRING'), ('mode', 'STRING'),
        ('undecided_share', 'FLOAT64'), ('turnout_intention_share', 'FLOAT64'),
        ('list_key', 'STRING'), ('list_label_reported', 'STRING'), ('share', 'FLOAT64'), ('share_base', 'STRING'),
        ('reported_margin_of_error', 'FLOAT64'), ('methodology_notes', 'STRING'),
        ('source_url', 'STRING'), ('retrieved_date', 'DATE'), ('verification_status', 'STRING')],
    'ext_events': [
        ('event_id', 'STRING'), ('event_date', 'DATE'), ('report_date', 'DATE'), ('event_type', 'STRING'),
        ('actor_name', 'STRING'), ('actor_role', 'STRING'), ('origin_entity', 'STRING'),
        ('destination_entity', 'STRING'), ('geo_id', 'STRING'), ('scope', 'STRING'),
        ('source_url', 'STRING'), ('source_name', 'STRING'), ('confidence', 'STRING'), ('notes', 'STRING')],
    'ext_markets': [
        ('observation_id', 'STRING'), ('observed_at', 'TIMESTAMP'), ('platform', 'STRING'),
        ('market_id', 'STRING'), ('market_question', 'STRING'), ('outcome_label', 'STRING'),
        ('price', 'FLOAT64'), ('bid', 'FLOAT64'), ('ask', 'FLOAT64'), ('volume_usd', 'FLOAT64'),
        ('liquidity_usd', 'FLOAT64'), ('resolution_criteria', 'STRING'), ('source_url', 'STRING'),
        ('notes', 'STRING')],
    'ext_mandates': [
        ('election_id', 'STRING'), ('list_id', 'STRING'), ('mandates_official', 'INT64'),
        ('source_url', 'STRING'), ('retrieved_date', 'DATE'), ('verification_status', 'STRING')],
    'ext_local_election_registry': [
        ('geo_id', 'STRING'), ('election_date', 'DATE'), ('election_type', 'STRING'),
        ('results_in_dataset', 'BOOL'), ('source_url', 'STRING'), ('notes', 'STRING')],
    # Poll cross-tabs / measured transitions: the ONLY legitimate input for the voter-transition model (Stage 6).
    'ext_poll_transitions': [
        ('poll_id', 'STRING'), ('origin_family', 'STRING'), ('origin_basis', 'STRING'),
        ('destination_list_key', 'STRING'), ('share_of_origin', 'FLOAT64'), ('origin_base_n', 'INT64'),
        ('source_url', 'STRING'), ('retrieved_date', 'DATE'), ('notes', 'STRING')],
    # Municipal registers for 25 Oct 2026, if the analyst obtains them (RIK / Ministry). Overrides national scaling.
    'ext_register_2026': [
        ('geo_id', 'STRING'), ('register_date', 'DATE'), ('registered_voters', 'INT64'),
        ('source_url', 'STRING'), ('retrieved_date', 'DATE'), ('notes', 'STRING')],
}

# Natural keys used when the analyst imports CSV files into ext_* tables (upsert: new rows replace rows with the same key).
EXT_KEYS = {
    'ext_polls': ['poll_id', 'list_key'], 'ext_events': ['event_id'], 'ext_markets': ['observation_id'],
    'ext_mandates': ['election_id', 'list_id'], 'ext_local_election_registry': ['geo_id', 'election_date'],
    'ext_poll_transitions': ['poll_id', 'origin_family', 'destination_list_key'], 'ext_register_2026': ['geo_id', 'register_date'],
}

# Controlled vocabulary for ext_events.event_type. Keeping departures, joinings, endorsements and measured
# voter shifts as DIFFERENT event types is what stops them being treated as equivalent (task section 5).
EVENT_TYPES = ['left_party', 'expelled', 'joined_organization', 'endorsed_list', 'list_withdrawn',
               'list_proclaimed', 'new_party_announced', 'measured_voter_shift', 'other']
