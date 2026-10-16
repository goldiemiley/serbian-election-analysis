# Research leads: what to obtain, and what it would change

These are the inputs that the forecast needs and does not have. Each one is stated as a task, with the stage it would improve and the file it goes into. Nothing here has been done or assumed: the model currently uses a labelled analyst assumption where an item is missing. Source ids (S01…) refer to `config/cfg_source_register.csv`.

## A. Highest impact on the headline results

| # | Obtain | Why it matters | Goes into | Where to look |
|---|---|---|---|---|
| 1 | **Primary pollster releases** for every poll used (CRTA/DAL, Faktor plus, NSPM, and the Ipsos and Nacija TV polls that S14 says fed the BIRODI model): fieldwork dates, sample, mode, base (all respondents / decided / likely voters), undecided and turnout-intention shares, commissioner | 4 of 5 loaded polls lack fieldwork dates, sample or base. House effects are the largest uncertainty in the aggregate. | `ext_polls` (Stage 5) | The pollsters' own publications; press releases cited in S09, S15, S16 |
| 2 | **Poll cross-tabs**: reported 2023 vote × current intention, or direct "switching" tables | The only legitimate basis for a transition model. Today realignment is a named scenario with a weight chosen by the analyst. **Code to read this table has not been written** (it needs the data to design against). | `ext_poll_transitions` (Stage 5/6) | Pollster technical reports, CRTA/DAL methodology notes |
| 3 | **Past polls matched with results** (the 2022 and 2023 parliamentary elections, and the 2025–2026 local rounds): the last polls before each election by pollster | Lets house effects, the design effect and the election-day miss be *estimated* instead of set as priors (`poll_house_sd_floor`, `poll_design_effect`, `poll_election_error_sd`). Also makes a genuine poll→result backtest possible. | new rows in `ext_polls` plus a result table (Stage 5/12) | Pollster archives; Wikipedia opinion-polling pages (S12) as a lead only |
| 4 | **RIK decisions** on the final collective list and **each list's national-minority status** | The roster and statuses rest on media reports (S05–S07). A status change moves seats (minority lists enter below 3% and with ×1.35). | `cfg_list_registry_2026` (Stage 7/9) | RIK website (S03, "izbori za narodne poslanike 2026" decisions) |
| 5 | **Electoral law in force**: the Law on the Election of MPs with the 2022 and May 2026 amendments, from the Official Gazette | The legal parameters were checked against a 2020 consolidation (S02) and the ODIHR report (S01). Two points are unresolved: the base of the 3% threshold ("voters who voted") and whether the ×1.35 uplift applies to every minority list or only those under the threshold. | `cfg_parameters` (`threshold_denominator`, `minority_uplift_scope`) (Stage 9) | Službeni glasnik; RIK; OSCE/ODIHR final report once published |

## B. Geography and turnout

| # | Obtain | Why | Goes into | Where to look |
|---|---|---|---|---|
| 6 | **Voter register by municipality for 25 Oct 2026** | Replaces national-ratio scaling of the 2023 registers. The national total is only a secondary report (6,450,523; S06). | `ext_register_2026` (Stage 2) | RIK, Ministry of Public Administration and Local Self-Government |
| 7 | **Turnout totals and unit-level list votes for earlier parliamentary elections** (2020, 2016, 2014 …) | Only one national election has turnout totals; the cross-sectional pattern of turnout *change* is not identified, and the backtest has one transition (2022→2023). | new rows in the package tables (Stage 1/2/12) | RIK archives; State Statistical Office |
| 8 | **Diaspora registrations** (about 111,000 are mentioned in an interview, S13) and how they vote | May add an electorate absent from the 2023 baseline; not modelled. | Stage 3 | RIK |
| 9 | **Results of the June 2025 Zaječar and Kosjerić local elections** and of any other municipality with a local election in the last 18 months | Adds cases to a Stage 4 sample of 12. Currently registered in `ext_local_election_registry` but without results. | `election_totals`, `list_votes` (Stage 4) | Local election commissions, RIK-linked results pages (S21) |
| 10 | **Verified classification of local lists** (65 rows in `cfg_local_list_review`): which are student-backed, SNS-led, SPS-led, joint | Local effects are only as good as this classification. 0 of 65 are verified. | `cfg_local_list_review` (Stage 4) | List submitters' own statements, local commissions, reputable press (S12 mentions the Bor list) |

## C. Realignment, events and markets

| # | Obtain | Why | Goes into | Where to look |
|---|---|---|---|---|
| 11 | **Dated, sourced events**: departures from the SPS and other parties, expulsions, endorsements, new organizations, lists withdrawn | The realignment mixture switches on only if events dated after the last poll exist; several loaded rows have only a report date. Departures are not voter switching, and the code keeps them apart. | `ext_events` (Stage 5) | Party statements, N1, Vreme, Danas (S08, S19) |
| 12 | **Prediction-market snapshots captured from the platform** with timestamps, the exact market question and resolution criteria, bid/ask, volume | The loaded quotes are from a news report about the *prime minister* market (S17), and an aggregator page (S10) was internally inconsistent. Validation only. | `ext_markets` (Stage 5) | The platform itself |

## D. Model upgrades once the data exist

* **Estimate house effects** from item 3 and replace the priors in `cfg_parameters`.
* **Read `ext_poll_transitions`** (item 2): replace the transfer moments of the matching rows in `cfg_event_scenarios` with the survey-based Beta moments, and report both.
* **Covariates for turnout and swing** (census, age, education, earnings in `municipality_context_2022` and `context_series`) become identifiable only with several elections of unit-level totals (item 7).
* **Verified family map** (37 rows) and **origin weights** (14 rows): review and set `mapping_status` to reviewed; the readiness matrix will stop flagging them PROVISIONAL.

