import pytest
import pandas as pd
from aggregate_frequency import aggregate_series


def test_aggregate_series_daily_returns_input_unchanged():
    idx = pd.to_datetime(["2026-07-01", "2026-07-02"])
    series = pd.Series([100.0, 101.0], index=idx)
    result = aggregate_series(series, "daily")
    assert list(result.values) == [100.0, 101.0]

def test_aggregate_series_weekly_chain_links_within_week():
    # 2026-06-29 is a Monday, 2026-07-05 is a Sunday — this 7-day span sits
    # entirely inside one pandas W-SUN (week-ending-Sunday) bucket.
    idx = pd.to_datetime(["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02",
                           "2026-07-03", "2026-07-04", "2026-07-05"])
    series = pd.Series([100.0] * 7, index=idx)
    result = aggregate_series(series, "weekly")
    assert len(result) == 1
    assert round(result.iloc[0], 1) == 100.0

def test_aggregate_series_rejects_unknown_frequency():
    series = pd.Series([100.0], index=pd.to_datetime(["2026-07-01"]))
    with pytest.raises(ValueError):
        aggregate_series(series, "yearly")
