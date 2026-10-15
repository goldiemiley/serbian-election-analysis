# Privacy preparation report

This report describes the cleaned upload folder, not an existing GitHub repository. No repository URL, remote history, collaborator list, or account settings were available for inspection. Nothing has been uploaded to GitHub by this preparation.

## Changes

- Replaced the owner's cloud project ID found in the uploaded STEP1 notebook, STEP2 notebook, and v3 README. The specific identifier is not reproduced here.
- Sanitized all four included notebooks: removed saved outputs, execution counts, cell metadata, and original notebook metadata; retained only Python kernel/language metadata.
- Changed notebook connection setup to hidden runtime prompts or environment variables with no private project/dataset defaults. Removed the normal connection-status print that exposed the full dataset reference.
- Updated both notebook generators so rebuilding a notebook does not bake a project or dataset ID from build-time environment variables into it.
- Removed the host OS/kernel fingerprint from the supplied output metadata. Seed, run sizes, scenario settings, and numerical results remain.
- Included one result snapshot from the separately uploaded `forecast_outputs.zip`; excluded the duplicate nested output ZIP and older embedded snapshot.
- Included the 12 original aggregate data CSVs, their schemas, manifests, documentation, and load script. Original cloud-console screenshots, source-download binaries/captures, and collection scripts are outside this upload copy.
- Added `.gitignore`, `.gitattributes`, dependency instructions, a local privacy checker, an upload guide, and a file manifest.

## Checks completed

| Check | Result |
|---|---|
| Common GitHub tokens, Google API keys, AWS access keys, private keys, JSON credentials | No recognized embedded credentials detected in the inspected text files |
| Email addresses, private home/workspace paths, private file/share references | No remaining matches in the cleaned project |
| Source URL user/password fields and credential-like query parameters | No matches in the inspected CSV source URLs |
| Notebook outputs and identifying metadata | Four notebooks structurally checked; no saved execution/output cells |
| Python source syntax | 35 Python files parsed |
| Notebook Python syntax | 52 code cells compiled; cloud/data queries were not executed |
| Notebook generator code templates | 26 templates compiled |
| Hidden input and offline setup behavior | Tested with isolated configuration inputs; passed |
| Privacy scanner detection | Positive detection cases checked; passed |
| `.gitignore` behavior | Credential/generated-file exclusions and retained data/config/result inclusions checked; passed |
| Original aggregate observation CSVs | All 12 files byte-identical |
| Uploaded numerical result CSVs | All 33 files byte-identical |
| Model implementation modules | All 18 files in `src/` byte-identical |
| Stage SQL queries | All 15 files in `sql/` byte-identical |

The saved chart PNGs were checked for metadata; the metadata contained Matplotlib/software and resolution information. They contain generated electoral charts, not the uploaded cloud-console screenshots. No individual voter records were identified in the included table schemas. Public political figure names, electoral list names, geography labels, and public source URLs remain where they belong to the aggregate electoral records.

## Limits

This is a focused file-privacy review. It is not a proof that all possible personal information or secret encodings have been identified. The checker does not inspect arbitrary future binary documents, embedded archives, or Git history. It does not change GitHub account/profile details, collaborators, or repository visibility. An executed notebook or cloud error can disclose identifiers again even when the input prompt is hidden.

The uploaded scientific implementation and assumptions are preserved. Live BigQuery execution, model performance, political-source accuracy, the target election schedule, electoral-law settings, and the supplied forecasting probabilities were not revalidated by this privacy task. No license or permission to redistribute third-party materials is asserted. Keep this copy private while reviewing those matters.
