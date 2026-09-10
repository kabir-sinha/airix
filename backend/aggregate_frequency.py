"""
aggregate_frequency.py
Aggregates a daily index series into weekly or monthly periods by chain-
linking the daily values (geometric mean within each period) rather than
arithmetically averaging them, so the result stays consistent with the
Jevons/geometric-mean methodology used throughout AIRIX.
"""

from index_math import chain_link_index

PANDAS_FREQ = {"daily": "D", "weekly": "W", "monthly": "ME"}


def aggregate_series(daily_series, freq):
    """
    daily_series: pandas Series indexed by pandas Timestamp, values = index numbers.
    freq: one of "daily", "weekly", "monthly".
    Returns a Series indexed by period-end date.
    """
    if freq not in PANDAS_FREQ:
        raise ValueError(f"freq must be one of {list(PANDAS_FREQ)}")
    if freq == "daily":
        return daily_series.sort_index()

    grouped = daily_series.sort_index().resample(PANDAS_FREQ[freq])
    return grouped.apply(
        lambda values: round(chain_link_index(values.tolist()), 1) if len(values) else None
    ).dropna()
