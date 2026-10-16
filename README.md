# Serbia parliamentary election forecasting project

Privacy-prepared copy of the uploaded v3 project, the two STEP notebooks, the electoral CSV package, and the separately uploaded result snapshot. Votes, parliamentary seats, and coalition arithmetic are separate stages. Begin with `STEP2_run_forecast.ipynb` if the electoral tables are already in BigQuery.

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

## Google Colab

1. Open [Google Colab](https://colab.research.google.com/). Choose **File → Upload notebook** and select `STEP2_run_forecast.ipynb` from the extracted folder.
2. Run the configuration cell. Enter your existing Google Cloud **project ID** and BigQuery **dataset ID** in the hidden prompts. The location defaults to **EU**. These identifiers are not written into the source cell.
3. Run the setup cell. When asked for a ZIP, select `Serbia_GitHub_Ready.zip`, or the source ZIP downloaded from your private repository. Both folder names are supported. Authenticate through Google's own Colab prompt.
4. Review the external CSVs and the model/legal parameters before running all stages. The supplied notebook builds or replaces working/configuration tables and can import external tables; existing raw electoral data need not be reloaded.
5. Keep the executed Colab copy private. Before uploading an updated notebook, clear **all outputs**, save a new copy, and check it with `python3 tools/privacy_check.py`. An error message from BigQuery can disclose a project ID even though the inputs were hidden.

If your raw tables have not been loaded, open `STEP1_load_data.ipynb` first, enter the identifiers privately, and select the same cleaned ZIP when prompted. It locates the included `election_totals.csv` and its schema folder. It replaces tables in the dataset you select.

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
