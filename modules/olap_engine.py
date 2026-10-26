import pandas as pd

def aggregate_data(df: pd.DataFrame, dimension: str, metric: str):
    allowed_dimensions = {"state","district","crop","year","season"}
    allowed_metrics = {"production","area","yield"}
    if dimension not in allowed_dimensions or metric not in allowed_metrics:
        raise ValueError("Unsupported dimension or metric")
    if df.empty:
        return pd.DataFrame(columns=[dimension,metric])
    agg = "mean" if metric == "yield" else "sum"
    return (df.groupby(dimension, dropna=False, as_index=False)[metric]
              .agg(agg).sort_values(metric, ascending=False).reset_index(drop=True))
