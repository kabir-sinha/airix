"""
clean_data.py
Reads the synthetic fare data (optionally merged with real scraped data),
checks it for data-quality problems, and produces a cleaned dataset plus
an audit log of what was flagged/excluded. The quality checks are pure
functions so they're independently testable — see test_clean_data.py.
"""

import os
import pandas as pd


def merge_scraped(synthetic_df, scraped_df):
    """
    Appends scraped observations onto the synthetic dataset, stamping them
    into the most recent collection round and giving them fresh record_ids
    — this is what actually connects the real scraper's output to the
    index rather than leaving fares_scraped.csv unused.
    """
    if scraped_df.empty:
        return synthetic_df
    latest_round = synthetic_df["collection_round"].max()
    next_id = synthetic_df["record_id"].max() + 1

    scraped_df = scraped_df.copy()
    scraped_df["collection_round"] = latest_round
    scraped_df["record_id"] = range(next_id, next_id + len(scraped_df))
    return pd.concat([synthetic_df, scraped_df], ignore_index=True)


def flag_missing_fares(df):
    df = df.copy()
    missing_fare = df["total_fare"].isna()
    df.loc[missing_fare, "quality_status"] = "Excluded"
    df.loc[missing_fare, "exclusion_reason"] = "Missing fare"
    return df


def flag_sold_out(df):
    df = df.copy()
    sold_out = df["availability"] == "Sold Out"
    df.loc[sold_out & (df["quality_status"] == "Valid"), "quality_status"] = "Flagged"
    df.loc[sold_out & (df["exclusion_reason"] == ""), "exclusion_reason"] = "Sold out at collection time"
    return df


def flag_duplicates(df):
    df = df.copy()
    duplicate_mask = df.duplicated(
        subset=["collection_round", "route", "airline", "flight", "booking_horizon"],
        keep="first"
    )
    df.loc[duplicate_mask, "quality_status"] = "Excluded"
    df.loc[duplicate_mask, "exclusion_reason"] = "Duplicate observation"
    return df


def flag_outliers(df):
    df = df.copy()
    route_mean = df.groupby("route")["total_fare"].transform("mean")
    route_std = df.groupby("route")["total_fare"].transform("std")

    is_outlier = (df["total_fare"] - route_mean).abs() > 2.5 * route_std
    still_valid = df["quality_status"] == "Valid"
    outlier_mask = is_outlier & still_valid & route_std.notna() & (route_std != 0)

    df.loc[outlier_mask, "quality_status"] = "Flagged"
    df.loc[outlier_mask, "exclusion_reason"] = "Outlier fare for this route"
    return df


if __name__ == "__main__":
    synthetic = pd.read_csv("fares_synthetic.csv")

     # merge_scraped() is defined and tested above, but disabled here by default:
    # scraped fares currently run 60-100% higher than synthetic ones at every
    # booking horizon (confirmed on DEL-BLR), so blending them directly distorts
    # the index rather than reflecting a real price movement. Re-enable only
    # after calibrating the two sources to a comparable scale.
    df = synthetic

    print(f"Loaded {len(df)} raw records.")

    df["quality_status"] = "Valid"
    df["exclusion_reason"] = ""

    df = flag_missing_fares(df)
    df = flag_sold_out(df)
    df = flag_duplicates(df)
    df = flag_outliers(df)

    df.to_csv("fares_cleaned.csv", index=False)

    summary = df["quality_status"].value_counts()
    print("\nData quality summary:")
    print(summary)
    print(f"\nSaved cleaned data to: fares_cleaned.csv")
