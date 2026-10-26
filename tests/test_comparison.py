import pandas as pd
from modules.comparison_engine import compare_years

def test_percentage_change():
    df = pd.DataFrame([
        {"district":"A","crop":"Paddy","year":2022,"production":100,"area":10,"yield":10},
        {"district":"A","crop":"Paddy","year":2023,"production":125,"area":12,"yield":10.4},
    ])
    result = compare_years(df, ["A"], ["Paddy"], 2022, 2023, "production")
    assert result.iloc[0]["absolute_change"] == 25
    assert result.iloc[0]["percentage_change"] == 25

def test_zero_previous_value_is_undefined():
    df = pd.DataFrame([
        {"district":"A","crop":"Paddy","year":2022,"production":0,"area":1,"yield":0},
        {"district":"A","crop":"Paddy","year":2023,"production":10,"area":2,"yield":5},
    ])
    result = compare_years(df, ["A"], ["Paddy"], 2022, 2023, "production")
    assert pd.isna(result.iloc[0]["percentage_change"])
