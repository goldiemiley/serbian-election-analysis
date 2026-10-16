# Serbia parliamentary election forecasting project

Privacy-prepared copy of the uploaded v3 project, the two STEP notebooks, the electoral CSV package, and the separately uploaded result snapshot. Votes, parliamentary seats, and coalition arithmetic are separate stages. Begin with `run_forecast.ipynb` if the electoral tables are already in BigQuery.

This copy removes the owner's cloud project ID, clears notebook outputs and identifying metadata, and uses hidden runtime prompts for project and dataset IDs. The statistical implementation, observed CSVs, numerical result tables, and scenario assumptions are preserved. **Privacy preparation is not statistical validation or verification of the election schedule, sources, or electoral law.** The uploaded results are conditional snapshots, not an updated forecast.

## Files

| Path | Use |
|---|---|
| `run_forecast.ipynb` | Main Google Colab notebook. Connection IDs are entered at runtime. |
| `Serbia_Election_Forecast_2026.ipynb`, `Step1_Load_Data_to_BigQuery.ipynb` | Privacy-prepared copies of the notebooks originally bundled in v3. |
| `src/`, `sql/`, `tests/`, `tools/` | Original forecasting modules, SQL, tests, and notebook builders; connection setup in the builders is sanitized. |
| `config/` | Uploaded list classifications, legal parameters, model settings, and scenario assumptions. |
| `data_to_import/` | Uploaded external political inputs and templates; retain their verification labels. |
| `data/serbia_bigquery/` | The 12 original electoral/context CSVs, schemas, manifests, and loader documentation. |
| `sample_outputs/` | The separately uploaded `forecast_outputs.zip`, unpacked once. Numerical CSVs are unchanged. |
| `docs/README_UPSTREAM.md`, `ARCHITECTURE.md`, `RESEARCH_LEADS.md` | Supplied methodological documentation and limitations. |
| `UPLOAD_TO_GITHUB.md`, `PRIVACY_REVIEW.md` | Upload instructions and the scope of the privacy review. |

## Optional local checks

Run commands in a terminal opened inside this repository:

```bash
python3 tools/privacy_check.py
python3 -m pip install -r requirements.txt
python3 -I -m pytest tests -q --pkg data/serbia_bigquery
```

The privacy checker reports file locations and issue types, without printing matched secret values. Passing it cannot prove that arbitrary prose or future uploaded documents contain no personal information. Review new data and documents before committing them. `.gitignore` applies to Git additions; it does not filter GitHub's browser file uploads or erase earlier commits.

## Data provenance and rights

The electoral and context files are aggregate observations with geography identifiers. Their source URLs, publishers, dates, hashes, and documented issues are in `data/serbia_bigquery/source_manifest.csv` and `quality_issues.csv`. Source download PDFs, spreadsheets, HTML captures, and collection scripts from the earlier archive are omitted from this upload copy; the manifest still documents their origin. No individual voter records were identified in the included table schemas.

No redistribution license was supplied. No license is invented here. Keep the repository private while reviewing permission to redistribute code, compiled polls, and source-derived data. Public political figures and public source URLs remain in the electoral records and documentation.
