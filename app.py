import streamlit as st
import pandas as pd
import plotly.express as px
from modules.database import init_db, load_data, get_engine, import_dataframe
from modules.etl_pipeline import validate_and_clean
from modules.comparison_engine import compare_years
from modules.olap_engine import aggregate_data
from modules.report_export import csv_bytes

st.set_page_config(page_title="Agriculture Yield Comparison", page_icon="🌾", layout="wide")
init_db()
st.title(" District-wise Year-on-Year Agriculture Comparison")
st.caption("Agriculture data warehouse • ETL • Star-schema analytics • OLAP")

@st.cache_data(ttl=30)
def get_data():
    return load_data()

with st.sidebar:
    st.header("Navigation")
    page = st.radio("Choose module", [
        "Overview", "Upload & ETL", "Year-on-Year Comparison",
        "Crop Analysis", "OLAP Explorer", "Data & Export", "About"
    ])
    st.divider()

df = get_data()

if page == "Overview":
    st.subheader("Agriculture analytics overview")
    if df.empty:
        st.warning("No records found yet. Open **Upload & ETL** to import a CSV or Excel dataset.")
        st.info("You can load the included synthetic sample file: data/sample_agriculture_data.csv")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Records", f"{len(df):,}")
        c2.metric("Districts", df["district"].nunique())
        c3.metric("Crops", df["crop"].nunique())
        c4.metric("Years", df["year"].nunique())
        st.subheader("Production by year")
        yearly = df.groupby("year", as_index=False)["production"].sum()
        st.plotly_chart(px.line(yearly, x="year", y="production", markers=True,
                                title="Total recorded production by year"), use_container_width=True)
        st.subheader("Production by district")
        dist = df.groupby("district", as_index=False)["production"].sum().sort_values("production", ascending=False)
        st.plotly_chart(px.bar(dist, x="district", y="production", title="Recorded production by district"),
                        use_container_width=True)
        st.caption("Aggregations reflect the imported records and their source units. Do not combine incompatible units.")
elif page == "Upload & ETL":
    st.subheader("Upload agricultural data")
    st.write("Upload CSV or Excel. Required columns: district, crop, year, production. Optional: state, season, area, yield.")
    uploaded = st.file_uploader("Choose CSV or Excel file", type=["csv","xlsx","xls"])
    if uploaded:
        try:
            raw = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
            st.write("Preview", raw.head(10))
            st.write("Columns detected:", list(raw.columns))
            cleaned, report = validate_and_clean(raw)
            st.write("Validation report")
            st.json(report)
            if not cleaned.empty:
                st.write("Cleaned preview", cleaned.head(10))
                if st.button("Import validated records", type="primary"):
                    count = import_dataframe(cleaned)
                    st.cache_data.clear()
                    st.success(f"Imported {count} records (duplicates may be skipped).")
                    st.rerun()
            else:
                st.error("No valid rows to import. Review required columns and validation errors.")
        except Exception as e:
            st.error(f"Could not read or validate the file: {e}")
    st.divider()
    st.subheader("Load bundled synthetic sample")
    st.warning("These are invented demonstration values, not official statistics.")
    if st.button("Load sample dataset"):
        sample = pd.read_csv("data/sample_agriculture_data.csv")
        cleaned, report = validate_and_clean(sample)
        count = import_dataframe(cleaned)
        st.cache_data.clear()
        st.success(f"Loaded {count} sample records.")
        st.rerun()
elif page == "Year-on-Year Comparison":
    st.subheader("Compare two years")
    if df.empty:
        st.info("Import data first.")
    else:
        a,b,c,d = st.columns(4)
        districts = sorted(df["district"].dropna().unique().tolist())
        crops = sorted(df["crop"].dropna().unique().tolist())
        years = sorted(df["year"].dropna().astype(int).unique().tolist())
        selected_districts = a.multiselect("Districts", districts, default=districts[:min(3,len(districts))])
        selected_crops = b.multiselect("Crops", crops, default=crops[:min(3,len(crops))])
        metric = c.selectbox("Metric", ["production","area","yield"])
        if len(years) >= 2:
            prev_year = d.selectbox("Previous year", years[:-1], index=max(0,len(years[:-1])-1))
            curr_year = st.selectbox("Current year", [y for y in years if y > prev_year], index=0)
            result = compare_years(df, selected_districts, selected_crops, int(prev_year), int(curr_year), metric)
            if result.empty:
                st.warning("No matching records for this selection.")
            else:
                st.dataframe(result, use_container_width=True, hide_index=True)
                chart = result.dropna(subset=["previous_value","current_value"])
                if not chart.empty:
                    long = chart.melt(id_vars=["district","crop"], value_vars=["previous_value","current_value"],
                                      var_name="period", value_name="value")
                    long["period"] = long["period"].map({"previous_value":str(prev_year),"current_value":str(curr_year)})
                    st.plotly_chart(px.bar(long, x="district", y="value", color="period", barmode="group",
                                            facet_col="crop", title=f"{metric.title()} comparison"),
                                    use_container_width=True)
        else:
            st.info("At least two distinct years are needed for year-on-year comparison.")
elif page == "Crop Analysis":
    st.subheader("Crop analysis")
    if df.empty:
        st.info("Import data first.")
    else:
        crops = sorted(df["crop"].dropna().unique().tolist())
        crop = st.selectbox("Select crop", crops)
        subset = df[df["crop"] == crop]
        yearly = subset.groupby("year", as_index=False)[["production","area"]].sum()
        st.plotly_chart(px.line(yearly, x="year", y="production", markers=True, title=f"{crop}: production trend"),
                        use_container_width=True)
        dist = subset.groupby("district", as_index=False)["production"].sum().sort_values("production", ascending=False)
        st.plotly_chart(px.bar(dist, x="district", y="production", title=f"{crop}: total production by district"),
                        use_container_width=True)
        st.dataframe(subset, use_container_width=True, hide_index=True)
elif page == "OLAP Explorer":
    st.subheader("Multidimensional / OLAP Explorer")
    if df.empty:
        st.info("Import data first.")
    else:
        dim = st.selectbox("Group by", ["state","district","crop","year","season"])
        metric = st.selectbox("Aggregate metric", ["production","area","yield"])
        operation = st.selectbox("Operation", ["Roll-up / group summary","Slice / filter one value","Pivot table"])
        filtered = df.copy()
        if operation == "Slice / filter one value":
            vals = sorted(filtered[dim].dropna().astype(str).unique().tolist())
            selected = st.selectbox(f"Select {dim}", vals)
            filtered = filtered[filtered[dim].astype(str) == selected]
        result = aggregate_data(filtered, dim, metric)
        if operation == "Pivot table":
            if dim in ["year","district","crop","season","state"]:
                pivot = pd.pivot_table(filtered, index="district", columns=dim, values=metric, aggfunc="sum", fill_value=0)
                st.dataframe(pivot, use_container_width=True)
            else:
                st.dataframe(result, use_container_width=True)
        else:
            st.dataframe(result, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(result, x=dim, y=metric, title=f"{metric.title()} by {dim}"),
                            use_container_width=True)
        st.caption("Drill-down is supported by selecting a more detailed grouping dimension; roll-up uses grouped aggregation.")
elif page == "Data & Export":
    st.subheader("Imported data and export")
    if df.empty:
        st.info("No data available.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download current dataset as CSV", data=csv_bytes(df),
                           file_name="agriculture_records.csv", mime="text/csv")
        st.write("Dataset summary")
        st.dataframe(df.describe(include="all").transpose(), use_container_width=True)
elif page == "About":
    st.subheader("About this project")
    st.markdown("""
    **Objective:** help users compare district-wise agricultural production and yield across years.

    **Modules:** data collection, cleaning/ETL, star-schema warehouse, year-on-year comparison,
    OLAP analysis, and dashboard/reporting.

    **Technology:** Python, Pandas, SQLAlchemy, SQLite by default (or MySQL through `DATABASE_URL`),
    Streamlit, Plotly, pytest.

    **Important:** production and yield are different. Yield is calculated only when the area and
    production units are compatible. The bundled sample is synthetic and must not be presented as
    official agricultural statistics.
    """)
