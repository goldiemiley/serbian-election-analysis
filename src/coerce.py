"""Type coercion of CSV-sourced DataFrames to a declared BigQuery column list (shared by all backends)."""
import pandas as pd

_TRUE = {'true', '1', 'yes', 'y', 't'}
_FALSE = {'false', '0', 'no', 'n', 'f'}


def _to_bool(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return pd.NA
    s = str(v).strip().lower()
    if s == '':
        return pd.NA
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError(f'cannot read {v!r} as a boolean')


def coerce_df(df, cols):
    """Return a copy of df with exactly the columns in `cols` ((name, bigquery_type) pairs), typed.
    Missing columns become NULL. Empty strings become NULL for every type."""
    df = df.copy()
    for c, t in cols:
        if c not in df.columns:
            df[c] = None
        if t == 'DATE':
            df[c] = pd.to_datetime(df[c].replace('', None), errors='raise').dt.date
        elif t == 'TIMESTAMP':
            df[c] = pd.to_datetime(df[c].replace('', None), errors='raise')
        elif t == 'BOOL':
            df[c] = pd.Series([_to_bool(v) for v in df[c]], index=df.index, dtype='boolean')
        elif t == 'INT64':
            df[c] = pd.to_numeric(df[c].replace('', None), errors='raise').astype('Int64')
        elif t == 'FLOAT64':
            df[c] = pd.to_numeric(df[c].replace('', None), errors='raise').astype('float64')
        else:  # STRING
            df[c] = df[c].astype('string').replace('', pd.NA)
    return df[[c for c, _ in cols]]
