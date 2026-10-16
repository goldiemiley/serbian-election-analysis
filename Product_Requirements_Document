# Task: Build an End-to-End Multi-Stage Forecasting Model for the Next Serbian Parliamentary Election

## 1. Role and Objective

I want to develop a rigorous, transparent, statistically defensible electoral forecasting model for the next Serbian parliamentary election.

The primary objective is to estimate the probabilities of:

1. The SNS-led electoral list receiving the most votes and parliamentary seats.
2. The student-backed electoral list receiving the most votes and parliamentary seats.
3. SPS and other electoral lists obtaining parliamentary representation.
4. Different parties or alliances reaching a parliamentary majority.
5. SNS-led, student-backed, or alternative coalitions being able to form a government.

**Important: Forecast three separate outcomes sequentially:**

- **Stage 1:** National votes and vote shares.
- **Stage 2:** Parliamentary seat allocation under Serbian electoral law.
- **Stage 3:** Probabilities of parliamentary majorities and feasible government coalitions.

Do not confuse winning the popular vote, obtaining the most seats, and forming a government.

This is a national-level forecast constructed from municipality-level observations, recent electoral information, and political developments.

The analysis must remain politically neutral and should not assume that SNS, students, or any other group will win.

---

## 2. Existing Data and SQL Query

I already have an existing BigQuery SQL query and electoral dataset.

**The existing query is the starting point and primary reference for the entire analysis.**

Before developing the model:

1. Inspect my existing query and identify the source tables, available variables, date coverage, elections, electoral lists, geographic identifiers, and data structure.
2. Explain which analytical requirements are already supported by the existing data.
3. Identify missing variables and additional data sources required.
4. Reuse the existing query wherever appropriate, rather than unnecessarily rewriting it.
5. Build additional SQL queries for each forecasting stage, using actual dataset names, column names, and relationships discovered in the provided data.
6. Verify the accuracy and completeness of election and municipality records.

### Strict coding rules

- Retrieve observations dynamically from BigQuery.
- Use the actual table schema and available fields.
- Use SQL aggregation, joins, and transformations.
- Create configurable reference tables for party/list classifications and electoral alliances.
- Retrieve configuration values from a central parameter table, configuration file, or Google Colab configuration cell.
- Keep scenario assumptions separate from observed data.
- Use reusable functions instead of municipality-specific code.
- Ensure the model works when new elections or observations are added.

Values that represent electoral law, user assumptions, or simulation settings may be defined in a clearly labeled, centralized configuration section, with their sources documented. They must not be scattered as unexplained numerical constants throughout SQL or Python.

Do not invent missing columns, tables, or observations.

If my query or data is not visible, first explain which specific source objects or schema details are needed. You may develop a reusable framework with clearly identified placeholders, but do not present placeholder code as already executable.

---

## 3. National Forecast and Turnout

Use **4.3–4.4 million participating voters** as the user-specified national turnout forecast range.

This is a scenario assumption, not an independently verified prediction.

Estimate:

- National participation and its geographic distribution.
- Municipality-level turnout.
- Municipality-level valid and invalid ballots.
- Party/list vote shares.
- National vote totals.
- Previously abstaining voters potentially participating in the next election.

The model should not distribute additional voters proportionally to historical vote shares without justification.

I want to understand how additional participation may affect SNS, students, SPS, opposition lists, and minority lists.

Develop municipality-level turnout forecasts and calibrate the aggregate forecast to several national turnout scenarios within the specified range.

Distinguish registered voters, ballots cast, valid votes, invalid ballots, and the legal denominator used for electoral thresholds.

---

## 4. Different Treatment of Municipalities with Recent Elections

This is one of the most important requirements.

Some Serbian municipalities conducted local elections more recently than others.

These recent elections may contain valuable information about political changes that historical parliamentary results cannot capture.

Classify municipalities dynamically into:

- Municipalities with recent local elections.
- Municipalities without recent local elections.
- Municipalities with multiple relevant historical election observations.

For municipalities with recent elections, compare historical performance with the latest results, accounting for:

- Changes in voter turnout.
- SNS and governing-coalition performance.
- Student-backed local electoral lists.
- Traditional opposition parties.
- SPS and its coalition partners.
- Local minority parties.
- Candidate and coalition differences.
- Local political conditions.

**Do not directly substitute local election results for parliamentary vote shares.**

Local and national electoral behavior may differ.

Investigate appropriate approaches including:

- Hierarchical Bayesian modeling.
- Municipality-level political swing models.
- Partial pooling.
- Panel-data analysis.
- Difference-in-differences or event-study designs, where causal identification is supported.
- Time-weighted updates.

Recommend the most statistically appropriate method given the actual available data.

Also investigate whether holding a recent municipal election could independently affect subsequent parliamentary voting through political mobilization or organizational changes.

Separate this potential effect from the information contained in the local election result itself.

If a causal effect cannot be identified, model it as an uncertain scenario rather than a confirmed adjustment.

---

## 5. Political Realignment and Changing Political Climate

The model must incorporate changing political conditions without assuming that every reported political development directly changes voter behavior.

An example is the October 2026 reports of SPS members leaving the party and some expressing support for the student movement.

Investigate and verify the relevant developments from credible, dated sources.

Distinguish:

1. Politicians leaving a party.
2. Politicians formally joining another electoral organization.
3. Politicians publicly endorsing an electoral list.
4. Actual changes in voters' preferences.

These are different observations and must not be treated as equivalent.

### Voter-transition model

Develop a model estimating potential movements among:

- SNS-led list.
- Student-backed list.
- SPS-led list.
- Traditional opposition parties.
- Minority lists.
- Other electoral lists.
- Abstention or nonparticipation.

Estimate transition probabilities with uncertainty rather than imposing arbitrary transfer percentages.

Consider both national-level shocks and geographically concentrated effects.

Include political-event scenarios such as:

- No significant SPS-to-student voter movement.
- Moderate voter realignment.
- Stronger SPS decline.
- Increased student mobilization.
- Increased SNS voter retention.
- Opposition fragmentation.
- Changes in public opinion due to subsequent political developments.

Do not assume that a politician's defection produces an equal proportional movement among their previous supporters.

Do not interpret changes in aggregate municipality results as direct evidence of individual-level voter switching without addressing ecological inference limitations.

### Opinion polls and prediction markets

Investigate relevant, current data from:

- Credible Serbian opinion polls.
- Polymarket.
- Meridianbet.
- Other verifiable election-related sources where useful.

Record source, publication date, sample information, methodology, market liquidity where available, and data limitations.

Use polls as imperfect measurements of voter preferences, accounting for sampling, timing, and pollster effects.

Use betting-market probabilities as external forecasting signals or validation benchmarks, rather than treating betting odds as observed vote shares.

Explain how to prevent double-counting information when political events, polling changes, and prediction markets react to the same developments.

---

## 6. Minority Parties and Geographic Voting Concentration

Model Serbia's minority electoral lists separately rather than automatically combining them into an "Others" category.

Identify relevant minority lists dynamically from historical data and verified information about the forthcoming election.

Consider geographically concentrated voting patterns, including relevant areas of Vojvodina, Sandžak, and southern Serbia.

Estimate:

- Minority-list vote totals.
- Municipality-level electoral support.
- Historical minority-party turnout.
- Changes in minority-list participation.
- Competition between multiple minority lists.
- Possible transfers between minority lists and broader national political groups.

Verify which electoral lists qualify for minority-list treatment under current Serbian election law.

Apply the appropriate special seat-allocation rules only to eligible lists.

Do not assume that every voter belonging to a national minority necessarily votes for a minority party.

---

## 7. Parliamentary Threshold and Seat Allocation

The model must reproduce the applicable Serbian parliamentary electoral system.

Verify the current legal rules through authoritative sources, including:

- The ordinary 3% electoral threshold.
- The legally prescribed denominator used to calculate this threshold.
- Special treatment of qualified national-minority lists.
- The applicable D'Hondt calculation and minority-list adjustments.
- The number of parliamentary seats.
- Any other legally relevant rules.

The electoral system must be coded as a reproducible allocation function, not approximated by multiplying each party's national vote share by the number of parliamentary seats.

### Threshold sensitivity

Analyze the effect of lists finishing immediately above or below 3%.

Pay particular attention to SPS.

For instance, if SPS loses support to the student-backed list and falls below the threshold, the effects may include:

1. More votes for students.
2. Loss of SPS parliamentary representation.
3. Redistribution of seats among qualifying lists.
4. Changes to possible governing-coalition majorities.

Estimate the probability that every non-exempt electoral list crosses the 3% threshold.

Model the relationship between vote movements and seat allocation as potentially nonlinear.

All threshold and seat calculations must be repeated for every simulated election outcome.

---

## 8. Government Formation and Coalition Probabilities

After computing seats, estimate:

- Probability each list receives the most seats.
- Probability each list independently obtains a parliamentary majority.
- Probability a predefined coalition reaches the majority threshold.
- Probability no feasible coalition has a majority.
- Potential influence of SPS and minority-list representation.

Distinguish mathematical coalition possibilities from politically plausible coalition agreements.

Do not assume every opposition list will join the student-backed list or that every minority party will join an SNS government.

Define coalition-compatibility assumptions explicitly and support them with available evidence.

Where government-formation probabilities cannot be statistically identified from voting data alone, clearly state that they are scenario-conditional estimates.

Report results under alternative coalition-compatibility assumptions.

---

## 9. Statistical Modeling and Uncertainty

I want a rigorous probabilistic model, not just a deterministic forecast.

Recommend an appropriate combination of:

- Municipality-level turnout forecasting.
- Hierarchical vote-share forecasting.
- Multinomial or other compositional vote-share modeling.
- National and municipality-level correlated political shocks.
- Bayesian updating where appropriate.
- Time-dependent political adjustments.
- Monte Carlo simulation.
- Exact electoral-law seat allocation.

Ensure that predicted vote shares sum to 100% in every simulated municipality.

Ensure that total votes are internally consistent with the turnout and valid-ballot forecasts.

The model must capture dependencies between competing parties rather than forecasting each party independently without constraints.

Estimate confidence or credible intervals and explicitly distinguish:

- Sampling uncertainty.
- Model uncertainty.
- Political-event uncertainty.
- Turnout uncertainty.
- Coalition-formation uncertainty.

Use reproducible random seeds and documented scenario weights.

Avoid false precision where the data cannot support narrow uncertainty intervals.

---

## 10. Required Step-by-Step Deliverables

**Do not immediately jump to the final Python model. Build the analysis sequentially.**

For each analytical stage, provide:

1. **Objective:** What are we estimating, and why?
2. **Input:** Which existing BigQuery tables, columns, and external observations are required?
3. **SQL query:** A complete BigQuery Standard SQL query for preparing or calculating the relevant data.
4. **Explanation:** What each query calculates and how the output is interpreted.
5. **Python implementation:** Google Colab-compatible code that consumes the actual SQL results.
6. **Validation:** Tests for missing data, inconsistent results, and incorrect assumptions.
7. **Output:** Expected tables, charts, statistics, and intermediate results.
8. **Limitations:** Which conclusions are supported by evidence and which depend on assumptions.

Organize the implementation into the following stages:

| Stage | Analytical task |
|---|---|
| 0 | Data inventory, source verification, query inspection and data-quality checks |
| 1 | Historical electoral baseline and party/list harmonization |
| 2 | Municipality-level turnout forecasting |
| 3 | National turnout calibration |
| 4 | Recent municipal-election analysis and local swing estimation |
| 5 | National polling signals and political-event adjustments |
| 6 | SNS, student-backed list, SPS and other-list vote-share forecasts |
| 7 | Minority-list forecasting |
| 8 | National vote aggregation |
| 9 | Threshold sensitivity and parliamentary seat allocation |
| 10 | Coalition and government-formation scenarios |
| 11 | Monte Carlo simulations and uncertainty estimation |
| 12 | Backtesting, model comparison and sensitivity analysis |
| 13 | Final national forecast, visualizations and reporting |

Each step should produce outputs that can be consumed by the next stage.

---

## 11. Google Colab Implementation

Build a complete, executable, modular Python forecasting pipeline for **Google Colab**, using BigQuery as the primary data source.

The implementation should include:

- Google Colab authentication.
- Google Cloud and BigQuery connection.
- Dynamic execution of the provided or derived SQL queries.
- Data extraction into pandas DataFrames.
- Data cleaning and validation.
- Exploratory data analysis.
- Model training and calibration.
- Scenario generation.
- Monte Carlo simulation.
- Vote aggregation.
- Electoral-law seat allocation.
- Coalition scenario analysis.
- Charts and summary tables.
- Export of results to CSV and other useful formats.

Use appropriate Python statistical libraries based on the selected methodology.

### Additional code requirements

1. No hardcoded municipality-specific results or historical vote totals.
2. No fabricated example observations inserted into the actual forecast.
3. Avoid manually hardcoding the complete set of parties into the estimation logic.
4. Use maintainable configuration tables for list identification, alliances, and coalition scenarios.
5. Separate observed data, inferred quantities, scenario assumptions, and legal parameters.
6. Use reusable Python functions and classes where appropriate.
7. Validate SQL and Python outputs at each stage.
8. Add explanatory Markdown cells and code comments.
9. Provide all dependencies and installation instructions.
10. Make the notebook executable from beginning to end once the required datasets and configuration are available.
11. Do not silently replace missing real data with arbitrary assumptions.
12. Clearly mark any external data that must be obtained or imported manually.

Any future updates to election results, polls, or political events should be incorporated by updating the underlying tables or configuration rather than rewriting the entire forecasting pipeline.

---

## 12. Backtesting and Model Selection

Before reporting national forecasts, evaluate predictive performance using historical electoral data.

Where the available data permits:

- Conduct time-based backtesting.
- Compare municipality-level and national vote-share errors.
- Measure turnout prediction errors.
- Evaluate party ranking and parliamentary seat allocation.
- Assess uncertainty calibration.
- Test whether incorporating recent municipal elections improves predictions.
- Compare simpler baseline models against more complex hierarchical approaches.

Prevent data leakage: historical backtests must use only information available before the corresponding election.

Select the preferred model based on demonstrated performance, statistical suitability, interpretability, and data availability.

Do not assume the most complex model is automatically the best.

---

## 13. Required Final Forecast Outputs

The final model should provide the following:

### A. National voting forecast

For every relevant electoral list:

- Expected votes.
- Expected vote share.
- Median forecast.
- 80% and 95% prediction or credible intervals.
- Probability of receiving the most votes.

### B. Parliamentary forecast

- Expected seats.
- Median seats.
- Seat distribution intervals.
- Probability of winning the most seats.
- Probability of obtaining a parliamentary majority.
- Probability of passing the applicable electoral threshold.

### C. Coalition forecast

- Feasible governing-coalition combinations.
- Estimated seats for each combination.
- Probability of obtaining a parliamentary majority.
- Sensitivity to alternative coalition assumptions.

### D. Municipality-level forecast

- Turnout forecasts by municipality.
- Predicted vote shares by municipality.
- Recent local-election effects.
- Areas contributing most to changes in national forecasts.
- Municipality-level prediction uncertainty.

### E. Scenario comparison

Compare the baseline with:

- Higher and lower turnout within the specified range.
- Stronger student mobilization.
- Stronger SNS voter retention.
- SPS voter defection scenarios.
- SPS falling below 3%.
- Opposition consolidation versus fragmentation.
- Alternative minority-list outcomes.
- Alternative coalition assumptions.

### F. Visualization

Create clear charts showing:

- National vote-share distributions.
- Parliamentary seat distributions.
- Probability of each electoral outcome.
- Municipality-level voting changes.
- Turnout sensitivity.
- SPS threshold sensitivity.
- Coalition-majority scenarios.
- Forecast changes over time as new observations arrive.

Where suitable, create interactive charts in Google Colab.

---

## 14. Research Integrity and Analytical Standards

Maintain a clear distinction between verified facts, observed data, estimated relationships, and scenario assumptions.

Do not invent:

- Election results.
- Polling observations.
- Political defections.
- Vote-transfer percentages.
- Minority-list eligibility.
- Coalition agreements.
- Betting-market probabilities.
- Election dates.

Verify current electoral rules and the actual election schedule rather than relying on previous conversation claims.

Use citations or source references for external political developments and legal claims.

If an event is reported but its electoral impact has not been measured, represent its possible effect through uncertain parameters and sensitivity analysis.

If different scenarios imply substantially different forecasts, report that uncertainty rather than hiding it in a single headline prediction.

The objective is a statistically defensible electoral forecast, not a model designed to favor a political party.

---

## 15. How I Want You to Begin

**Start with the analytical architecture and Stage 0, not with an unexplained final prediction.**

1. Review my existing BigQuery query.
2. Explain the dataset structure and its analytical potential.
3. Identify what the existing data can and cannot support.
4. Design the end-to-end forecasting workflow.
5. Recommend the specific statistical approach for each stage and justify why.
6. Identify the required data outputs and dependencies between stages.
7. Produce the first executable BigQuery SQL query and its corresponding Google Colab Python code.
8. Explain how the output of that stage will be used by subsequent stages.

Continue sequentially through the analytical stages, creating working SQL and Python components.

Whenever the existing data is sufficient, implement the analysis directly. Whenever required data is missing, state precisely what is missing and how it affects the forecast.

**Final requirement:** The completed project must be reproducible, data-driven, parameterized, statistically validated, politically neutral, and capable of updating the forecast when new electoral or political information becomes available.
