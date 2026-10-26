# District-wise Year-on-Year Agriculture Yield Comparison

A local Streamlit application for agricultural data ingestion, ETL, a star-schema warehouse, year-on-year comparisons, OLAP-style analysis, and CSV export.

**Important:** `data/sample_agriculture_data.csv` contains synthetic demonstration values, not official statistics.

## Requirements
- Python 3.10+
- SQLite (included with Python) for the default setup
- Optional: MySQL 8+ if you want to use the MySQL database

## Run locally (SQLite default)
Open a terminal in this folder:

```bash
python -m venv .venv
```

Windows:
```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Install packages and run:
```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit. In the app, choose **Upload & ETL** and load the included sample file. The app can also load the bundled sample using its button.

## Use MySQL instead
1. Create a MySQL database and a user with permission to create/read/write the project tables.
2. Copy `.env.example` to `.env`.
3. Set `DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE`.
4. Load environment variables before launching Streamlit. One simple option is to add these lines near the top of `app.py` before `init_db()`:

```python
from dotenv import load_dotenv
load_dotenv()
```

Use URL-encoded credentials if the password contains special characters. Never commit `.env`.

## Data format
Required fields: `district`, `crop`, `year`, `production`.

Optional fields: `state`, `season`, `area`, `yield`.

The importer recognizes common variants such as `District_Name`, `Crop`, `Year`, and `Production`. If your government dataset has different headings, update the alias map in `modules/etl_pipeline.py`.

Check units before comparing production across datasets. Yield is only meaningful when production and area units are compatible. The sample yield values are demonstration data.

Suggested official data sources:
- https://www.data.gov.in/catalog/district-wise-season-wise-crop-production-statistics-0
- https://data.desagri.gov.in/website/crops-apy-report-web

Availability, coverage, and column names should be verified for the specific downloaded file.

## Tests
```bash
pytest -q
```

## Database
The app defaults to `sqlite:///agriculture.db` and creates a star schema:
- `dim_district`
- `dim_crop`
- `dim_year`
- `dim_season`
- `fact_crop_production`

To use a different database, set `DATABASE_URL`.

## Project modules
- `modules/etl_pipeline.py`: column mapping, cleaning, validation
- `modules/database.py`: schema, dimension records, fact imports, data retrieval
- `modules/comparison_engine.py`: year-on-year calculations
- `modules/olap_engine.py`: grouped analytical queries
- `modules/report_export.py`: CSV export
- `app.py`: Streamlit interface

## Limitations and next improvements
- Dataset column aliases may need adjustment to match a particular government download.
- The current dashboard provides OLAP-style operations via SQL/Pandas aggregation rather than a dedicated OLAP server.
- Yield aggregation uses an average of recorded yield values; for rigorous analysis, calculate weighted yield as total production divided by total cultivated area when units and data grain permit.
- Add audit history, PDF reports, and more detailed source-unit metadata if required by your college.
