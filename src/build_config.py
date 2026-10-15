"""Builds config/*.csv (provenance script; the CSVs are the editable source of truth).

Everything written here is either
  * a legal parameter with its source and a verification_status,
  * a scenario assumption supplied by the user,
  * an analyst choice (labelled as such), or
  * a PROPOSED classification that carries mapping_status = 'proposed_unreviewed'.
Nothing here is an election result, a poll value, a market price or a vote-transfer percentage.

Usage:  python3 -I build_config.py /path/to/serbia_bigquery
(the package path is only needed to enumerate list ids / names for the family map and the local-list review).
"""
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'config'
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------------------------- parameters
P = [
    # key, value, type, category, description, source, source_date, verification, used_in_stage
    ('election_target_date', '2026-10-25', 'date', 'legal_calendar',
     'Date of the early parliamentary election being forecast.',
     'Balkan Insight 2026-09-09 (decree 9 Sep 2026); ODIHR EOM page', '2026-09-09', 'verified_multiple_sources', '0-13'),
    ('seats_total', '250', 'int', 'legal', 'Number of MPs elected.',
     'Law on Election of MPs Art.3; ODIHR NAM report 2026-07-30 p.8', '2026-07-30', 'verified_primary', '9-13'),
    ('national_single_electoral_unit', 'true', 'bool', 'legal', 'Whole country is one electoral unit.',
     'Law Art.4; ODIHR NAM 2026-07-30', '2026-07-30', 'verified_primary', '9'),
    ('majority_seats', '126', 'int', 'legal', 'Seats needed for a majority: floor(seats_total/2)+1.',
     'Derived', '2026-10-14', 'derived', '10'),
    ('threshold_share', '0.03', 'float', 'legal', 'Ordinary participation threshold.',
     'Law Art.81(1); ODIHR NAM p.8', '2026-07-30', 'verified_primary', '9'),
    ('threshold_denominator', 'voters_turned_out', 'enum:voters_turned_out|ballots_cast|valid_ballots', 'legal',
     'Base of the 3% test. Art.81 says 3% of the votes "of the total number of voters who voted". Art.74/85 list '
     '"voters who voted" separately from used ballots and valid ballots, which maps to dataset column '
     'voters_turned_out. HOW THE RIK APPLIES IT IN PRACTICE WAS NOT VERIFIED; the pipeline runs all three.',
     'Law Art.74,81,85 (2020 consolidated text); RIK and CRTA explainers', '2026-10-14',
     'legal_text_reading__practice_unverified', '9'),
    ('minority_quotient_multiplier', '1.35', 'float', 'legal',
     'Quotients of national-minority lists are multiplied by 1.35 in the largest-quotient calculation.',
     'Law Art.81(2); RIK and CRTA explainers', '2026-10-14', 'verified_primary', '7,9'),
    ('minority_uplift_scope', 'all_minority', 'enum:all_minority|below_threshold_only', 'legal',
     'Statutory wording uplifts the quotients of ALL minority lists; official explainers describe the uplift for '
     'minority lists under 3%. Outcomes differ only if a minority list reaches 3%.',
     'Law Art.81(2) vs RIK explainer', '2026-10-14', 'wording_ambiguity__sensitivity', '9'),
    ('tie_break', 'larger_total_votes', 'enum', 'legal', 'Equal quotients on the last seat: more total votes wins.',
     'Law Art.82(4)', '2026-10-14', 'verified_primary', '9'),
    ('fallback_if_no_list_reaches_threshold', 'true', 'bool', 'legal',
     'If no list reaches 3%, all lists with votes take part.', 'Law Art.82(5)', '2026-10-14', 'verified_primary', '9'),
    ('minority_status_decider', 'RIK_decision_per_list', 'text', 'legal',
     'Minority status is decided by the RIK per list at proclamation; May 2026 amendments specify the criteria. '
     'It is an INPUT (cfg_list_registry_2026), never inferred from votes.',
     'Law Art.81(3-4); ODIHR NAM 2026-07-30 pp.15-16', '2026-07-30', 'verified_primary', '7,9'),
    ('register_total_2026', '6450523', 'int', 'observed_external',
     'Voters in the register for 25 Oct 2026, as reported from the RIK decision.',
     'Danas 2026-10-09 (reports RIK decision)', '2026-10-09',
     'secondary_media_report_of_RIK_decision__verify_in_Sluzbeni_glasnik', '2,3'),
    ('register_total_odihr_july', '6439075', 'int', 'observed_external',
     'Register size given to ODIHR NAM by the Ministry in July 2026. Information only.',
     'ODIHR NAM 2026-07-30 p.3', '2026-07-30', 'verified_primary', '2'),
    ('turnout_voters_low', '4300000', 'int', 'user_scenario',
     'USER-SPECIFIED participating voters, lower end. Scenario assumption, not a verified prediction.',
     'User instruction', '2026-10-14', 'user_assumption', '3,11'),
    ('turnout_voters_high', '4400000', 'int', 'user_scenario',
     'USER-SPECIFIED participating voters, upper end. Scenario assumption, not a verified prediction.',
     'User instruction', '2026-10-14', 'user_assumption', '3,11'),
    ('register_scaling_mode', 'national_ratio', 'enum:national_ratio', 'analyst_choice',
     'Municipal 2026 registers are NOT in the data (only the national total). Each 2023 unit register is scaled by '
     'register_total_2026 / 2023 national register. Sensitivity: the 13 sample municipalities show a larger register '
     'decline than the national ratio, so unit-level drift is uncertain.',
     'Analyst choice', '2026-10-14', 'analyst_choice', '2,3'),
    ('special_electorate_mode', 'hold_2023_attendance', 'enum:hold_2023_attendance', 'analyst_choice',
     'Abroad (33000) and institutions (55001) are held at 2023 attendance in turnout calibration. Reports suggest '
     'diaspora registration for 2026 is far higher than 2023 attendance abroad (unverified); replace once '
     'RIK special-register data are loaded.', 'Analyst choice', '2026-10-14', 'analyst_choice', '3'),
    ('fixed_rate_region_ids', 'RS23', 'csv', 'analyst_choice',
     'territories.region_id values whose 2023 turnout RATE is held fixed in calibration (RS23 = Kosovo i Metohija: '
     'displaced-voter registers, 2023 turnout 3-33%).', 'Derived from territories + 2023 turnout', '2026-10-14',
     'derived_from_data', '0,2,3'),
    ('recent_local_max_age_months', '18', 'int', 'analyst_choice',
     'A municipality has a recent local election if it was held at most this many months before the target date. '
     'Sensitivity run required.', 'Analyst choice (not a legal or empirical quantity)', '2026-10-14',
     'analyst_choice', '0,4'),
    ('national_election_prefix', 'parliamentary_', 'text', 'data_policy',
     'election_id prefix identifying national parliamentary elections in the package.',
     'Package convention (README)', '2026-10-14', 'derived_from_data', '0,1'),
    ('min_national_elections_for_backtest', '3', 'int', 'analyst_choice',
     'National elections with turnout, list votes and mandates needed to claim a meaningful backtest.',
     'Analyst standard', '2026-10-14', 'analyst_choice', '0,12'),
    ('share_sum_tolerance', '0.000001', 'float', 'data_policy', 'Tolerance for vote shares summing to 1.',
     'Analyst choice', '2026-10-14', 'analyst_choice', '0,1'),
    ('random_seed', '20261014', 'int', 'simulation', 'Master seed for stochastic steps (spawned per component).',
     'Analyst choice', '2026-10-14', 'analyst_choice', '11'),
]
pd.DataFrame(P, columns=['param_key', 'param_value', 'value_type', 'category', 'description', 'source',
                         'source_date', 'verification_status', 'used_in_stage']).to_csv(OUT / 'cfg_parameters.csv', index=False)

# ------------------------------------------------------------------------------------------- source register
S = [
    ('S01', 'OSCE/ODIHR', 'Republic of Serbia, Anticipated Early Elections 2026: Needs Assessment Mission Report',
     'https://odihr.osce.org/sites/default/files/documents/official_documents/2026/07/SRB%202026%20forthcoming%20elections%20NAM%20report_30.07.2026.pdf',
     '2026-07-30', 'primary', '250 seats; 3% threshold; May 2026 amendments (minority-list criteria, multi-list signatures); register 6,439,075; local elections of 29 Mar 2026 in 10 municipalities with reported irregularities',
     'Authoritative on the legal framework; written before the election was called.'),
    ('S02', 'Propisi.net', 'Zakon o izboru narodnih poslanika (consolidated text through 68/2020)',
     'https://www.propisi.net/zakon-o-izboru-narodnih-poslanika/', '2020-05-11', 'legal_text_secondary_host',
     'Art. 3, 4, 74, 78, 81, 82, 85 wording',
     '2020 consolidation. The 2022 law and the May 2026 amendments were NOT article-checked. Verify in Sluzbeni glasnik / RIK.'),
    ('S03', 'RIK', 'O izborima za narodne poslanike', 'https://www.rik.parlament.gov.rs/tekst/sr/77/o-izborima-za-narodne-poslanike.php',
     '', 'primary_explainer', '3% threshold; +35% minority uplift wording', 'Undated explainer.'),
    ('S04', 'Balkan Insight', "Serbia's Vucic Calls Early Parliamentary Elections for October 25",
     'https://balkaninsight.com/2026/09/09/serbias-vucic-calls-early-parliamentary-elections-for-october-25/bi/',
     '2026-09-09', 'news', 'Election date and call', 'Reputable regional outlet.'),
    ('S05', 'Danas', 'Izborne liste: Spisak proglasenih lista i kandidata za izbore 25. oktobra',
     'https://www.danas.rs/vesti/politika/konacne-izborne-liste-izbori-2026-spisak/', '2026-10-06', 'news_citing_RIK',
     '18 lists, 9 minority; names, submitters, signature counts',
     'Secondary. Ballot numbers beyond #1-#3 are inconsistent across reports. Verify against the RIK collective list.'),
    ('S06', 'Danas', 'RIK proglasio 18 izbornih lista (collective list adopted; register 6,450,523)',
     'https://www.danas.rs/vesti/politika/izbori26/rik-proglasio-18-izbornih-lista/', '2026-10-09', 'news_citing_RIK',
     'Final 18-list count; register total', 'Secondary report of a RIK decision.'),
    ('S07', 'Beta', 'RIK proglasio izbornu listu Studentska lista - studenti pobedjuju i jos dve manjinske liste',
     'https://beta.rs/content/252117-rik-proglasio-izbornu-listu-studentska-lista--studenti-pobedjuju', '2026-09-15', 'news',
     'Student List is a separate, non-minority list proclaimed in the same session as two minority lists (Ljajic SDP-CDP, SVM); 69,099 valid signatures',
     'Resolves an ambiguous RTV snippet that seemed to give the Student List minority status. RTV page could not be fetched (robots), so it was not read directly.'),
    ('S08', 'Vreme / Naslovi.net / 021.rs / Razglas / Ozonpress', 'SPS departures: Ruzic expelled (late Aug); local officials in Sabac, Pozega, Smederevo (late Sep); 13 Rakovica members (9 Oct); Milicevic (12 Oct); Djokovic (c.12 Oct)',
     'https://vreme.com/vesti/nastavlja-se-okrsaj-u-sps-u-ko-je-sve-otisao-za-ruzicem/', '2026-10-09', 'news',
     'Event-log leads for ext_events', 'Departures and endorsements are NOT measures of voter switching.'),
    ('S09', 'Danas / Vreme / 021.rs / N1', 'Polls (CRTA decided voters, NSPM, Faktor plus) and the BIRODI scenario model',
     'https://www.danas.rs/vesti/politika/studenti-glasaci-istrazivanje-javnog-mnjenja/', '2026-07-25', 'news_citing_polls',
     'Poll leads only. Fieldwork dates, sample sizes and methods NOT captured.',
     'Pollster divergence is very large. Primary pollster releases are required before any use.'),
    ('S10', 'lines.com (aggregator)', 'Prediction market page: will Vucic - United Serbia win the Serbian parliamentary election',
     'https://www.lines.com/prediction-markets/politics/global-elections/serbia-parliamentary-election-winner-2026',
     '2026-09-23', 'aggregator', 'Market existence and volume lead',
     'Internally inconsistent figures (65.0% vs about 58.5%) and about three weeks old. NOT usable as data; capture from the platform with timestamps.'),
    ('S11', 'Slobodna Evropa / N1 / CRTA', 'Local elections of 30 Nov 2025 in Mionica, Negotin, Secanj (Zajecar and Kosjeric earlier in 2025)',
     'https://www.slobodnaevropa.org/a/izbori-negotin-mionica-secanj/33609135.html', '2025-12-01', 'news',
     'Nov 2025 cohort is exactly 3 municipalities; Zajecar and Kosjeric (about 5 months earlier) are absent from the package',
     'Coverage-gap evidence.'),
    ('S12', 'Wikipedia', '2026 Serbian local elections; 2023 and 2024 local elections; Next Serbian parliamentary election',
     'https://en.wikipedia.org/wiki/2026_Serbian_local_elections', '2026-10-14', 'tertiary',
     'Bor list supported by the Student Movement; same-day local elections in 65 municipalities on 17 Dec 2023; a June 2024 round',
     'Orientation only; verify with RIK / local commissions.'),
    ('S13', 'N1', 'Koji je prag izlaznosti na kom se moze ocekivati promena (SPS, Evropska Srbija i Autenticna desnica se bore za cenzus)',
     'https://n1info.rs/vesti/koji-je-prag-izlaznosti-na-kom-se-moze-ocekivati-promena-sps-evropska-srbija-i-autenticna-desnica-se-bore-za-cenzus/',
     '2026-10-12', 'news', 'Threshold framed as roughly 130-135k votes; about 111,000 registrations for voting abroad (as stated in an interview)',
     'Commentary / interview. Context only; the diaspora figure is unverified.'),
    ('S14', 'N1 (BIRODI)', 'BIRODI model puts the student list at 48.5 percent ahead of the SNS (analytical model of 2026-08-30)',
     'https://n1info.rs/english/news/birodi-model-puts-serbias-student-list-at-485-percent-ahead-of-vucics-sns/', '2026-08-30', 'derived_model',
     'Model combining RIK results and CRTA, NSPM, Faktor plus, Nacija TV and Ipsos polls; 4.132 million voters assumed',
     'A DERIVED product of the same polls: NOT loaded into ext_polls (would double count). Described by its authors as a scenario, not a forecast.'),
    ('S15', 'N1', 'CRTA/DAL poll published 2026-07-15 (fieldwork 10-24 June 2026, n = 2,324, face-to-face)',
     'https://n1info.rs/vesti/crta-istrazivanje-izbori-studentska-lista-sns/', '2026-07-15', 'news_citing_poll', 'ext_polls crta_2026_06', 'Metadata partly missing in the article.'),
    ('S16', '021.rs / Mondo / Beta (Nova.rs) / N1', 'Faktor plus (4 Sep and 16-20 Sep 2026) and NSPM (July and early September 2026) poll reports',
     'https://mondo.rs/Info/Politika/a2284943/novo-istrazivanje-o-rejtinzima-stranaka-pred-izbore-2026.html', '2026-09-21', 'news_citing_poll',
     'ext_polls faktorplus_2026_09a/b, nspm_2026_07, nspm_2026_09', 'Commissioners not disclosed; pollster independence is disputed in the press (not a finding of this project).'),
    ('S17', 'N1', 'Polymarket: Srdanovic overtakes Vucic (market on the next prime minister, 18 Sep 2026)',
     'https://n1info.rs/english/news/ilija-srdanovic-overtakes-aleksandar-vucic-on-polymarket-prediction-platform/', '2026-09-19', 'news_citing_market',
     'ext_markets rows pm_pm_20260918_*', 'Not a market on the election result; intraday swings of 30-40 points indicate a thin market. Validation only.'),
    ('S18', 'Radio Slobodna Evropa', 'Skupstina Srbije raspravlja o izboru nove vlade (SPS said it will support the new government)',
     'https://www.slobodnaevropa.org/a/33385634.html', '2025-04-15', 'news', 'cfg_coalitions C02 evidence', 'Debate coverage; vote count not given on the page.'),
    ('S19', 'Vreme / N1 (FoNet)', 'SPS departures, Ruzic expulsion and endorsement, Milicevic departure',
     'https://n1info.rs/vesti/boris-milicevic-napustio-sps/', '2026-10-12', 'news', 'ext_events E002-E014', 'Distinguishes leaving a party, joining an organization and endorsing a list.'),
    ('S20', 'tportal.hr', 'Final seat distribution of the December 2023 election (State Election Commission)',
     'https://www.tportal.hr/vijesti/clanak/drzavno-izborno-povjerenstvo-potvrdilo-pobjedu-vuciceva-sns-a-foto-20240112', '2024-01-12', 'news_citing_commission',
     'ext_mandates_2023.csv; used to validate the seat-allocation module', 'Secondary report of official results; the seats sum to 250.'),
    ('S21', 'Vreme', 'Regular local elections in Zajecar and Kosjeric, 8 June 2025 (live blog)',
     'https://vreme.com/vesti/blog-redovni-lokalni-izbori-u-zajecaru-i-kosjericu/', '2025-06-08', 'news', 'ext_local_election_registry', 'Results are not in the package.'),
]
pd.DataFrame(S, columns=['source_id', 'publisher', 'title', 'url', 'publication_date', 'source_type', 'used_for',
                         'reliability_note']).to_csv(OUT / 'cfg_source_register.csv', index=False)

# ------------------------------------------------------------------------------------- 2026 list roster
R = [
    # key, name, ballot#, submitter, components, minority, group, signatures, candidates, status, sources, notes
    ('aleksandar_vucic_ujedinjena_srbija', 'Aleksandar Vučić – Ujedinjena Srbija', 1, 'Srpska napredna stranka (SNS)', '', 'no', '', None, 250, 'proclaimed', 'S05;S06', 'SNS-led list. Ballot #1 consistently reported.'),
    ('ivica_dacic_faktor_stabilnosti', 'Ivica Dačić – Faktor stabilnosti', 2, 'SPS-led coalition', 'SPS; Jedinstvena Srbija; SDPS; Zeleni Srbije', 'no', '', None, 250, 'proclaimed', 'S05;S06', 'Ballot #2 consistently reported.'),
    ('studentska_lista', 'Studentska lista – Studenti pobeđuju', 3, 'Student movement list (list carrier: Ilija Srdanović)', '', 'no', '', 69099, 250, 'proclaimed', 'S05;S07', 'Ballot #3. NOT a minority list (S07). Endorsed by some parties; endorsements are not captured here.'),
    ('rasim_ljajic_ljudski', 'Rasim Ljajić – Ljudski (SDP – CDP)', 4, 'SDP / CDP coalition', 'SDP; CDP', 'yes', 'not stated in sources', None, 250, 'proclaimed', 'S05;S07', 'Described as a minority list (S07). Group not stated; verify the RIK decision.'),
    ('svm_pastor', 'Savez vojvođanskih Mađara – dr Balint Pastor', None, 'SVM', '', 'yes', 'Hungarian', 9531, None, 'proclaimed', 'S05;S07', 'Described as a minority list (S07). Verify the RIK decision.'),
    ('usame_zukorlic_pokret_za_ujedinjenje', 'Usame Zukorlić – Pokret za ujedinjenje', None, 'SPP', '', 'yes', 'Bosniak', 6182, 121, 'proclaimed', 'S05', 'Signatures exceed the 5,000 required for minority lists.'),
    ('ruska_stranka_srbija_u_briksu', 'Ruska stranka – Srbija u Briksu – Slobodan Nikolić', None, 'Ruska stranka', '', 'yes', 'Russian', 5101, 25, 'proclaimed', 'S05', 'Competes with a second Russian-minority list (below).'),
    ('autenticna_desnica', 'Autentična desnica – Miloš Jovanović', None, 'NDSS; Monarhisti', 'NDSS; Monarhisti', 'no', '', 10436, 250, 'proclaimed', 'S05', ''),
    ('evropska_srbija', 'Evropska Srbija – Marinika Tepić – Zdravko Ponoš', None, 'SSP; Srbija centar; Građanski pokret Solidarnost', 'SSP; Srbija centar – SRCE; Solidarnost – Samoodbrana – Oslobođenje', 'no', '', None, 246, 'proclaimed', 'S05', ''),
    ('sda_sandzaka_cuvari_sandzaka', 'SDA Sandžaka – čuvari Sandžaka', None, 'SDA Sandžaka', '', 'yes', 'Bosniak', 5910, 35, 'proclaimed', 'S05', 'RIK stated to have determined minority-list status (per Danas).'),
    ('bogoljub_karic_pss_bk', 'Bogoljub Karić – Pokret snaga Srbije – BK', None, 'PSS', '', 'no', '', 10603, 250, 'proclaimed', 'S05', ''),
    ('liberalno_zelena_stranka', 'Liberalno zelena stranka – za slobodnu i čistiju Srbiju', None, 'LZS', '', 'no', '', 10580, 45, 'proclaimed', 'S05', ''),
    ('biram_pravdu_biram_buducnost', 'Biram pravdu, biram budućnost – koalicija snaga', None, 'Stranka budućnosti i razvoja; Građanska stranka Grka Srbije', 'Ferid Bulić; Vasilios Proveleggios coalition', 'yes', 'Bosniak; Greek', None, 22, 'proclaimed', 'S05', 'Bosniak and Greek minority coalition per Danas.'),
    ('stranka_rusko_srpskog_jedinstva', 'Stranka rusko-srpskog jedinstva – Rusi i Srbi braća zauvek', None, 'SRSJ (newly founded)', '', 'yes', 'Russian', None, 15, 'proclaimed', 'S05', 'Second Russian-minority list.'),
    ('cale_ovo_je_za_tebe', 'Grupa građana „Ćale, ovo je za tebe“ – Petar Đurić', None, 'Citizens group', '', 'no', '', None, None, 'proclaimed', 'S05', 'Ballot position reported inconsistently.'),
    ('alternativa_za_srbiju', 'Vladimir Gajić – Alternativa za Srbiju – Narodna stranka, Bunt – prava Srbija', None, 'Narodna stranka; Bunt – Prava Srbija', 'Narodna stranka; Bunt – Prava Srbija', 'no', '', None, 50, 'proclaimed', 'S05', ''),
    ('albanska_koalicija', 'Albanska koalicija – Koalicioni Shqiptar', None, 'Albanian parties coalition', 'PDD; Alternativa za promene; DP; DPA; Pokret za demokratski proces; Pokret za reforme; Demokratska unija Albanaca', 'yes', 'Albanian', None, 10, 'proclaimed', 'S05', ''),
    ('majka_srbija_gruda', 'Majka Srbija – Gruda', None, 'Slovak minority list', '', 'yes', 'Slovak', None, 28, 'proclaimed', 'S05', ''),
    ('izbor_naroda_withdrawn', 'Izbor naroda – Miki Aleksić – Miloš Parandilović – Aleksandar Jovanović Ćuta', None, 'NPS; Novo lice Srbije; Pokret Ekološki ustanak', 'NPS; Novo lice Srbije; Ekološki ustanak', 'no', '', None, None, 'withdrawn', 'S05', 'Proclaimed 18 Sep, withdrawal notified 22 Sep, RIK noted it 24 Sep. NOT on the ballot.'),
]
reg = pd.DataFrame(R, columns=['list_key', 'list_name_reported', 'ballot_number_reported', 'submitter_reported', 'components_stated',
                               'minority_status_reported', 'minority_group_reported', 'signatures_reported', 'candidates_reported',
                               'status', 'source_ids', 'notes'])
reg['on_final_collective_list'] = reg.status.map({'proclaimed': 'reported_consistent_count_18', 'withdrawn': 'no'})
reg['verification_status'] = 'secondary_media_report__verify_against_RIK_collective_list_and_minority_decisions'
for c in ('ballot_number_reported', 'signatures_reported', 'candidates_reported'):
    reg[c] = reg[c].astype('Int64')
assert (reg.status == 'proclaimed').sum() == 18 and ((reg.status == 'proclaimed') & (reg.minority_status_reported == 'yes')).sum() == 9
reg.to_csv(OUT / 'cfg_list_registry_2026.csv', index=False)

# --------------------------------------------------------------------------- model priors and scenario tables
# Everything below is an ANALYST ASSUMPTION or a scenario definition. None is estimated from data unless the description says so.
PRIOR = 'analyst_prior__not_estimated_from_data'
MP = [
    ('poll_reference_list_key', 'aleksandar_vucic_ujedinjena_srbija', 'text', 'poll_model', 'Denominator list for the log-ratio coordinates (any list works; results are invariant to the choice).', 'Analyst choice', 'analyst_choice', '5'),
    ('poll_target_list_keys', 'studentska_lista;ivica_dacic_faktor_stabilnosti;evropska_srbija;autenticna_desnica', 'csv;', 'poll_model', 'Lists modelled from polls (log-ratio to the reference). Lists polled in too few polls are still included; their posterior is then prior-dominated and flagged.', 'Analyst choice', 'analyst_choice', '5,6'),
    ('poll_share_base_assumption', 'decided_voters', 'text', 'poll_model', 'All reported shares are treated as shares of decided voters (log-ratios are insensitive to the base as long as it is common across lists within a poll).', 'Analyst choice; base is stated for only two of five polls', 'analyst_choice', '5'),
    ('poll_design_effect', '2.0', 'float', 'poll_model', 'Variance inflation for sampling error of quota/clustered surveys. Sensitivity 1.0-4.0.', 'Analyst prior', PRIOR, '5'),
    ('poll_default_sample', '1000', 'int', 'poll_model', 'Sample size used ONLY where the source does not state it (variance is not otherwise inflated for that).', 'Analyst prior', PRIOR, '5'),
    ('poll_house_sd_floor', '0.15', 'float', 'poll_model', 'Lower bound for the SD of pollster effects on the log-ratio scale. The pipeline uses max(this, between-house SD of the loaded polls).', 'Analyst prior', PRIOR, '5'),
    ('poll_rw_sd_per_day', '0.004', 'float', 'poll_model', 'Daily SD of real opinion movement on the log-ratio scale (about 0.024 over 35 days).', 'Analyst prior', PRIOR, '5'),
    ('poll_election_error_sd', '0.10', 'float', 'poll_model', 'SD of a polling miss shared by all houses on election day (log-ratio scale). Not estimated: no past poll-vs-result pairs are in the dataset. Sensitivity 0.05-0.20.', 'Analyst prior', PRIOR, '5,11'),
    ('poll_prior_sd', '2.0', 'float', 'poll_model', 'Prior SD of log-ratio levels (very weak).', 'Analyst prior', PRIOR, '5'),
    ('other_nonminority_share_median', '0.02', 'float', 'closure', 'Median combined share of non-minority lists that no poll reports separately (their share is carved out before the polled lists are scaled).', 'Analyst prior; the Faktor plus 16-20 Sep poll leaves 3.0 percent for all lists it does not name, minority lists included', PRIOR, '6,8'),
    ('other_nonminority_share_sdlog', '0.5', 'float', 'closure', 'Log-SD of that combined share.', 'Analyst prior', PRIOR, '6,8'),
    ('unit_turnout_sd_multiplier', '1.0', 'float', 'turnout', 'Multiplier on the unit-level turnout dispersion estimated from the 2022-2023 change in valid votes (a lower bound for a longer interval).', 'Analyst prior', PRIOR, '2,3'),
    ('turnout_grid_points', '21', 'int', 'turnout', 'Number of national-turnout grid points used to map participating voters to ballots and valid ballots (linear interpolation) in the national draws.', 'Computation setting', 'analyst_choice', '3,11'),
    ('other_nonminority_split_concentration', '2.0', 'float', 'closure', 'Dirichlet concentration (equal means) for splitting the combined share of the non-minority lists no poll reports separately among those lists.', 'Analyst prior', PRIOR, '6,8'),
    ('incumbent_bloc_list_keys', 'aleksandar_vucic_ujedinjena_srbija;ivica_dacic_faktor_stabilnosti', 'csv;', 'coalitions', 'List keys the coalition tokens @all_except_incumbent and the incumbent-anchored assumption set refer to.', 'Analyst choice', 'analyst_choice', '10'),
    ('student_list_key', 'studentska_lista', 'text', 'coalitions', 'List key the token @all_except_student and the student-anchored assumption set refer to.', 'Analyst choice', 'analyst_choice', '10'),
    ('event_activation_types', 'left_party;expelled;joined_organization;endorsed_list;measured_voter_shift', 'csv;', 'events', 'ext_events types that can trigger the event-scenario mixture when dated AFTER the last poll (polls cannot have captured them). Departures, joinings, endorsements and measured shifts remain distinct types.', 'Analyst choice', 'analyst_choice', '5,6'),
    ('swing_sd_default', '0.25', 'float', 'geography', 'Unit-level log-weight SD used for pseudo-origins and families without a stable 2022-2023 swing estimate.', 'Analyst prior', PRIOR, '6'),
    ('swing_sd_cap', '0.50', 'float', 'geography', 'Upper bound on any estimated swing SD (families with few or tiny observations give unstable values).', 'Analyst prior', PRIOR, '6'),
    ('local_swing_outcome', 'proxy_change_pp_excl_joint_list', 'enum:proxy_change_pp_excl_joint_list|lead_share_change_pp', 'local_info', 'Outcome column of s4_local_swing_panel used for the descriptive local summary and the alpha scenarios. Rows with a missing value are left out, not imputed.', 'Analyst choice', 'analyst_choice', '4,6'),
    ('turnout_sensitivity_offsets', '-500000;300000', 'csv;', 'sensitivity', 'Shifts (in participating voters) applied to BOTH ends of the user-specified turnout range to build alternative turnout scenarios. Scenario definitions, not forecasts of turnout.', 'Analyst scenario', 'analyst_choice', '11'),
    ('poll_sensitivity_design_effects', '1.0;4.0', 'csv;', 'sensitivity', 'Alternative design effects for the poll sampling error.', 'Analyst scenario', 'analyst_choice', '5,11'),
    ('poll_sensitivity_election_error_sd', '0.05;0.20', 'csv;', 'sensitivity', 'Alternative SDs of the shared election-day polling miss.', 'Analyst scenario', 'analyst_choice', '5,11'),
    ('dispersion_sensitivity_multipliers', '0.5;2.0', 'csv;', 'sensitivity', 'Multipliers on unit and region swing dispersion for the municipal layer (the backtest finds regional heterogeneity of roughly 0.3x to 2x).', 'Analyst scenario', 'analyst_choice', '6,11'),
    ('threshold_focus_list_keys', 'ivica_dacic_faktor_stabilnosti;evropska_srbija;autenticna_desnica', 'csv;', 'sensitivity', 'Non-minority lists whose poll strength is swept to show how the seat outcome reacts around the 3 percent threshold.', 'Analyst choice', 'analyst_choice', '9,11'),
    ('threshold_sweep_shift_log', '-0.6;-0.4;-0.2;0;0.2;0.4;0.6', 'csv;', 'sensitivity', 'Additive shifts of log(list / reference) used in the threshold sweep.', 'Analyst scenario', 'analyst_choice', '9,11'),
    ('n_sweep_simulations', '5000', 'int', 'simulation', 'Draws per grid point in the threshold sweep.', 'Computation setting', 'analyst_choice', '9,11'),
    ('minority_status_sensitivity_keys', 'rasim_ljajic_ljudski', 'csv;', 'sensitivity', 'Lists marked as minority lists in cfg_list_registry_2026 whose status is flipped to non-minority in a sensitivity run (the RIK decides; the group of this list is not stated in the sources).', 'Analyst choice', 'analyst_choice', '7,9'),
    ('small_unit_valid_votes_flag', '500', 'int', 'reporting', 'Units whose expected valid votes fall below this are flagged in municipal outputs: their shares rest on a handful of votes (for example the polling-station units of region RS23).', 'Reporting setting', 'analyst_choice', '8,13'),
    ('minority_sensitivity_phi_values', '0;1', 'csv;', 'sensitivity', 'Fixed values of the minority turnout responsiveness phi used in minority-outcome scenarios (0 = minority votes unchanged by turnout, 1 = proportional to valid votes).', 'Analyst scenario', 'analyst_choice', '7,11'),
    ('minority_sensitivity_capture_means', '0.05;0.30', 'csv;', 'sensitivity', 'Alternative mean shares of a group pool captured by new-entrant minority lists.', 'Analyst scenario', 'analyst_choice', '7,11'),
    ('poll_timeline_max_points', '40', 'int', 'reporting', 'Upper bound on the number of dated re-estimations in the forecast timeline.', 'Reporting setting', 'analyst_choice', '13'),
    ('turnout_draw', 'uniform_between_low_and_high', 'enum', 'turnout', 'Distribution of national participating voters within the user-specified range.', 'Analyst choice', PRIOR, '3,11'),
    ('invalid_rate_multiplier_baseline', '1.0', 'float', 'turnout', 'Scales the unit baseline invalid-ballot rate (1 = unchanged).', 'Analyst prior', PRIOR, '3'),
    ('unit_swing_sd_multiplier', '1.0', 'float', 'geography', 'Multiplier on unit-level swing dispersion estimated from 2022-2023.', 'Analyst prior', PRIOR, '6,11'),
    ('region_swing_sd_multiplier', '1.0', 'float', 'geography', 'Multiplier on regional swing dispersion estimated from 2022-2023 (5 regions: weakly identified).', 'Analyst prior', PRIOR, '6,11'),
    ('local_transfer_alpha_values', '0;0.5;1', 'csv;', 'local_info', 'Scenario grid for how much of a municipality local-election swing of the governing-coalition lists carries into its parliamentary geography (NOT identified).', 'Analyst scenario', PRIOR, '4,6'),
    ('local_mobilization_effect_sd', '0.10', 'float', 'local_info', 'SD of an unidentified mobilization effect of having held a recent local election (log scale, student-list geography). Mean 0 because no effect is identified.', 'Analyst prior', PRIOR, '4,6'),
    ('minority_turnout_responsiveness_low', '0.0', 'float', 'minority', 'Lower bound of phi: elasticity of a minority group vote to the change in valid votes (0 = unchanged, 1 = proportional).', 'Analyst prior', PRIOR, '7'),
    ('minority_turnout_responsiveness_high', '1.0', 'float', 'minority', 'Upper bound of phi (uniform draw).', 'Analyst prior', PRIOR, '7'),
    ('minority_group_shock_sdlog', '0.15', 'float', 'minority', 'Log-SD of a shock common to all lists of a minority group.', 'Analyst prior', PRIOR, '7'),
    ('minority_new_entrant_capture_mean', '0.15', 'float', 'minority', 'Mean share of an existing minority-group pool captured by a new entrant list of the same group.', 'Analyst prior', PRIOR, '7'),
    ('minority_new_entrant_capture_concentration', '8', 'float', 'minority', 'Beta concentration for the capture share.', 'Analyst prior', PRIOR, '7'),
    ('minority_prior_only_votes_median', '3000', 'int', 'minority', 'Median votes of a minority list with no historical analog and no group pool in the data (prior-only).', 'Analyst prior', PRIOR, '7'),
    ('minority_prior_only_votes_sdlog', '0.8', 'float', 'minority', 'Log-SD for prior-only minority lists.', 'Analyst prior', PRIOR, '7'),
    ('n_simulations', '20000', 'int', 'simulation', 'Monte Carlo draws for the national forecast.', 'Analyst choice', 'analyst_choice', '11'),
    ('n_unit_draws', '400', 'int', 'simulation', 'Draws for which the municipal-level downscaling is run (municipal intervals).', 'Analyst choice', 'analyst_choice', '11'),
    ('interval_levels', '0.8;0.95', 'csv;', 'simulation', 'Central interval levels reported.', 'Analyst choice', 'analyst_choice', '11,13'),
    ('market_prices_are_inputs', 'false', 'bool', 'policy', 'Prediction-market prices are validation signals only and never enter the vote-share model.', 'Task specification', 'policy', '5,12'),
]
mp = pd.DataFrame(MP, columns=['param_key', 'param_value', 'value_type', 'category', 'description', 'source', 'verification_status', 'used_in_stage'])
mp['source_date'] = '2026-10-14'
base_params = pd.read_csv(OUT / 'cfg_parameters.csv', dtype=str, keep_default_na=False)
allp = pd.concat([base_params, mp[base_params.columns]], ignore_index=True)
assert allp.param_key.is_unique
allp.to_csv(OUT / 'cfg_parameters.csv', index=False)

# geography weights: which 2023 families (votes per registered voter) drive WHERE each 2026 list's votes fall
OW = [
    ('aleksandar_vucic_ujedinjena_srbija', 'SNS_LED', 1.0, 'SNS-led successor list.'),
    ('ivica_dacic_faktor_stabilnosti', 'SPS_LED', 1.0, 'SPS-led successor list.'),
    ('studentska_lista', 'OPP_BROAD', 1.0, 'New list. Geography assumed to follow the 2023 broad opposition list.'),
    ('studentska_lista', 'OPP_OTHER', 0.5, 'Other opposition voters of 2023.'),
    ('studentska_lista', 'MI_GIN', 0.5, 'Protest-vote list of 2023.'),
    ('studentska_lista', 'UNCLASSIFIED', 0.5, 'Unclassified 2023 lists.'),
    ('studentska_lista', 'ABSTAIN', 0.15, 'Previous abstainers (per registered voter): the student list is assumed to draw on first-time and returning voters. Affects where votes fall, not the national level.'),
    ('evropska_srbija', 'OPP_BROAD', 1.0, 'Successor of part of the 2023 broad opposition list.'),
    ('autenticna_desnica', 'NADA', 1.0, 'Same leader as the 2023 NADA list.'),
    ('autenticna_desnica', 'DVERI_ZAVETNICI', 0.3, 'Neighbouring national-right electorate.'),
    ('alternativa_za_srbiju', 'NARODNA_STRANKA', 1.0, 'Narodna stranka is a component.'),
    ('bogoljub_karic_pss_bk', 'REGISTERED', 1.0, 'No historical analog in the data: pattern proportional to the register.'),
    ('liberalno_zelena_stranka', 'REGISTERED', 1.0, 'No historical analog in the data: pattern proportional to the register.'),
    ('cale_ovo_je_za_tebe', 'REGISTERED', 1.0, 'No historical analog in the data: pattern proportional to the register.'),
]
pd.DataFrame([(a, b, c, 'proposed_unreviewed', d) for a, b, c, d in OW],
             columns=['list_key', 'origin', 'weight', 'mapping_status', 'note']).to_csv(OUT / 'cfg_origin_weights.csv', index=False)

MM = [
    ('svm_pastor', 'Hungarian', 'MIN_HU', 'continuing', 'analog_family', 'Continuity of the SVM list is documented by name.'),
    ('usame_zukorlic_pokret_za_ujedinjenje', 'Bosniak', 'MIN_BOSNIAK_SPP', 'continuing', 'analog_family', 'Same leader as the 2023 list.'),
    ('sda_sandzaka_cuvari_sandzaka', 'Bosniak', 'MIN_BOSNIAK_SDA', 'continuing', 'analog_family', 'Same party as the 2023 list.'),
    ('rasim_ljajic_ljudski', 'Bosniak', '', 'new_entrant', 'group_pool', 'ASSUMED Bosniak group (not stated in sources); no 2023 minority list of this organization in the data.'),
    ('biram_pravdu_biram_buducnost', 'Bosniak', '', 'new_entrant', 'group_pool', 'Bosniak and Greek minority coalition per Danas; modelled in the Bosniak pool; a 2023 list with a similar name (NP202310) is unclassified in the data.'),
    ('albanska_koalicija', 'Albanian', 'MIN_ALBANIAN', 'continuing', 'analog_family', 'Seven Albanian parties on one list; in 2023 two Albanian lists ran (families merged).'),
    ('ruska_stranka_srbija_u_briksu', 'Russian', 'MIN_RUSSIAN', 'continuing', 'analog_family', 'Same leader as the 2023 Russian Party list.'),
    ('stranka_rusko_srpskog_jedinstva', 'Russian', '', 'new_entrant', 'group_pool', 'Newly founded; competes for the same pool as the Russian Party list.'),
    ('majka_srbija_gruda', 'Slovak', '', 'prior_only', 'region_uniform', 'No Slovak list and no group base in the data; votes are prior-only and spread uniformly over region RS12 as an explicit placeholder.'),
]
pd.DataFrame([(a, b, c, d, e, 'proposed_unreviewed', f) for a, b, c, d, e, f in MM],
             columns=['list_key', 'minority_group', 'analog_family', 'role', 'unit_pattern', 'mapping_status', 'note']).to_csv(OUT / 'cfg_minority_roster_map.csv', index=False)

SC = 'scenario_definition__analyst_choice__not_an_estimate'
ES = []


def add_sc(sid, name, inmix, wt, param, val, desc, frm='', to='', trigger=''):
    ES.append((sid, name, inmix, wt, trigger, param, frm, to, val, desc, SC))


SPS, STU, ES_, AD = 'ivica_dacic_faktor_stabilnosti', 'studentska_lista', 'evropska_srbija', 'autenticna_desnica'
# SPS -> student transfer applied only to the part of the movement the polls cannot yet reflect (events after the last poll).
# `trigger_origin_entity` is the label used in ext_events.origin_entity; the mixture is active only if such an event exists.
for sid, nm, mean, d in (('sps_none', 'No significant SPS-to-student voter movement', 0.0, 'Departures and endorsements do not move SPS voters.'),
                         ('sps_moderate', 'Moderate voter realignment', 0.10, 'Share of the SPS poll vote that moves to the student list (mean of a Beta).'),
                         ('sps_strong', 'Stronger SPS decline', 0.25, 'Larger share of the SPS poll vote moves to the student list (mean of a Beta).')):
    add_sc(sid, nm, True, 1 / 3, 'transfer_mean', mean, d, SPS, STU, 'SPS')
    add_sc(sid, nm, True, 1 / 3, 'transfer_beta_concentration', 20.0, 'Beta concentration around the mean transfer share.', SPS, STU, 'SPS')
# sensitivity scenarios (not in the baseline mixture)
add_sc('student_mobilization_up', 'Increased student mobilization', False, 0.0, 'shift_log', 0.10, 'Adds to log(list / reference) for the list in to_list_key: about +2 points on the student share at a 40 percent level.', '', STU)
add_sc('sns_retention_up', 'Increased SNS voter retention', False, 0.0, 'shift_log', -0.10, 'Subtracts from log(list / reference) for the list in to_list_key.', '', STU)
add_sc('opposition_fragmentation', 'Opposition fragmentation', False, 0.0, 'transfer_mean', 0.05, 'Share of the student poll vote moving to this list (0.10 in total, split equally between the two other polled opposition lists).', STU, ES_)
add_sc('opposition_fragmentation', 'Opposition fragmentation', False, 0.0, 'transfer_mean', 0.05, 'Share of the student poll vote moving to this list (0.10 in total, split equally between the two other polled opposition lists).', STU, AD)
add_sc('opposition_consolidation', 'Opposition consolidation', False, 0.0, 'transfer_mean', 0.25, 'Share of this list poll vote moving to the student list.', ES_, STU)
add_sc('opposition_consolidation', 'Opposition consolidation', False, 0.0, 'transfer_mean', 0.25, 'Share of this list poll vote moving to the student list.', AD, STU)
pd.DataFrame(ES, columns=['scenario_id', 'scenario_name', 'in_baseline_mixture', 'baseline_weight', 'trigger_origin_entity', 'param', 'from_list_key', 'to_list_key',
                          'value', 'description', 'status']).to_csv(OUT / 'cfg_event_scenarios.csv', index=False)

EV = 'No source states this compatibility; scenario only.'
CO = [
    ('C01', 'SNS-led list alone', 'aleksandar_vucic_ujedinjena_srbija', 'aleksandar_vucic_ujedinjena_srbija', 'all', 'mathematical_only', 'Single-list majority.'),
    ('C02', 'SNS-led list + SPS-led list', 'aleksandar_vucic_ujedinjena_srbija;ivica_dacic_faktor_stabilnosti', 'aleksandar_vucic_ujedinjena_srbija', 'incumbent_anchored', 'plausible_by_precedent',
     'RFE/RL 2025-04-15: SPS said it would support the new government. A longer SNS-SPS governing history exists but was not source-checked in this run.'),
    ('C03', 'SNS-led + SPS-led + all minority lists', 'aleksandar_vucic_ujedinjena_srbija;ivica_dacic_faktor_stabilnosti;@minority', 'aleksandar_vucic_ujedinjena_srbija', 'incumbent_anchored', 'assumed', EV),
    ('C04', 'SNS-led + SPS-led + Autenticna desnica', 'aleksandar_vucic_ujedinjena_srbija;ivica_dacic_faktor_stabilnosti;autenticna_desnica', 'aleksandar_vucic_ujedinjena_srbija', 'incumbent_anchored', 'assumed', EV),
    ('C05', 'Student list alone', 'studentska_lista', 'studentska_lista', 'all', 'mathematical_only', 'Single-list majority.'),
    ('C06', 'Student list + Evropska Srbija', 'studentska_lista;evropska_srbija', 'studentska_lista', 'student_anchored', 'assumed', EV),
    ('C07', 'Student list + Evropska Srbija + all minority lists', 'studentska_lista;evropska_srbija;@minority', 'studentska_lista', 'student_anchored', 'assumed', EV),
    ('C08', 'Student list + every list except the SNS-led and SPS-led lists', 'studentska_lista;@all_except_incumbent', 'studentska_lista', 'student_anchored', 'assumed', EV),
    ('C09', 'Every list except the student list', '@all_except_student', 'aleksandar_vucic_ujedinjena_srbija', 'mathematical_only', 'mathematical_only', 'Upper bound for any coalition that excludes the student list.'),
]
pd.DataFrame([(a, b, c, d, e, f, g, 'analyst_scenario__not_an_estimate') for a, b, c, d, e, f, g in CO],
             columns=['coalition_id', 'coalition_name', 'members', 'anchor', 'plausibility_assumption_set', 'plausibility', 'evidence', 'status']).to_csv(OUT / 'cfg_coalitions.csv', index=False)

# ------------------------------------------------------------------------------- required columns (pipeline SQL)
# Columns that the pipeline SQL reads. Stage 0.1 checks they exist in the loaded dataset. This is a code-dependency
# declaration (what the SQL needs), not an observation.
REQUIRED = {
    'election_totals': ('0-3', ['election_id', 'election_date', 'geo_id', 'geo_name', 'geo_level', 'is_2023_leaf', 'registered_voters',
                                'voters_turned_out', 'ballots_cast', 'invalid_ballots', 'valid_ballots_reported',
                                'valid_ballots_from_lists', 'list_sum_minus_reported_valid', 'sample_13', 'is_local_election',
                                'is_round_nov2025', 'is_round_mar2026']),
    'list_votes': ('0-4', ['election_id', 'election_date', 'geo_id', 'geo_level', 'is_2023_leaf', 'list_id', 'list_number',
                           'list_name_source', 'votes', 'mandates', 'vote_share_valid', 'is_local_election',
                           'coalition_members_documented']),
    'territories': ('0-3', ['geo_id', 'geo_name', 'parent_geo_id', 'region_id', 'geo_level', 'is_2023_leaf',
                            'is_special_electorate', 'sample_13']),
    'polling_stations_2023': ('0', ['election_id', 'geo_id', 'registered_voters', 'voters_turned_out', 'ballots_cast', 'valid_ballots']),
    'paired_changes_13': ('4', ['geo_id', 'baseline_date', 'local_election_date', 'baseline_2023_registered_weight',
                                'lead_share_valid_2023', 'lead_share_valid_local', 'turnout_rate_2023', 'turnout_rate_local',
                                'lead_share_change_pp', 'turnout_change_pp', 'eligible_for_default_model', 'cohort_nov2025',
                                'cohort_mar2026']),
    'model_panel_13': ('4', ['election_id', 'geo_id', 'registered_voters', 'voters_turned_out', 'valid_ballots_reported',
                             'lead_list_votes', 'eligible_for_default_model']),
    'data_dictionary': ('0', ['table_name', 'column_name', 'bigquery_type']),
}
rq = [(t, c, stg) for t, (stg, cols) in REQUIRED.items() for c in cols]
pd.DataFrame(rq, columns=['table_name', 'column_name', 'needed_by']).to_csv(OUT / 'cfg_required_columns.csv', index=False)

# ----------------------------------------------------------------------------------- data-dependent tables
if len(sys.argv) > 1:
    sys.path.insert(0, str(ROOT / 'tests'))
    from harness import load_package
    con, _ = load_package(sys.argv[1])
    nat = con.execute("SELECT election_id, list_id, list_number, list_name_source FROM list_votes "
                      "WHERE geo_id = 'RS' ORDER BY election_id, list_number").df()
    M = {  # list_id -> (family, bloc, minority, minority_group, confidence, basis, note)
        'NP202201': ('SNS_LED', 'sns_led', False, '', 'high', 'leader named in list', ''),
        'NP202202': ('SPS_LED', 'sps_led', False, '', 'high', 'leader named in list', ''),
        'NP202203': ('MIN_HU', 'minority', True, 'Hungarian', 'high', 'party named in list', 'RIK minority decision to verify.'),
        'NP202204': ('SRS', 'right_national', False, '', 'high', 'party named in list', ''),
        'NP202205': ('OPP_BROAD', 'opposition_broad', False, '', 'medium', '2022 main opposition list', 'Continuity with the 2023 SPN list is an ASSUMPTION (different coalitions).'),
        'NP202206': ('NADA', 'right_national', False, '', 'medium', 'leader Milos Jovanovic also leads the 2023 list and the 2026 Autenticna desnica', 'Organisational continuity assumed.'),
        'NP202207': ('DVERI_ZAVETNICI', 'right_national', False, '', 'high', 'name: Serbian Party the Patrons (Zavetnici); package README: Zavetnici and Dveri ran jointly in 2023', 'Merged with Dveri (NP202211) to match the 2023 joint list.'),
        'NP202208': ('MIN_BOSNIAK_SPP', 'minority', True, 'Bosniak', 'medium', "name: Mufti's Pledge - Party of Justice and Reconciliation (SPP)", 'Continuity with the 2023 Usame Zukorlic list and the 2026 SPP-submitted list is inferred from names (SPP is the submitter of the 2026 list per S05); verify. RIK minority decision to verify.'),
        'NP202209': ('OPP_BROAD', 'opposition_broad', False, '', 'low', 'name: We Must - Action - Environmental Uprising - Dont Let Belgrade Drown', 'ASSUMPTION that these components are inside the 2023 SPN list (Stage 1 swing compares the family totals). NOT verified from the data; review.'),
        'NP202210': ('OPP_OTHER', 'opposition_other', False, '', 'low', 'name: The Sovereignists - Enough Is Enough, Together for Serbia, ZZS', 'Partial overlap with the 2023 Enough-is-enough list (NP202312) is possible; review.'),
        'NP202211': ('DVERI_ZAVETNICI', 'right_national', False, '', 'high', 'package README (joint 2023 list)', ''),
        'NP202212': ('UNCLASSIFIED', 'unclassified', False, '', 'low', 'Vojvodina regional list; nature not verifiable from data', 'Review.'),
        'NP202213': ('MIN_BOSNIAK_SDA', 'minority', True, 'Bosniak', 'medium', 'party named in list', 'RIK minority decision to verify.'),
        'NP202214': ('OPP_OTHER', 'opposition_other', False, '', 'low', 'leader named in list', 'Review.'),
        'NP202215': ('MIN_ALBANIAN', 'minority', True, 'Albanian', 'medium', 'name', 'RIK minority decision to verify.'),
        'NP202216': ('MIN_ALBANIAN', 'minority', True, 'Albanian', 'medium', 'name', 'RIK minority decision to verify.'),
        'NP202217': ('OPP_OTHER', 'opposition_other', False, '', 'low', 'name only', 'Review.'),
        'NP202218': ('MIN_ROMA', 'minority', True, 'Roma', 'medium', 'name', 'RIK minority decision to verify.'),
        'NP202219': ('MIN_RUSSIAN', 'minority', True, 'Russian', 'low', 'name: Russian Minority Alliance', 'Organisational continuity with the 2023 Russian Party list not established; review. RIK minority decision to verify.'),
        'NP202301': ('SNS_LED', 'sns_led', False, '', 'high', 'leader named in list', ''),
        'NP202302': ('SPS_LED', 'sps_led', False, '', 'high', 'leader named in list', ''),
        'NP202303': ('SRS', 'right_national', False, '', 'high', 'party named in list', ''),
        'NP202304': ('DVERI_ZAVETNICI', 'right_national', False, '', 'high', 'package README: joint Dveri/Zavetnici list', ''),
        'NP202305': ('NADA', 'right_national', False, '', 'medium', 'leader Milos Jovanovic', 'Organisational continuity assumed.'),
        'NP202306': ('MIN_HU', 'minority', True, 'Hungarian', 'high', 'party named in list', 'RIK minority decision to verify.'),
        'NP202307': ('OPP_BROAD', 'opposition_broad', False, '', 'high', 'Serbia Against Violence (Aleksic, Tepic named)', '2026 successors are split across several lists: transition model needed (Stages 5-6).'),
        'NP202308': ('MIN_BOSNIAK_SPP', 'minority', True, 'Bosniak', 'medium', 'leader Usame Zukorlic (also on the 2026 list)', 'RIK minority decision to verify.'),
        'NP202309': ('MIN_BOSNIAK_SDA', 'minority', True, 'Bosniak', 'medium', 'party named in list', 'RIK minority decision to verify.'),
        'NP202310': ('UNCLASSIFIED', 'unclassified', False, '', 'low', 'name: Together for the Future and Development', 'The name resembles a component of the 2026 Biram pravdu, biram buducnost list (Stranka buducnosti i razvoja); continuity and minority status NOT established; review.'),
        'NP202311': ('NARODNA_STRANKA', 'opposition_other', False, '', 'medium', "name: People's Party", 'Narodna stranka is on the 2026 Alternativa za Srbiju list (S05).'),
        'NP202312': ('OPP_OTHER', 'opposition_other', False, '', 'low', 'name only', 'Review.'),
        'NP202313': ('MIN_ALBANIAN', 'minority', True, 'Albanian', 'medium', 'name', 'RIK minority decision to verify.'),
        'NP202314': ('MI_GIN', 'opposition_other', False, '', 'high', 'leader Branimir Nestorovic named', 'Not on the 2026 ballot.'),
        'NP202315': ('UNCLASSIFIED', 'unclassified', False, '', 'low', 'name only', 'Review.'),
        'NP202316': ('MIN_RUSSIAN', 'minority', True, 'Russian', 'high', 'name: Russian Party - Slobodan Nikolic (leader also on the 2026 list)', 'RIK minority decision to verify.'),
        'NP202317': ('OPP_OTHER', 'opposition_other', False, '', 'medium', 'leader named in list', 'Review.'),
        'NP202318': ('MIN_ALBANIAN', 'minority', True, 'Albanian', 'medium', 'name', 'RIK minority decision to verify.'),
    }
    rows = []
    for _, r in nat.iterrows():
        f = M[r.list_id]
        rows.append(dict(election_id=r.election_id, list_id=r.list_id, list_name_source=r.list_name_source, family=f[0], bloc=f[1],
                         is_minority_proposed=f[2], minority_group_proposed=f[3], confidence=f[4],
                         mapping_status='proposed_unreviewed', basis=f[5], review_note=f[6]))
    fm = pd.DataFrame(rows)
    fm['is_minority_proposed'] = fm['is_minority_proposed'].astype('boolean')
    fm.to_csv(OUT / 'cfg_list_family_map.csv', index=False)
    assert len(fm) == len(nat) == 37, (len(fm), len(nat))

    lv = con.execute("SELECT election_id, list_id AS local_list_id, geo_id, geo_name, list_name_source, "
                     "coalition_members_documented FROM list_votes WHERE is_local_election = 1 "
                     "ORDER BY election_id, list_id").df()

    def hint(s, pats):
        s = (s or '').lower()
        return any(p in s for p in pats)
    lv['hint_student_in_name'] = lv.list_name_source.apply(lambda s: hint(s, ['студент', 'student']))
    lv['hint_youth_in_name'] = lv.list_name_source.apply(lambda s: hint(s, ['млад', 'mlad']))
    lv['hint_united_in_name'] = lv.list_name_source.apply(lambda s: hint(s, ['уједињен', 'ujedinjen']))
    lv['hint_sns_led_name_pattern'] = lv.list_name_source.apply(
        lambda s: (s or '').lower().replace('коалиција ', '').startswith('александар вучић'))
    lv['external_evidence_note'] = ''
    lv.loc[lv.local_list_id == 'LOCAL_70327_2026_02', 'external_evidence_note'] = (
        'Wikipedia (tertiary, retrieved 2026-10-14): the list included local politicians/movements supported by the '
        'Serbian Student Movement. Verify with a primary or reliable secondary source before classifying.')
    for c in ('verified_family', 'verified_bloc', 'verification_source_url', 'verified_by', 'verified_date'):
        lv[c] = ''
    lv['review_status'] = 'unreviewed'
    lv.to_csv(OUT / 'cfg_local_list_review.csv', index=False)
    print('family map', len(fm), '| local list review', len(lv), '| name hints: student',
          int(lv.hint_student_in_name.sum()), 'youth', int(lv.hint_youth_in_name.sum()),
          'united', int(lv.hint_united_in_name.sum()), 'sns-pattern', int(lv.hint_sns_led_name_pattern.sum()))
print('config written to', OUT)


# --------------------------------------------------------------------------- header-only templates for the manual-import tables
import config_schemas as _cs
_tpl = OUT.parent / 'data_to_import' / 'templates'
_tpl.mkdir(parents=True, exist_ok=True)
for _name, _cols in _cs.EXT_TABLES.items():
    pd.DataFrame(columns=[c for c, _ in _cols]).to_csv(_tpl / f'{_name}.csv', index=False)
print('templates written to', _tpl)
