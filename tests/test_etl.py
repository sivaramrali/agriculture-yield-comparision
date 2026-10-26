import pandas as pd
from modules.etl_pipeline import validate_and_clean

def test_clean_valid_rows():
    raw = pd.DataFrame({"District":["krishna"],"Crop":["paddy"],"Year":[2023],"Production":[100]})
    clean, report = validate_and_clean(raw)
    assert len(clean) == 1
    assert clean.iloc[0]["district"] == "Krishna"
    assert report["status"] == "success"

def test_missing_required_column():
    clean, report = validate_and_clean(pd.DataFrame({"District":["A"]}))
    assert clean.empty
    assert "production" in report["missing_required_columns"]
