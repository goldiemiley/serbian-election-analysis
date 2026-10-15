-- STAGE 0.1  Schema contract.
-- Objective : confirm that the dataset you loaded has the columns and types the package itself documents
--             (data_dictionary) and the columns this pipeline's SQL reads (cfg_required_columns).
-- Input     : {DS}.data_dictionary, {DS}.cfg_required_columns, {DS}.INFORMATION_SCHEMA.COLUMNS
-- Output    : {DS}.s0_schema_contract  (one row per expected column; status OK / MISSING_COLUMN / TYPE_MISMATCH)
-- Note      : nothing is hardcoded here. The expected schema is read from the data.
CREATE OR REPLACE TABLE `{DS}.s0_schema_contract` AS
WITH expected AS (
  SELECT table_name, column_name, bigquery_type AS expected_type, 'data_dictionary' AS expectation_source
  FROM `{DS}.data_dictionary`
  UNION ALL
  SELECT table_name, column_name, CAST(NULL AS STRING) AS expected_type, 'cfg_required_columns' AS expectation_source
  FROM `{DS}.cfg_required_columns`
),
actual AS (
  SELECT table_name, column_name, data_type AS actual_type
  FROM `{DS}.INFORMATION_SCHEMA.COLUMNS`
)
SELECT
  e.table_name,
  e.column_name,
  e.expectation_source,
  e.expected_type,
  a.actual_type,
  CASE
    WHEN a.column_name IS NULL THEN 'MISSING_COLUMN'
    WHEN e.expected_type IS NOT NULL AND e.expected_type != a.actual_type THEN 'TYPE_MISMATCH'
    ELSE 'OK'
  END AS status
FROM expected AS e
LEFT JOIN actual AS a
  ON a.table_name = e.table_name AND a.column_name = e.column_name
ORDER BY e.table_name, e.column_name, e.expectation_source;
