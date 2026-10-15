#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  printf 'Usage: %s PROJECT_ID EXISTING_EMPTY_DATASET_ID\n' "$0" >&2
  exit 2
fi
bq_project="$1"
bq_dataset="$2"
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v bq >/dev/null
bq --project_id="$bq_project" show "$bq_project:$bq_dataset" >/dev/null
tables=(territories polling_stations_2023 election_totals list_votes context_series municipality_context_2022 coalition_bridge model_panel_13 paired_changes_13 source_manifest quality_issues data_dictionary)
for table_name in "${tables[@]}"; do
  if bq --project_id="$bq_project" show "$bq_project:$bq_dataset.$table_name" >/dev/null 2>&1; then
    printf 'Destination table already exists: %s. Use an empty dataset to avoid duplicates.\n' "$table_name" >&2
    exit 1
  fi
done
for table_name in "${tables[@]}"; do
  bq --project_id="$bq_project" load \
    --source_format=CSV --skip_leading_rows=1 --encoding=UTF-8 \
    --field_delimiter=',' --quote='"' --max_bad_records=0 \
    "$bq_project:$bq_dataset.$table_name" \
    "$package_dir/$table_name.csv" "$package_dir/schemas/$table_name.schema.json"
done
