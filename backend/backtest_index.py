"""
backtest_index.py
Validates AIRIX's computed daily index against a reference series.

By default this runs a SYNTHETIC PROXY backtest: it compares the
pipeline's computed AIRIX against the known ground-truth index used to
generate the synthetic data (true_index_daily.csv). This stands in for
the problem statement's requirement to back-test against real DGCA
monthly average-fare data, which AIRIX does not yet have access to (see
README "Data provenance"). To run a REAL backtest once a DGCA
average-fare CSV is available, pass its path with --reference; it must
have columns [collection_round, route, avg_fare] on the same round
numbering as route_indices_by_round.csv.
"""
import argparse
import json
import pandas as pd
from index_math import weighted_airix
from backtest_metrics import mean_absolute_error, root_mean_squared_error, mean_absolute_pct_error


def load_reference_airix(reference_path, weights):
    ref_df = pd.read_csv(reference_path)
    value_col = "true_index" if "true_index" in ref_df.columns else "avg_fare"
    reference_by_round = {}
    for rnd, group in ref_df.groupby("collection_round"):
        reference_by_round[rnd] = weighted_airix(
            group.set_index("route")[value_col].to_dict(), weights
        )
    return reference_by_round


def run_backtest(reference_path="true_index_daily.csv", source_label="synthetic_proxy_pending_dgca"):
    weights = pd.read_csv("route_weights.csv").set_index("route")["weight"].to_dict()
    reference_by_round = load_reference_airix(reference_path, weights)

    computed = pd.read_csv("airix_trend.csv").set_index("collection_round")["airix"]
    common_rounds = sorted(set(reference_by_round) & set(computed.index))
    if len(common_rounds) < 30:
        print(f"WARNING: only {len(common_rounds)} overlapping periods available; "
              f"expected at least 30 for the problem statement's back-test requirement.")

    computed_vals = [round(float(computed[r]), 4) for r in common_rounds]
    reference_vals = [round(float(reference_by_round[r]), 4) for r in common_rounds]

    metrics = {
        "data_source": source_label,
        "periods_compared": len(common_rounds),
        "mae": round(mean_absolute_error(computed_vals, reference_vals), 4),
        "rmse": round(root_mean_squared_error(computed_vals, reference_vals), 4),
        "mape_pct": round(mean_absolute_pct_error(computed_vals, reference_vals), 2),
    }

    series_df = pd.DataFrame({
        "collection_round": common_rounds,
        "computed_airix": computed_vals,
        "reference_airix": reference_vals,
    })
    series_df.to_csv("backtest_series.csv", index=False)
    with open("backtest_summary.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Backtest ({source_label}): {len(common_rounds)} periods compared.")
    print(f"MAE={metrics['mae']}  RMSE={metrics['rmse']}  MAPE={metrics['mape_pct']}%")
    print("Saved: backtest_series.csv, backtest_summary.json")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest AIRIX against a reference index series.")
    parser.add_argument("--reference", default="true_index_daily.csv",
                         help="CSV with [collection_round, route, true_index|avg_fare]")
    parser.add_argument("--label", default="synthetic_proxy_pending_dgca",
                         help="Label recorded in backtest_summary.json identifying the reference source")
    args = parser.parse_args()
    run_backtest(args.reference, args.label)
