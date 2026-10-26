
import re
import pandas as pd
import numpy as np


ALIASES = {
    "district": [
        "district", "district_name", "district name",
        "districtname", "dist_name"
    ],
    "state": [
        "state", "state_name", "state name", "statename"
    ],
    "crop": [
        "crop", "crop_name", "crop name", "commodity",
        "cropname"
    ],
    "year": [
        "year", "year_value", "financial year", "crop year",
        "crop_year", "year_value"
    ],
    "season": [
        "season", "crop season", "crop_season"
    ],
    "area": [
        "area", "area_hectares", "area hectares",
        "area (hectares)", "area_in_hectares",
        "cultivated area", "area_ha"
    ],
    "production": [
        "production", "production_tonnes", "production tonnes",
        "production (tonnes)", "production_in_tonnes",
        "quantity", "production_tons", "production_mt"
    ],
    "yield": [
        "yield", "yield_value", "yield (kg/ha)",
        "productivity", "yield_kg_ha", "yield_tonnes_per_hectare"
    ],
}


def normalize_column_name(name):
    """Normalize headers by removing punctuation and extra spaces."""
    name = str(name).strip().lower()
    name = name.replace("-", "_")
    name = re.sub(r"[/()]+", "_", name)
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def validate_and_clean(raw: pd.DataFrame):
    """Validate CSV data and return standardized columns plus a report."""

    if raw is None or raw.empty:
        return pd.DataFrame(), {
            "status": "failed",
            "message": "The uploaded file is empty.",
            "missing_required_columns": [
                "district", "crop", "year", "production"
            ],
            "rows_received": 0,
            "valid_rows": 0,
            "rejected_rows": 0,
        }

    df = raw.copy()
    df.columns = [normalize_column_name(c) for c in df.columns]

    # Normalize aliases using the same function as the input headers.
    normalized_aliases = {
        canonical: {normalize_column_name(alias) for alias in names}
        for canonical, names in ALIASES.items()
    }

    rename = {}
    used_canonical = set()

    for col in df.columns:
        for canonical, aliases in normalized_aliases.items():
            if col in aliases and canonical not in used_canonical:
                rename[col] = canonical
                used_canonical.add(canonical)
                break

    df = df.rename(columns=rename)

    required = ["district", "crop", "year", "production"]
    missing = [col for col in required if col not in df.columns]

    if missing:
        return pd.DataFrame(), {
            "status": "failed",
            "message": "Required CSV columns could not be identified.",
            "missing_required_columns": missing,
            "received_columns": list(raw.columns),
            "normalized_columns": list(df.columns),
            "rows_received": int(len(raw)),
            "valid_rows": 0,
            "rejected_rows": int(len(raw)),
        }

    # Optional text fields.
    for col, default in [("state", "Unknown"), ("season", "Unknown")]:
        if col not in df.columns:
            df[col] = default

        df[col] = (
            df[col]
            .fillna(default)
            .astype(str)
            .str.strip()
            .replace("", default)
        )

    # Required text fields.
    for col in ["district", "crop"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Numeric fields.
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    for col in ["area", "production", "yield"]:
        if col not in df.columns:
            df[col] = np.nan

        # Handle comma-formatted numbers such as "12,500".
        df[col] = (
            df[col]
            .astype("string")
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    invalid = (
        df["district"].eq("")
        | df["crop"].eq("")
        | df["year"].isna()
        | df["production"].isna()
        | (df["production"] < 0)
        | (df["year"] < 1900)
        | (df["year"] > 2200)
        | (df["year"] % 1 != 0)
    )

    rejected_rows = int(invalid.sum())
    df = df.loc[~invalid].copy()

    if not df.empty:
        df["year"] = df["year"].astype(int)

        for col in ["district", "crop", "state", "season"]:
            df[col] = df[col].str.title()

        # Negative area is invalid; missing area is permitted.
        bad_area = df["area"].notna() & (df["area"] < 0)
        rejected_rows += int(bad_area.sum())
        df = df.loc[~bad_area].copy()

        # Negative yield is invalid; missing yield is permitted.
        bad_yield = df["yield"].notna() & (df["yield"] < 0)
        rejected_rows += int(bad_yield.sum())
        df = df.loc[~bad_yield].copy()

    rows_before_deduplication = len(df)
    df = df.drop_duplicates()
    duplicates_removed = rows_before_deduplication - len(df)

    output_columns = [
        "state", "district", "crop", "year",
        "season", "area", "production", "yield"
    ]

    df = df[output_columns].reset_index(drop=True)

    report = {
        "status": "success" if not df.empty else "failed",
        "rows_received": int(len(raw)),
        "valid_rows": int(len(df)),
        "rejected_rows": int(rejected_rows),
        "duplicate_rows_removed": int(duplicates_removed),
        "required_columns": required,
        "output_columns": output_columns,
        "note": (
            "Confirm area and production units before calculating yield. "
            "The calculated yield is production divided by area only when "
            "both measurements use compatible units."
        ),
    }

    return df, report
