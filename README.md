# Serbian Parliamentary Election Forecasting

This project develops a transparent electoral forecasting workflow for Serbia using municipal electoral data, Python, Google Colab and Google BigQuery.

The analysis examines SNS-led, student-backed, SPS, opposition and minority-list scenarios without assuming a winner.

## Three separate electoral outcomes

The workflow distinguishes:

1. **National votes:** turnout, vote totals and vote shares for each electoral list.
2. **Parliamentary seats:** threshold eligibility and seat allocation under the configured electoral rules.
3. **Coalition outcomes:** parliamentary majorities and government-formation scenarios under explicit compatibility assumptions.

Government-formation estimates depend on coalition assumptions as well as election results.

## Data and approach

The repository contains historical electoral records, geographic identifiers, contextual data, imported external observations, configurable assumptions, SQL queries, Python modules and archived results.

The workflow considers:

- Geographic differences in turnout and electoral support.
- Recent local-election information, with uncertain applicability to parliamentary voting.
- Polling signals and differences between pollsters.
- Minority lists and geographically concentrated support.
- Threshold sensitivity, including scenarios involving SPS.
- Monte Carlo uncertainty and alternative coalition combinations.

**National participation of 4.3–4.4 million voters is a scenario assumption, not an independently verified turnout prediction.**

Municipal changes cannot establish individual voter switching. Political departures or endorsements also do not establish how many voters will change their preferences.

## Using the project

Start with `STEP2_run_forecast.ipynb` if the electoral tables are already available in BigQuery. `STEP1_load_data.ipynb` provides an optional data-loading workflow.

Source documentation is recorded in `data/serbia_bigquery/source_manifest.csv`. Model parameters and scenario assumptions are maintained in `config/`.

Cloud connection identifiers are entered at runtime. Credentials should remain outside the repository, and executed notebooks should have their outputs cleared before sharing.

## Project status

This is a work in progress. The included results are archived, scenario-conditional outputs. Their presence does not establish forecast accuracy or confirm that every political input, election arrangement or electoral-law setting has been verified.

Updated forecasts require source review, appropriate backtesting and validation of the applicable electoral rules. The purpose is to make the assumptions, calculations and uncertainty inspectable.
