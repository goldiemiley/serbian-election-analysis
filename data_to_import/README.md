# data_to_import — manual external inputs

**Everything in this folder is a manual import.** None of it comes from the BigQuery package. The files were compiled on 2026-10-14 from secondary media reports (see `config/cfg_source_register.csv`, ids S08–S21) and they are *starting points to review*, not authoritative data. Each row says where it came from and how reliable it is (`verification_status`, `source_url`). Where a field was not stated in the source it is left empty — it was not filled in.

| File | Rows | Loads into | What it holds | Reliability |
|---|---:|---|---|---|
| `ext_polls_2026.csv` | 18 (5 polls, 3 pollsters) | `ext_polls` | Shares by list from CRTA/DAL (fieldwork 10–24 Jun, n = 2,324), Faktor plus (two releases), NSPM (two releases) | Media reports of pollster releases. Fieldwork dates, sample sizes and bases are partly or mostly missing for 4 of 5 polls. Commissioners not disclosed. |
| `ext_events_2026.csv` | 17 | `ext_events` | SPS departures and expulsions, endorsements of the student list, list proclamations and one withdrawal | Media reports. `event_date` is empty for several departures, so their `report_date` (when the press reported them) is used as the reference date. `confidence` is the source's, not a verification. |
| `ext_markets_2026.csv` | 8 | `ext_markets` | Four Polymarket snapshots of the *next prime minister* market on 2026-09-18 | Not a market on the election result; the swings between snapshots (30–40 points within a day) show a thin market. **Validation only — never a model input.** |
| `ext_local_election_registry.csv` | 2 | `ext_local_election_registry` | Zaječar and Kosjerić regular local elections of 2025-06-08 | The elections are documented; their results are **not** in the package. |
| `ext_mandates_2023.csv` | 18 | `ext_mandates` | Official December 2023 seat distribution (sums to 250) | Media report of the State Election Commission's final results; used only to test the seat-allocation code against a known outcome. |
| `templates/*.csv` | header only | – | Empty files with the right columns for `ext_poll_transitions` and `ext_register_2026`, and for the five above | – |

## How to use

* **Notebook.** `IMPORT_EXTERNAL = True` (the default) upserts these five files into the `ext_*` tables at Stage 5. `False` leaves the tables as they are.
* **From code.** `pipeline.import_external_csv(be, 'ext_polls', 'data_to_import/ext_polls_2026.csv')`. Upsert on the natural key (`config_schemas.EXT_KEYS`; polls: `poll_id` + `list_key`). `replace_all=True` discards the table first.
* **Never automatic.** `ext_*` tables are created empty if missing and are never overwritten by the pipeline.

## Adding or correcting data

1. **Polls.** One row per poll × list. Required for use: `poll_id`, `pollster`, a date (`fieldwork_end` preferred; `publication_date` is used only to order polls and is flagged as a proxy), `list_key` (must match `cfg_list_registry_2026`), `share` as a proportion of the base named in `share_base`. Add `sample_size` whenever the pollster reports it; otherwise the model uses `poll_default_sample` and flags it. Load **pollster releases, not derived models** (the BIRODI scenario model, source S14, was deliberately not loaded: it is built from the same polls and would double count).
2. **Events.** Choose `event_type` from the controlled vocabulary in `config_schemas.EVENT_TYPES` — a member leaving a party, joining an organization, endorsing a list and a measured voter shift are different types and are never treated as equivalent. Give `origin_entity` (it must match `trigger_origin_entity` in `cfg_event_scenarios`, e.g. `SPS`; an endorsement row with no `origin_entity` never triggers anything) and `event_date`. The reference date of an event is `event_date`, else `report_date`; an event with neither can never trigger. The realignment mixture switches on only if an activation-type event (`event_activation_types`) is dated *after* the last poll.
3. **Markets.** One row per observation with `observed_at` (timestamp), platform, the exact market question and resolution criteria, price, and bid/ask/volume if available. Capture from the platform, not from aggregator pages.
4. **Transitions** (`ext_poll_transitions`): origin family (or origin basis), destination list, share of the origin base, base size, poll id. **The pipeline does not read this table yet** (see `ARCHITECTURE.md` §4). It is checked by the readiness matrix.
5. **Municipal registers** (`ext_register_2026`): `geo_id`, `register_date`, `registered_voters`. Stage 2 uses them in place of national-ratio scaling for the units provided.
6. After any change, re-run the notebook from Stage 0; `s0_readiness_matrix` shows what the new data changed.

## Verification status

`ext_polls` and `ext_mandates` carry a free-text `verification_status` (`secondary_media_report…`, `tertiary_compilation…`, or `implied_zero…` for the seat count of a list not among the winners). `ext_events` carries `confidence`, `source_url` and `notes`; `ext_markets` and the registry carry `source_url` and `notes`. **Nothing here is verified against a primary source.** To verify a row, open the primary source (pollster release, RIK / State Election Commission publication, platform page), correct the values, and set `verification_status` to `verified_primary` (polls, mandates) or add the primary URL and a note (the other files).
