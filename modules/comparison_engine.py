import pandas as pd

def compare_years(df, districts, crops, previous_year, current_year, metric="production"):
    if metric not in {"production","area","yield"}:
        raise ValueError("metric must be production, area, or yield")
    subset = df[df["district"].isin(districts) & df["crop"].isin(crops) &
                 df["year"].isin([previous_year,current_year])].copy()
    if subset.empty:
        return pd.DataFrame(columns=["district","crop","previous_value","current_value","absolute_change","percentage_change"])
    # Sum is appropriate for additive measures; yield is averaged from the recorded yield values.
    agg = "mean" if metric == "yield" else "sum"
    grouped = subset.groupby(["district","crop","year"], dropna=False)[metric].agg(agg).unstack("year")
    for y in [previous_year,current_year]:
        if y not in grouped.columns:
            grouped[y] = float("nan")
    result = grouped.reset_index().rename(columns={previous_year:"previous_value",current_year:"current_value"})
    result["absolute_change"] = result["current_value"] - result["previous_value"]
    result["percentage_change"] = result.apply(
        lambda r: ((r["absolute_change"] / r["previous_value"]) * 100)
        if pd.notna(r["previous_value"]) and r["previous_value"] != 0 and pd.notna(r["current_value"])
        else float("nan"), axis=1)
    result = result.rename(columns={metric:"metric_value"})
    return result.sort_values(["district","crop"]).reset_index(drop=True)
