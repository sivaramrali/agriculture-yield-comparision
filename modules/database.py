
import os
from hashlib import sha256

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


DEFAULT_URL = "sqlite:///agriculture.db"


def get_engine() -> Engine:
    """Create a SQLAlchemy engine using SQLite by default."""
    load_dotenv()
    url = os.getenv("DATABASE_URL") or DEFAULT_URL

    return create_engine(
        url,
        pool_pre_ping=True,
    )


def init_db() -> None:
    """Create the star-schema dimension and fact tables."""
    engine = get_engine()

    if engine.dialect.name == "sqlite":
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
    elif engine.dialect.name in ("mysql", "mariadb"):
        pk = "INTEGER PRIMARY KEY AUTO_INCREMENT"
    else:
        raise ValueError(
            f"Unsupported database dialect: {engine.dialect.name}"
        )

    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS dim_district (
            district_id {pk},
            district_name VARCHAR(150) NOT NULL,
            state_name VARCHAR(150) NOT NULL,
            UNIQUE(district_name, state_name)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS dim_crop (
            crop_id {pk},
            crop_name VARCHAR(150) NOT NULL UNIQUE
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS dim_year (
            year_id {pk},
            year_value INTEGER NOT NULL UNIQUE
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS dim_season (
            season_id {pk},
            season_name VARCHAR(100) NOT NULL UNIQUE
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS fact_crop_production (
            fact_id {pk},
            district_id INTEGER NOT NULL,
            crop_id INTEGER NOT NULL,
            year_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            area FLOAT,
            production FLOAT NOT NULL,
            yield_value FLOAT,
            source_fingerprint VARCHAR(64) NOT NULL UNIQUE,
            FOREIGN KEY(district_id)
                REFERENCES dim_district(district_id),
            FOREIGN KEY(crop_id)
                REFERENCES dim_crop(crop_id),
            FOREIGN KEY(year_id)
                REFERENCES dim_year(year_id),
            FOREIGN KEY(season_id)
                REFERENCES dim_season(season_id)
        )
        """,
    ]

    with engine.begin() as conn:
        # SQLite foreign-key enforcement must be enabled separately.
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = ON"))

        for statement in statements:
            conn.execute(text(statement))


def _clean_string(value, default="Unknown") -> str:
    """Convert a value to a safe, non-empty string."""
    if value is None or pd.isna(value):
        return default

    value = str(value).strip()
    return value if value else default


def _upsert_dimension(
    conn,
    table: str,
    id_col: str,
    value_col: str,
    value,
    extra=None,
) -> int:
    """Find a dimension record or insert it if it does not exist."""

    # Only allow known table/column combinations.
    allowed = {
        "dim_district": ("district_id", "district_name"),
        "dim_crop": ("crop_id", "crop_name"),
        "dim_year": ("year_id", "year_value"),
        "dim_season": ("season_id", "season_name"),
    }

    if table not in allowed:
        raise ValueError(f"Unsupported dimension table: {table}")

    if allowed[table] != (id_col, value_col):
        raise ValueError("Invalid dimension table or column configuration")

    extra = extra or {}

    if table == "dim_district":
        state = _clean_string(extra.get("state"))

        query = text("""
            SELECT district_id
            FROM dim_district
            WHERE district_name = :value
              AND state_name = :state
        """)
        params = {"value": value, "state": state}

    elif table == "dim_year":
        query = text("""
            SELECT year_id
            FROM dim_year
            WHERE year_value = :value
        """)
        params = {"value": int(value)}

    else:
        query = text(
            f"SELECT {id_col} FROM {table} WHERE {value_col} = :value"
        )
        params = {"value": value}

    existing = conn.execute(query, params).first()

    if existing is not None:
        return int(existing[0])

    # Insert using SQLAlchemy text() and named parameters.
    if table == "dim_district":
        result = conn.execute(
            text("""
                INSERT INTO dim_district (district_name, state_name)
                VALUES (:value, :state)
            """),
            {"value": value, "state": state},
        )

    elif table == "dim_crop":
        result = conn.execute(
            text("""
                INSERT INTO dim_crop (crop_name)
                VALUES (:value)
            """),
            {"value": value},
        )

    elif table == "dim_year":
        result = conn.execute(
            text("""
                INSERT INTO dim_year (year_value)
                VALUES (:value)
            """),
            {"value": int(value)},
        )

    else:
        result = conn.execute(
            text("""
                INSERT INTO dim_season (season_name)
                VALUES (:value)
            """),
            {"value": value},
        )

    # CursorResult.lastrowid works for the supported SQLite/MySQL inserts.
    new_id = result.lastrowid

    if new_id is None:
        # Fallback: query the inserted dimension by its unique value.
        if table == "dim_district":
            inserted = conn.execute(
                text("""
                    SELECT district_id
                    FROM dim_district
                    WHERE district_name = :value
                      AND state_name = :state
                """),
                {"value": value, "state": state},
            ).first()
        else:
            inserted = conn.execute(
                text(
                    f"SELECT {id_col} FROM {table} "
                    f"WHERE {value_col} = :value"
                ),
                {"value": int(value) if table == "dim_year" else value},
            ).first()

        if inserted is None:
            raise RuntimeError(
                f"Could not retrieve ID for {table}: {value}"
            )

        return int(inserted[0])

    return int(new_id)


def import_dataframe(df: pd.DataFrame) -> int:
    """Import cleaned agriculture records into the star-schema database.

    Expected columns:
    state, district, crop, year, season, area, production, yield
    """
    required = {"district", "crop", "year", "production"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required DataFrame columns: {sorted(missing)}"
        )

    engine = get_engine()
    inserted = 0

    with engine.begin() as conn:
        for _, row in df.iterrows():
            state = _clean_string(row.get("state"))
            district = _clean_string(row.get("district"), "")
            crop = _clean_string(row.get("crop"), "")
            season = _clean_string(row.get("season"))

            if not district or not crop:
                continue

            year_value = pd.to_numeric(
                pd.Series([row.get("year")]), errors="coerce"
            ).iloc[0]

            production_value = pd.to_numeric(
                pd.Series([row.get("production")]), errors="coerce"
            ).iloc[0]

            if pd.isna(year_value) or pd.isna(production_value):
                continue

            year = int(year_value)
            production = float(production_value)

            if year < 1900 or year > 2200 or production < 0:
                continue

            area_value = pd.to_numeric(
                pd.Series([row.get("area", None)]), errors="coerce"
            ).iloc[0]

            area = (
                None
                if pd.isna(area_value)
                else float(area_value)
            )

            yield_value = pd.to_numeric(
                pd.Series([row.get("yield", None)]), errors="coerce"
            ).iloc[0]

            yld = (
                None
                if pd.isna(yield_value)
                else float(yield_value)
            )

            if yld is None and area is not None and area > 0:
                yld = production / area

            district_id = _upsert_dimension(
                conn,
                "dim_district",
                "district_id",
                "district_name",
                district,
                {"state": state},
            )

            crop_id = _upsert_dimension(
                conn,
                "dim_crop",
                "crop_id",
                "crop_name",
                crop,
            )

            year_id = _upsert_dimension(
                conn,
                "dim_year",
                "year_id",
                "year_value",
                year,
            )

            season_id = _upsert_dimension(
                conn,
                "dim_season",
                "season_id",
                "season_name",
                season,
            )

            canonical = "|".join([
                state,
                district,
                crop,
                str(year),
                season,
                str(area),
                str(production),
                str(yld),
            ])

            fingerprint = sha256(
                canonical.encode("utf-8")
            ).hexdigest()

            existing = conn.execute(
                text("""
                    SELECT fact_id
                    FROM fact_crop_production
                    WHERE source_fingerprint = :fp
                """),
                {"fp": fingerprint},
            ).first()

            if existing is not None:
                continue

            conn.execute(
                text("""
                    INSERT INTO fact_crop_production (
                        district_id,
                        crop_id,
                        year_id,
                        season_id,
                        area,
                        production,
                        yield_value,
                        source_fingerprint
                    )
                    VALUES (
                        :d, :c, :y, :s, :a, :p, :v, :fp
                    )
                """),
                {
                    "d": district_id,
                    "c": crop_id,
                    "y": year_id,
                    "s": season_id,
                    "a": area,
                    "p": production,
                    "v": yld,
                    "fp": fingerprint,
                },
            )

            inserted += 1

    return inserted


def load_data() -> pd.DataFrame:
    """Load joined agriculture data for comparisons and dashboards."""

    engine = get_engine()

    query = text("""
        SELECT
            dd.district_name AS district,
            dd.state_name AS state,
            dc.crop_name AS crop,
            dy.year_value AS year,
            ds.season_name AS season,
            f.area AS area,
            f.production AS production,
            f.yield_value AS yield
        FROM fact_crop_production f
        JOIN dim_district dd
            ON f.district_id = dd.district_id
        JOIN dim_crop dc
            ON f.crop_id = dc.crop_id
        JOIN dim_year dy
            ON f.year_id = dy.year_id
        JOIN dim_season ds
            ON f.season_id = ds.season_id
        ORDER BY
            dy.year_value,
            dd.district_name,
            dc.crop_name
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)

    if not df.empty:
        df["year"] = df["year"].astype(int)

    return df
