import pandas as pd
from clean_data import flag_missing_fares, flag_sold_out, flag_duplicates, flag_outliers, merge_scraped


def _base_df(rows):
    df = pd.DataFrame(rows)
    df["quality_status"] = "Valid"
    df["exclusion_reason"] = ""
    return df


def test_flag_missing_fares_excludes_nan_total_fare():
    df = _base_df([
        {"route": "DEL-BOM", "total_fare": 5000, "availability": "Available"},
        {"route": "DEL-BOM", "total_fare": None, "availability": "Available"},
    ])
    result = flag_missing_fares(df)
    assert result.loc[1, "quality_status"] == "Excluded"
    assert result.loc[1, "exclusion_reason"] == "Missing fare"
    assert result.loc[0, "quality_status"] == "Valid"


def test_flag_sold_out_flags_but_does_not_exclude():
    df = _base_df([
        {"route": "DEL-BOM", "total_fare": 5000, "availability": "Sold Out"},
    ])
    result = flag_sold_out(df)
    assert result.loc[0, "quality_status"] == "Flagged"
    assert result.loc[0, "exclusion_reason"] == "Sold out at collection time"


def test_flag_duplicates_excludes_repeats_within_same_round():
    df = _base_df([
        {"collection_round": 1, "route": "DEL-BOM", "airline": "IndiGo", "flight": "6E101",
         "booking_horizon": "T+1", "total_fare": 5000, "availability": "Available"},
        {"collection_round": 1, "route": "DEL-BOM", "airline": "IndiGo", "flight": "6E101",
         "booking_horizon": "T+1", "total_fare": 5100, "availability": "Available"},
    ])
    result = flag_duplicates(df)
    assert result.loc[0, "quality_status"] == "Valid"
    assert result.loc[1, "quality_status"] == "Excluded"
    assert result.loc[1, "exclusion_reason"] == "Duplicate observation"


def test_flag_outliers_flags_fares_far_from_route_mean():
    rows = [{"route": "DEL-BOM", "total_fare": 5000, "availability": "Available"} for _ in range(10)]
    rows.append({"route": "DEL-BOM", "total_fare": 50000, "availability": "Available"})
    df = _base_df(rows)
    result = flag_outliers(df)
    assert result.loc[10, "quality_status"] == "Flagged"
    assert result.loc[10, "exclusion_reason"] == "Outlier fare for this route"
    assert (result.loc[:9, "quality_status"] == "Valid").all()


def test_merge_scraped_stamps_latest_round_and_new_ids():
    synthetic = pd.DataFrame({
        "record_id": [1, 2],
        "collection_round": [1, 2],
        "route": ["DEL-BOM", "DEL-BOM"],
    })
    scraped = pd.DataFrame({
        "route": ["DEL-BOM", "DEL-BLR"],
    })
    merged = merge_scraped(synthetic, scraped)
    assert len(merged) == 4
    scraped_rows = merged[merged["record_id"] > 2]
    assert (scraped_rows["collection_round"] == 2).all()
    assert set(scraped_rows["record_id"]) == {3, 4}
