"""
calculate_index.py
The mathematical heart of AIRIX. Now calls the TESTED functions from
index_math.py directly (jevons_index, weighted_airix, route_contributions)
instead of a separate reimplementation — so test_index_math.py's 10 passing
tests genuinely cover the code path that produces these real numbers.
"""

import pandas as pd
from index_math import jevons_index, weighted_airix, route_contributions

df = pd.read_csv("fares_cleaned.csv")
usable = df[df["quality_status"] != "Excluded"].copy()

print(f"Using {len(usable)} usable records out of {len(df)} total.\n")

ROUTES = sorted(usable["route"].unique())
ROUNDS = sorted(usable["collection_round"].unique())

# =========================================================
# PART 1: AIRIX TREND (calendar time, round over round)
# =========================================================

round1_data = usable[usable["collection_round"] == ROUNDS[0]]
base_prices = round1_data.groupby("route")["total_fare"].mean()

usable["base_price"] = usable["route"].map(base_prices)
usable["price_relative"] = usable["total_fare"] / usable["base_price"]

# Route index per round, computed via the tested jevons_index()
route_index_by_round = {}
for rnd in ROUNDS:
    round_data = usable[usable["collection_round"] == rnd]
    round_indices = {}
    for route in ROUTES:
        relatives = round_data[round_data["route"] == route]["price_relative"].tolist()
        if relatives:
            round_indices[route] = round(jevons_index(relatives), 1)
    route_index_by_round[rnd] = round_indices

route_index_df = pd.DataFrame(route_index_by_round).T
route_index_df.index.name = "collection_round"
print("Route indices by round:")
print(route_index_df)

# Load REAL DGCA passenger-volume weights
weights_df = pd.read_csv("route_weights.csv").set_index("route")["weight"]
weights = weights_df.to_dict()

print("\nReal DGCA-based route weights in use:")
print(weights_df)

# AIRIX per round, computed via the tested weighted_airix()
airix_trend_dict = {}
for rnd in ROUNDS:
    airix_trend_dict[rnd] = round(weighted_airix(route_index_by_round[rnd], weights), 1)
airix_trend = pd.Series(airix_trend_dict)
airix_trend.index.name = "collection_round"

print("\nAIRIX trend across rounds (DGCA-weighted):")
print(airix_trend)

current_round = ROUNDS[-1]
previous_round = ROUNDS[-2]
current_airix = airix_trend[current_round]
previous_airix = airix_trend[previous_round]

print(f"\nCurrent AIRIX (round {current_round}): {current_airix}")
print(f"Change vs previous round: {round(current_airix - previous_airix, 1)} points")

# =========================================================
# PART 2: ROUTE CONTRIBUTIONS, computed via the tested route_contributions()
# =========================================================
route_change = {
    route: route_index_by_round[current_round][route] - route_index_by_round[previous_round][route]
    for route in ROUTES
}
contributions = route_contributions(route_change, weights)
contributions = {k: round(v, 2) for k, v in contributions.items()}
contributions_sorted = pd.Series(contributions).sort_values(ascending=False)
contributions_sorted.index.name = "route"

print("\nRoute contributions to latest AIRIX movement (percentage points, DGCA-weighted):")
print(contributions_sorted)
print(f"Total (should match AIRIX change): {contributions_sorted.sum():.2f} pp")

# =========================================================
# PART 3: LEAD-TIME CURVE (within the latest round only)
# =========================================================
latest_data = usable[usable["collection_round"] == current_round]
leadtime = (
    latest_data.groupby(["route", "booking_horizon"])["total_fare"]
    .mean()
    .unstack()
)
horizon_order = ["T+45", "T+30", "T+15", "T+7", "T+1"]
leadtime = leadtime[horizon_order].round(0)

print("\nLead-time fare curve (latest round, average fare by horizon):")
print(leadtime)

# =========================================================
# Save everything for the API to use later
# =========================================================
route_index_df.to_csv("route_indices_by_round.csv")
airix_trend.to_csv("airix_trend.csv", header=["airix"])
contributions_sorted.to_csv("route_contributions.csv", header=["contribution_pp"])
leadtime.to_csv("leadtime_by_route.csv")

with open("airix_summary.txt", "w") as f:
    f.write(f"AIRIX: {current_airix}\n")
    f.write(f"Change vs previous round: {round(current_airix - previous_airix, 1)}\n")
    f.write(f"Routes tracked: {len(ROUTES)}\n")
    f.write(f"Observations used: {len(usable)}\n")

print("\nSaved: route_indices_by_round.csv, airix_trend.csv, route_contributions.csv, leadtime_by_route.csv")