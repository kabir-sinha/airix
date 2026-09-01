"""
clean_data.py
Reads the synthetic fare data, checks it for data-quality problems,
and produces a cleaned dataset plus an audit log of what was flagged/excluded.
"""

import pandas as pd

df = pd.read_csv("fares_synthetic.csv")

print(f"Loaded {len(df)} raw records.")

df["quality_status"] = "Valid"
df["exclusion_reason"] = ""

# ---- Check 1: Missing fares ----
missing_fare = df["total_fare"].isna()
df.loc[missing_fare, "quality_status"] = "Excluded"
df.loc[missing_fare, "exclusion_reason"] = "Missing fare"

# ---- Check 2: Sold-out flights (flagged, not excluded) ----
sold_out = df["availability"] == "Sold Out"
df.loc[sold_out & (df["quality_status"] == "Valid"), "quality_status"] = "Flagged"
df.loc[sold_out & (df["exclusion_reason"] == ""), "exclusion_reason"] = "Sold out at collection time"

# ---- Check 3: Duplicate observations ----
# Now includes collection_round, since the same route/airline/flight/horizon
# combination legitimately repeats across different rounds.
duplicate_mask = df.duplicated(
    subset=["collection_round", "route", "airline", "flight", "booking_horizon"],
    keep="first"
)
df.loc[duplicate_mask, "quality_status"] = "Excluded"
df.loc[duplicate_mask, "exclusion_reason"] = "Duplicate observation"

# ---- Check 4: Outliers (within each route, across all rounds/horizons) ----
route_mean = df.groupby("route")["total_fare"].transform("mean")
route_std = df.groupby("route")["total_fare"].transform("std")

is_outlier = (df["total_fare"] - route_mean).abs() > 2.5 * route_std
still_valid = df["quality_status"] == "Valid"
outlier_mask = is_outlier & still_valid & route_std.notna() & (route_std != 0)

df.loc[outlier_mask, "quality_status"] = "Flagged"
df.loc[outlier_mask, "exclusion_reason"] = "Outlier fare for this route"

df.to_csv("fares_cleaned.csv", index=False)

summary = df["quality_status"].value_counts()
print("\nData quality summary:")
print(summary)
print(f"\nSaved cleaned data to: fares_cleaned.csv")