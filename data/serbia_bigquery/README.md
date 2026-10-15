# Serbia election analysis data — 14 October 2026

This package contains downloaded official results and statistics, checked local-report transcriptions, a 26-row matched panel, explicit BigQuery schemas, and a field dictionary. It is an analysis dataset, not a national election forecast. No polling estimates or party-announced preliminary results are used.

## Start here

Load **model_panel_13.csv** for the direct comparison: the same 13 territories in the 17 December 2023 parliamentary election and their recent local election. **paired_changes_13.csv** provides one row per municipality with descriptive percentage-point changes. Use **list_votes.csv** to investigate every list rather than accepting an assumed opposition grouping.

| Table | Rows | Data points |
|---|---:|---|
| model_panel_13 | 26 | Matched election counts, lead-list shares, turnout, invalid rates, round and municipality dummies, coalition scenarios, 2022 census structure, quality flags |
| paired_changes_13 | 13 | Local-minus-2023 lead-share and turnout changes, two coalition-family scenarios, fixed 2023 electorate weights |
| election_totals | 247 | All 234 published 2023 territories/aggregates plus 13 recent local totals; register, attendance, ballots, valid/invalid counts, report dates |
| list_votes | 8,723 | All published 2022 and 2023 parliamentary list votes across 234 territories, plus all 65 local lists in the selected sample |
| polling_stations_2023 | 8,273 | Final station-level register, attendance, ballots, valid/invalid counts and votes for all 18 parliamentary lists |
| municipality_context_2022 | 236 | Census population, adults, age 65+, age 20–34 share, female share, urban share, tertiary education among people aged 15+ |
| context_series | 98,304 | 2022 census age × sex × settlement and education × sex × settlement cells; annual total population by sex 2011–2025; monthly gross/net earnings January 2022–July 2026; employment by residence/sex Q1 2022–Q2 2026 |
| territories | 236 | Official territory codes, parents, regions, selected-sample flags and disjoint 2023 electoral-unit flags |
| coalition_bridge | 37 | Local lead list to 2023 electoral families, documented membership and explicit joint-list scenarios |
| source_manifest | 24 | Publisher, original download URL, request parameters, retrieval time, byte size and SHA-256 |
| quality_issues | 7 | One published arithmetic discrepancy; three incomplete local partner descriptions; three joint-list mapping limitations |
| data_dictionary | 255 | Column types, definitions, table grain, key columns, origins and missing-value conventions |

All row counts exclude the header. The two extra territory codes relative to the parliamentary tables are the statistical submunicipalities of Novi Sad. Their inclusion does not create parliamentary election observations that the electoral sources do not supply.

## Selected sample

| Cohort | Municipalities | Original election date |
|---|---|---|
| November 2025 | Mionica, Negotin, Sečanj | 2025-11-30 |
| March 2026 | Aranđelovac, Bajina Bašta, Bor, Kladovo, Knjaževac, Kula, Lučani, Majdanpek, Smederevska Palanka, Sevojno | 2026-03-29 |

The Bajina Bašta totals include a rerun on 9 April 2026; Knjaževac includes a rerun on 29 April 2026. Sevojno is matched to **71366**, not the entire City of Užice **79065**. The final 2023 baseline includes repeat voting through 2 January 2024.

## Dummy variables and an appropriate first model

`sample_13` denotes selection into this dataset. It equals 1 in every row of the 26-row panel and varies across the national tables. It is not a randomized treatment indicator.

`is_round_nov2025` and `is_round_mar2026` indicate the actual recent local ballot. Both are 0 for the 2023 parliamentary baseline. `cohort_nov2025` and `cohort_mar2026` indicate the municipality's later election cohort and remain constant across its two rows.

The panel has 12 municipality columns named `mun_<official_code>`. Mionica (70831) is the reference municipality when fitting an intercept. Alternatively, use a categorical `geo_id` fixed effect; do not include both representations.

A first descriptive model is:

`lead_vote_share_valid ~ municipality fixed effects + is_round_nov2025 + is_round_mar2026`

Use the same model with `proxy_share_valid_excluding_mixed` and `proxy_share_valid_including_mixed` as explicitly labelled sensitivity analyses on complete mapped pairs. The raw lead-list model and the family scenarios measure different things.

The round coefficients combine elapsed time, parliamentary-versus-local ballot differences, turnout changes, local candidates and coalition changes. They do not identify a causal treatment effect or a national swing. In this panel **post_2023 equals is_local_election exactly**. Do not estimate both coefficients. Sample flags, cohort flags, census attributes and other time-invariant municipal features are absorbed by the municipality fixed effects; entering them alongside those effects will introduce collinearity. Do not use all 64 CSV columns as independent regressors.

If using weights, `baseline_2023_registered_weight` supplies a fixed within-sample electorate weight. It is not a national representativeness weight. The 13 areas are a nonrandom sample, with no recent outcomes for most other territories. Their 2023-only rows cannot be fabricated into post-election controls for difference-in-differences. A forecast requires out-of-sample calibration, ballot-type adjustment, coalition scenarios, turnout scenarios and uncertainty about transport to the national electorate. With only 13 municipality clusters, conventional cluster-robust inference alone is insufficient; use suitable small-cluster methods and sensitivity checks.

## Coalition handling and source limitations

Original electoral lists remain separate. A local list can include SNS, SPS, SRS, VMSZ or additional parties. Compare the raw SNS-led lead-list share only with its stated coalition caveat; do not interpret it as SNS's individual party vote.

For ten local lead lists, the total report enumerates party members. The bridge creates whole-list electoral-family proxies: the 2023 SNS-led family plus documented SPS-, SRS- and VMSZ-led families. These are modelling scenarios. Older lists themselves contain partners, so these proxies are not exact party decomposition or identified mathematical bounds.

Aranđelovac, Knjaževac and Smederevska Palanka include Zavetnici in the recent lead coalition. Zavetnici and Dveri ran jointly in 2023. One scenario excludes that entire joint list; the other includes it. No party split or individual voter transfer is invented.

The retrieved total reports do not enumerate all lead-list members in **Mionica, Sečanj and Sevojno**. Partner dummies and coalition-adjusted proxy outcomes are NULL for these municipalities. `coalition_bridge` retains a clearly marked raw SNS-family reference for audit. SPS and SRS have separate local lists in Sečanj, but that does not establish the full membership of its lead list.

**Aranđelovac's published list votes sum to 25,543 while its published valid-ballot total is 25,547.** Rendered pages confirm the source's four-vote discrepancy. Both figures are retained. Its local row has `eligible_for_default_model=0`; require both observations of a pair to be eligible when modelling, rather than dropping just its local row. Twelve complete pairs remain in the default count-reconciled panel. Nine complete pairs remain for the documented coalition-family scenarios after that exclusion. The supplied SQL applies these pair-level restrictions.

Sečanj's retrieved total report does not supply mandates, so these values are NULL. Parliamentary mandates are not collected in this version. The 2022 table supplies list votes and valid-vote shares; 2022 register/turnout totals are not joined. The current economic data are exposed as dated series, not silently merged as pre-election controls. The fixed census fields are pre-2023 structural covariates; do not infer that later statistical revisions were available at an earlier prediction date.

This version does not include complete recent local polling-station protocols, historical same-day local/parliamentary ballot pairs, campaign finance/media exposure, or a poll archive. Those are additional research inputs, not empty outcomes coded as zero. The package covers the core municipal comparison and national 2022/2023 vote history; it does not claim to exhaust every public Serbian dataset.

## Denominators, geography and dates

Shares and rates are fractions, e.g. 0.52 means 52%. Changes ending in `_pp` are percentage points. Turnout uses voters who attended divided by registered voters. Ballots cast can be lower than attendance. Invalid-ballot rates use ballots cast. Parliamentary `vote_share_valid` uses the list-vote sum; local shares use published valid ballots, with the Aranđelovac discrepancy flagged.

Registered voters are not census residents. Some registered voters reside abroad, and statistical population and electoral registration have different reference concepts. Municipal turnout and individual party switching cannot be inferred from census ratios.

The geographical tables contain overlapping national, regional, district and city aggregates. **Do not sum every row for a national total.** Use `geo_id='RS'` where a national row exists, or `is_2023_leaf=1` to sum the disjoint 2023 election units. Keep abroad (33000) and institutional voting (55001) visible; exclude them explicitly only when studying resident-municipal covariates. Do not sum sex, age or settlement totals with their component categories in `context_series`.

Statistical series retain official provisional/missing status flags. Blank cells mean missing, not applicable, unavailable or not collected. Unknown coalition membership is not absence. Retrieval dates identify this snapshot; publication dates remain NULL if an exact date was not established. The source manifest includes public read-only POST query parameters where a results page generated a dataset dynamically.

## BigQuery loading

Each of the 12 CSVs has a matching `schemas/<table>.schema.json`. Files use UTF-8 without a BOM, comma delimiters, a header row, double-quote escaping, LF line endings, ISO dates, decimal points and empty cells for NULL. Do not enable schema autodetection; use the supplied schemas to preserve identifiers and all-null columns. The package is ready to load, but has not been uploaded into your Google Cloud account.

In BigQuery's upload dialog choose CSV, provide the schema, and set header rows to skip to **1**. Keep maximum bad records at **0**.

For the CLI, after changing to the extracted package folder:

```bash
bq load --source_format=CSV --skip_leading_rows=1 --encoding=UTF-8 \
  PROJECT_ID:DATASET_ID.model_panel_13 \
  model_panel_13.csv schemas/model_panel_13.schema.json
```

`load_to_bigquery.sh PROJECT_ID DATASET_ID` loads all tables into an existing empty dataset. It checks for pre-existing destination tables before starting, so a rerun cannot silently append duplicates. It does not create a dataset or change sharing permissions. Choose a dataset/location appropriate for your account before running it. `analysis.sql` contains national reconciliation, properly restricted paired analysis and cohort summaries; replace `PROJECT_ID.DATASET_ID` there.

`validation_summary.json` records numerical checks, and `table_manifest.json` records row counts, grains, keys, sizes and file hashes. All 8,273 station rows reconcile, and their national sum matches registered **6,500,666**, attendance **3,820,746**, ballots cast **3,815,007**, invalid **104,029**, and valid **3,710,978**. Every available disjoint 2023 parliamentary list-vote cell matches the corresponding RIK station aggregation. Every 2023 geographical total matches its list-vote sum. Local transcriptions were visually checked; the single unresolved discrepancy is retained and flagged above.

The ZIP includes the 24 used source files and the transcription/build scripts. The builder's source-file paths are relative to `scripts/raw`; run `scripts/build_dataset.py` after making the documented Python dependencies available (standard library, lxml, openpyxl). The included CSVs can be loaded directly without rebuilding. Rebuilding writes a fresh `outputs/serbia_bigquery` folder beneath the extracted package; its rows can be compared with the supplied file hashes. The optional export checker also uses NumPy.

Primary source portals: [RIK documents](https://www.rik.parlament.gov.rs/dokumenta/sr/41985), [2023 parliamentary votes](https://data.stat.gov.rs/Home/Result/07021101?languageCode=en-US), [RZS open-data catalogue](https://opendata.stat.gov.rs/odata/?id=en-us), [wages by residence](https://data.stat.gov.rs/Home/Result/2403040103?languageCode=en-US), [employment by residence](https://data.stat.gov.rs/Home/Result/24021308?languageCode=en-US). Loading specifications: [BigQuery CSV documentation](https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-csv). Exact download URLs and SHA-256 hashes are in `source_manifest.csv`.
