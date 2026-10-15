"""Writes data_to_import/*.csv: EXTERNAL observations collected from dated public sources on 2026-10-14.

Rules followed:
  * a value is entered only if a source states it; anything a source does not state is left EMPTY, never filled in;
  * every row carries source_url and a verification_status describing how well it is verified;
  * non-scientific reader polls and derived models (BIRODI) are NOT entered as polls (see cfg_source_register);
  * shares are stored as proportions (0.449 = 44.9 percent) in the base the source states in share_base.
These files are NOT loaded automatically. The analyst loads them with pipeline.import_external_csv(...) after reviewing them.
"""
import pathlib

import pandas as pd

OUT = pathlib.Path(__file__).resolve().parents[1] / 'data_to_import'
OUT.mkdir(exist_ok=True)
RET = '2026-10-14'

# ----------------------------------------------------------------------------------------------- polls
U, S, D, E, A, N, M = ('aleksandar_vucic_ujedinjena_srbija', 'studentska_lista', 'ivica_dacic_faktor_stabilnosti',
                       'evropska_srbija', 'autenticna_desnica', 'unlisted_mi_snaga_naroda_narodna_stranka',
                       'other_and_minorities_aggregate')
polls = []


def poll(pid, pollster, commissioner, fs, fe, pub, n, pop, mode, und, turn, rows, base, moe, notes, url, ver):
    for key, label, val in rows:
        polls.append(dict(poll_id=pid, pollster=pollster, commissioned_by=commissioner, fieldwork_start=fs, fieldwork_end=fe,
                          publication_date=pub, sample_size=n, population_base=pop, mode=mode, undecided_share=und,
                          turnout_intention_share=turn, list_key=key, list_label_reported=label, share=val, share_base=base,
                          reported_margin_of_error=moe, methodology_notes=notes, source_url=url, retrieved_date=RET,
                          verification_status=ver))


poll('crta_2026_06', 'CRTA with Democracy Action Lab (Stanford)', None, '2026-06-10', '2026-06-24', '2026-07-15', 2324,
     'adult citizens of Serbia (18+), described as representative', 'face-to-face', 0.12, None,
     [(S, 'Studentska lista', 0.449), (U, 'SNS', 0.357), (D, 'SPS', 0.038)],
     'decided_voters (reported as 70 percent of respondents)', None,
     'Reported: 12 percent politically undecided and 9 percent will not vote (base of these two not stated). Weighting, sampling '
     'procedure, margin of error and Evropska Srbija value not stated in the article. Other lists not reported.',
     'https://n1info.rs/vesti/crta-istrazivanje-izbori-studentska-lista-sns/', 'secondary_media_report_of_pollster_release__metadata_partly_missing')
poll('nspm_2026_07', 'NSPM (Nova srpska politicka misao)', None, None, None, '2026-07-30', 1000, None, None, None, None,
     [(S, 'Studentska lista', 0.396), (U, 'SNS-led list', 0.375), (D, 'SPS', 0.049)], None, None,
     'Publication date, sample and the SPS value come from a Wikipedia compilation (tertiary). The student-list and SNS-led values '
     'are corroborated by Beta/Nova.rs and N1 (2026-09-30), which cite them as the previous NSPM reading. Fieldwork, mode and base not stated.',
     'https://en.wikipedia.org/wiki/Opinion_polling_for_the_next_Serbian_parliamentary_election',
     'tertiary_compilation__two_of_three_values_corroborated_by_media')
poll('nspm_2026_09', 'NSPM (Nova srpska politicka misao)', None, None, '2026-09-10', '2026-09-30', None, None, None, None, None,
     [(S, 'Studentska lista', 0.444), (U, 'Ujedinjena Srbija', 0.417)], None, None,
     'Fieldwork "at the beginning of September" / "first ten days of September" (fieldwork_end is an upper bound, not a stated date). '
     'Conducted before list proclamation. Sample, mode, base and other lists not stated. Vreme column gives 44.3 for the student list; '
     'Beta/Nova.rs and N1 give 44.4 (44.4 used).',
     'https://nova.rs/vesti/politika/novo-istrazivanje-nsp-studentska-lista-44-odsto-ujedinjena-srbija-417-odsto/',
     'secondary_media_report__metadata_mostly_missing')
poll('faktorplus_2026_09a', 'Faktor plus', None, None, None, '2026-09-04', 1200, None, None, 0.31, None,
     [(S, 'Studentska lista', 0.315), (U, 'SNS-led list', 0.472), (D, 'SPS', 0.049)], None, None,
     'Student-list and SNS-led values confirmed by a 021.rs headline; SPS value and sample from a Wikipedia compilation (tertiary). '
     'The 31 percent undecided figure is attributed in a 021.rs article (2026-10-02) to the 4 September reading. Base of shares not stated '
     '(undecided reported separately). Commissioner not disclosed.',
     'https://www.021.rs/info/srbija/454405/faktor-plus-ima-novo-istrazivanje-sns-bi-osvojila-472-odsto-glasova-a-studentska-lista-315-odsto',
     'secondary_media_report__metadata_mostly_missing')
poll('faktorplus_2026_09b', 'Faktor plus', None, '2026-09-16', '2026-09-20', '2026-09-21', 986,
     'all citizens of both sexes, excluding Kosovo and Metohija', None, None, 0.62,
     [(U, 'Ujedinjena Srbija', 0.486), (S, 'Studentska lista', 0.371), (D, 'SPS', 0.049), (E, 'Evropska Srbija', 0.036),
      (A, 'Autenticna desnica - Milos Jovanovic - Novi DSS - Monarhisti - NADA', 0.028),
      (N, 'Mi snaga naroda - Narodna stranka - Branimir Nestorovic', 0.012), (M, 'Other/minorities', 0.018)],
     'decided_voters (per pollster V. Pajic as quoted by 021.rs; the Mondo article does not state the base)', None,
     'Turnout intention 62 percent (Mondo). Pollster says fieldwork lasted 4 days although 16-20 Sept spans five calendar days. Mode, '
     'weighting and margin of error not stated. Commissioner not disclosed: the pollster said the agency co-publishes with Blic and denied '
     'that the SNS commissioned the poll. A pollster-independent analyst (BIRODI) estimated about 16 percent undecided from this release; that '
     'is his reading, not a pollster figure. The label "Mi snaga naroda - Narodna stranka" does not match any list on the 2026 roster.',
     'https://mondo.rs/Info/Politika/a2284943/novo-istrazivanje-o-rejtinzima-stranaka-pred-izbore-2026.html',
     'secondary_media_report__metadata_partly_missing')
pd.DataFrame(polls).to_csv(OUT / 'ext_polls_2026.csv', index=False)

# ---------------------------------------------------------------------------------------------- events
V = 'https://vreme.com/vesti/nastavlja-se-okrsaj-u-sps-u-ko-je-sve-otisao-za-ruzicem/'
ev = [
    ('E001', '2026-09-09', '2026-09-09', 'other', 'Aleksandar Vucic (president)', 'President of Serbia', None, None, None, 'national',
     'https://balkaninsight.com/2026/09/09/serbias-vucic-calls-early-parliamentary-elections-for-october-25/bi/', 'Balkan Insight',
     'high', 'Early parliamentary election called for 25 October 2026.'),
    ('E002', None, '2026-10-09', 'expelled', 'Branko Ruzic', 'former MP (per N1); role not given by Vreme', 'SPS', None, None, 'national', V, 'Vreme',
     'high', 'Expelled by the SPS Statutory Commission "at the end of August 2026" (exact day not given). Expulsion is not a voluntary departure.'),
    ('E003', '2026-10-09', '2026-10-09', 'left_party', 'Group of 13 members of the SPS Rakovica committee (incl. Marko Radunovic, a candidate on the Dacic list)',
     'local party committee members', 'SPS', None, '70211', 'municipal', V, 'Vreme', 'high',
     'Left the party and resigned all functions in a joint statement. No destination organization stated. Whether the candidacy of M. Radunovic on the Dacic list continues is not stated.'),
    ('E004', None, '2026-10-09', 'left_party', 'Dejan Curcic', 'member of the SPS Main Board', 'SPS', None, None, 'national', V, 'Vreme', 'medium',
     'Left after the expulsion of B. Ruzic, which he named as the reason. Date not given.'),
    ('E005', None, '2026-10-09', 'left_party', 'Milan Stepanovic', 'president of the SPS municipal board, Kursumlija', 'SPS', None, '70688', 'municipal', V,
     'Vreme', 'medium', 'Left, citing the expulsion of B. Ruzic. Date not given.'),
    ('E006', None, '2026-10-09', 'left_party', 'Milutin Ruzic', 'member of the SPS Main Board', 'SPS', None, None, 'national', V, 'Vreme', 'medium',
     'Submitted "irrevocable resignations" from all functions and from membership. Date not given.'),
    ('E007', None, '2026-10-09', 'left_party', 'Mateja Rankovic', 'member of the SPS Main Board', 'SPS', None, None, 'national', V, 'Vreme', 'medium',
     'Submitted "irrevocable resignations" from all functions and from membership. Date not given.'),
    ('E008', None, '2026-10-09', 'left_party', 'Branko Prodanovic', 'president of the SPS municipal board, Zubin Potok', 'SPS', None, '90093', 'municipal', V,
     'Vreme', 'medium', 'Left the party. Date not given.'),
    ('E009', None, '2026-10-09', 'other', 'Andrija Radivojevic', 'SPS official, Paracin (role not given)', 'SPS', None, '70904', 'municipal', V, 'Vreme', 'medium',
     'Resigned from all party functions. The article does NOT say he left membership, so this is not recorded as left_party.'),
    ('E010', None, '2026-10-09', 'left_party', 'Unnamed local officials in Sabac, Pozega and Smederevo (members of city/municipal government and local party officials)',
     'local officials', 'SPS', None, None, 'municipal', V, 'Vreme', 'medium',
     'Left SPS "at the end of September 2026" per Vreme. Three municipalities (geo ids 71269, 70955, 71099) are covered by one event row; no names.'),
    ('E011', '2026-10-12', '2026-10-12', 'left_party', 'Boris Milicevic', 'member of the SPS Main Board and Presidency', 'SPS', None, None, 'national',
     'https://n1info.rs/vesti/boris-milicevic-napustio-sps/', 'N1 (FoNet)', 'high',
     'Announced he is leaving SPS (membership), accusing the leadership of silence on rights violations and persecution of dissenters. No destination organization.'),
    ('E012', '2026-10-12', '2026-10-12', 'endorsed_list', 'Boris Milicevic', 'former member of the SPS Main Board and Presidency', None, 'Studentska lista', None, 'national',
     'https://n1info.rs/vesti/boris-milicevic-napustio-sps/', 'N1 (FoNet)', 'low',
     'INDIRECT: said that anyone who advocates freedom, equality, rule of law and socialist principles will vote for the Student List. Not a stated personal endorsement.'),
    ('E013', '2026-10-11', '2026-10-11', 'endorsed_list', 'Branko Ruzic', 'former MP, expelled from SPS', None, 'Studentska lista', None, 'national',
     'https://n1info.rs/vesti/ruzic-izbori-vucic-studentska-lista-sps/', 'N1 (FoNet interview)', 'high',
     'Said he will support the Student List (headline: "I will support the student list"). He did not call on others to leave SPS.'),
    ('E014', '2026-10-11', '2026-10-11', 'new_party_announced', 'Branko Ruzic', 'former MP, expelled from SPS', None, 'new social-democratic organization (unnamed, not registered)',
     None, 'national', 'https://n1info.rs/vesti/ruzic-izbori-vucic-studentska-lista-sps/', 'N1 (FoNet interview)', 'medium',
     'Says he is working on the programme, organization and infrastructure of a new political organization. No name; registration not stated; not on the 2026 ballot.'),
    ('E015', '2026-09-15', '2026-09-15', 'list_proclaimed', 'RIK', 'Republic Electoral Commission', None, 'Studentska lista - Studenti pobeduju', None, 'national',
     'https://beta.rs/content/252117-rik-proglasio-izbornu-listu-studentska-lista--studenti-pobedjuju', 'Beta.rs', 'high',
     'Proclaimed unanimously; 69,099 valid signatures. Not a national-minority list.'),
    ('E016', '2026-09-18', '2026-10-06', 'list_proclaimed', 'RIK', 'Republic Electoral Commission', None, 'Izbor naroda - Miki Aleksic - Milos Parandilovic - Aleksandar Jovanovic Cuta',
     None, 'national', 'https://www.danas.rs/vesti/politika/konacne-izborne-liste-izbori-2026-spisak/', 'Danas', 'medium', 'Proclaimed on 18 September per Danas (secondary).'),
    ('E017', '2026-09-22', '2026-10-06', 'list_withdrawn', 'Izbor naroda coalition', 'list submitter', None, 'Izbor naroda - Miki Aleksic - Milos Parandilovic - Aleksandar Jovanovic Cuta',
     None, 'national', 'https://www.danas.rs/vesti/politika/konacne-izborne-liste-izbori-2026-spisak/', 'Danas', 'medium',
     'Withdrawal notified 22 September; RIK noted it on 24 September (Danas, secondary). The list is NOT on the final ballot.'),
]
cols = ['event_id', 'event_date', 'report_date', 'event_type', 'actor_name', 'actor_role', 'origin_entity', 'destination_entity', 'geo_id', 'scope',
        'source_url', 'source_name', 'confidence', 'notes']
pd.DataFrame(ev, columns=cols).to_csv(OUT / 'ext_events_2026.csv', index=False)

# ---------------------------------------------------------------------------------------------- markets
NU = 'https://n1info.rs/english/news/ilija-srdanovic-overtakes-aleksandar-vucic-on-polymarket-prediction-platform/'
mk = []
for i, (slot, v, s) in enumerate([('early Friday morning', 0.56, 0.42), ('mid-morning', 0.712, 0.21),
                                   ('between 11:00 and 12:00', 0.30, 0.53), ('before 17:00', 0.43, 0.49)]):
    for who, pr in (('Aleksandar Vucic', v), ('Ilija Srdanovic', s)):
        mk.append((f'pm_pm_20260918_{i}_{who.split()[-1].lower()}', '2026-09-18 00:00:00', 'Polymarket', None,
                   'Next prime minister of Serbia (exact wording and resolution criteria not stated in the source)', who, pr, None, None, None, None,
                   None, NU,
                   f'Reported intraday price, time slot "{slot}" on Friday 2026-09-18 (time zone not stated; observed_at is the DATE only). '
                   'Reported by N1 on 2026-09-19. Volume and liquidity not stated. NOT a market on the election result or on vote shares. '
                   'The swings within one day (e.g. Vucic 71.2 to 30 percent) indicate a thin or fast-moving market.'))
mcols = ['observation_id', 'observed_at', 'platform', 'market_id', 'market_question', 'outcome_label', 'price', 'bid', 'ask', 'volume_usd',
         'liquidity_usd', 'resolution_criteria', 'source_url', 'notes']
pd.DataFrame(mk, columns=mcols).to_csv(OUT / 'ext_markets_2026.csv', index=False)

# ------------------------------------------------------------------------------------ local election registry
lr = [('70556', '2025-06-08', 'regular_local', False,
       'https://vreme.com/vesti/blog-redovni-lokalni-izbori-u-zajecaru-i-kosjericu/',
       'Zajecar. Vreme live blog of 2025-06-08: "regular local elections". Results are NOT in the package. N1 (2025-06-09) reports the SNS list at 14,199 votes (47.12 percent), preliminary.'),
      ('70629', '2025-06-08', 'regular_local', False,
       'https://vreme.com/vesti/blog-redovni-lokalni-izbori-u-zajecaru-i-kosjericu/',
       'Kosjeric. Same source. N1 (2025-06-09) reports the SNS list at 3,686 votes (49.23 percent), 100 percent processed. Results are NOT in the package.')]
pd.DataFrame(lr, columns=['geo_id', 'election_date', 'election_type', 'results_in_dataset', 'source_url', 'notes']).to_csv(
    OUT / 'ext_local_election_registry.csv', index=False)
print('written to', OUT)
