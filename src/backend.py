"""Backends: BigQuery (production, Colab) and the thin interface the rest of the pipeline relies on.

The DuckDB stand-in used by the tests lives in tests/harness.py and implements the same interface.
This file is the only place that imports google.cloud.bigquery, so it is only imported inside Colab.
"""
import pandas as pd

from coerce import coerce_df

_BQ_TYPES = {'STRING': 'STRING', 'INT64': 'INT64', 'FLOAT64': 'FLOAT64', 'BOOL': 'BOOL', 'DATE': 'DATE', 'TIMESTAMP': 'TIMESTAMP'}


def normalize_df(df):
    """Make query results from any backend look the same to the numerical code.

    BigQuery clients return pandas nullable dtypes (Int64, boolean, string, Float64) and 'dbdate'; the model code wants plain numpy
    columns. Nullable ints become int64 when there is no NA, else float64 (NA -> NaN); nullable booleans become bool when there is
    no NA, else object; strings become object with NaN for missing; dates become datetime64."""
    import numpy as np
    df = df.copy()
    for c in df.columns:
        dt = str(df[c].dtype)
        s = df[c]
        if dt in ('dbdate', 'dbtime'):
            df[c] = pd.to_datetime(s)
        elif dt.startswith(('Int', 'UInt')):
            df[c] = s.astype('int64') if not s.isna().any() else s.astype('float64')
        elif dt == 'Float64' or dt == 'Float32':
            df[c] = s.astype('float64')
        elif dt == 'boolean':
            df[c] = s.astype(bool) if not s.isna().any() else s.astype(object).where(s.notna(), None)
        elif dt == 'string':
            df[c] = s.astype(object).where(s.notna(), np.nan)
        elif dt == 'object' and s.notna().any() and hasattr(s.dropna().iloc[0], 'isoformat') and not isinstance(s.dropna().iloc[0], str):
            df[c] = pd.to_datetime(s)
        if hasattr(df[c].dtype, 'tz') and getattr(df[c].dtype, 'tz', None) is not None:
            df[c] = df[c].dt.tz_localize(None)
    return df


class BigQueryBackend:
    name = 'bigquery'

    def __init__(self, project, dataset, location=None):
        from google.cloud import bigquery
        self._bq = bigquery
        self.client = bigquery.Client(project=project, location=location)
        self.dataset_ref = f'{project}.{dataset}'

    def _fmt(self, sql):
        return sql.replace('{DS}', self.dataset_ref)

    def query(self, sql):
        df = self.client.query(self._fmt(sql)).to_dataframe(create_bqstorage_client=False)
        return normalize_df(df)

    def execute(self, sql):
        self.client.query(self._fmt(sql)).result()

    def table_exists(self, table):
        from google.api_core.exceptions import NotFound
        try:
            self.client.get_table(f'{self.dataset_ref}.{table}')
            return True
        except NotFound:
            return False

    def _schema(self, cols):
        return [self._bq.SchemaField(c, _BQ_TYPES[t]) for c, t in cols]

    def create_empty_if_missing(self, table, cols):
        if self.table_exists(table):
            return False
        self.client.create_table(self._bq.Table(f'{self.dataset_ref}.{table}', schema=self._schema(cols)))
        return True

    def replace_table_from_df(self, table, df, cols):
        df = coerce_df(df, cols)
        job = self.client.load_table_from_dataframe(
            df, f'{self.dataset_ref}.{table}',
            job_config=self._bq.LoadJobConfig(schema=self._schema(cols), write_disposition='WRITE_TRUNCATE'))
        job.result()

    def upload_df(self, table, df):
        """Write a model-output DataFrame (schema inferred from dtypes) to {dataset}.{table}."""
        job = self.client.load_table_from_dataframe(
            df, f'{self.dataset_ref}.{table}', job_config=self._bq.LoadJobConfig(write_disposition='WRITE_TRUNCATE'))
        job.result()
