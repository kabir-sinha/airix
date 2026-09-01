"""
calculate_dgca_weights.py
Reads real DGCA city-pair passenger traffic data and computes real,
passenger-volume-based weights for our 10 AIRIX routes — replacing the
"illustrative" equal weights with actual government data.
"""

import pandas as pd

# Map our route codes to the city names DGCA uses (data spans years, and
# DGCA/older records sometimes use older city names, so we check both).
CITY_NAMES = {
    "DEL": ["DELHI"],
    "BOM": ["MUMBAI", "BOMBAY", "MUMBAI (MUMBAI)", "MUMBAI (NAVI MUMBAI)"],
    "BLR": ["BENGALURU", "BANGALORE"],
    "CCU": ["KOLKATA", "CALCUTTA"],
    "HYD": ["HYDERABAD"],
    "MAA": ["CHENNAI", "MADRAS"],
}

ROUTES = [
    ("DEL", "BOM"), ("DEL", "BLR"), ("BOM", "BLR"), ("DEL", "CCU"), ("DEL", "HYD"),
    ("BOM", "HYD"), ("BLR", "HYD"), ("DEL", "MAA"), ("BOM", "MAA"), ("CCU", "BLR"),
]

df = pd.read_csv("dgca_data/city_traffic.csv")
print(f"Loaded {len(df)} DGCA city-pair records.")

# Use the most recent full year available, so weights reflect current travel patterns
latest_year = df["Year"].max()
recent = df[df["Year"] == latest_year].copy()
print(f"Using {len(recent)} records from {latest_year} (most recent year available).")

recent["total_pax"] = recent["PaxToCity2"].fillna(0) + recent["PaxFromCity2"].fillna(0)


def get_route_traffic(code_a, code_b):
    names_a = CITY_NAMES[code_a]
    names_b = CITY_NAMES[code_b]
    # DGCA records a pair in one direction (City1, City2) — check both orderings
    mask = (
        (recent["City1"].isin(names_a) & recent["City2"].isin(names_b)) |
        (recent["City1"].isin(names_b) & recent["City2"].isin(names_a))
    )
    matched = recent[mask]
    return matched["total_pax"].sum()


route_traffic = {}
for a, b in ROUTES:
    traffic = get_route_traffic(a, b)
    route_traffic[f"{a}-{b}"] = traffic
    print(f"  {a}-{b}: {traffic:,.0f} passengers ({latest_year})")

total_traffic = sum(route_traffic.values())

if total_traffic == 0:
    print("\nWARNING: No matching traffic found for any route — check city names in the data.")
else:
    weights = {route: round(pax / total_traffic, 4) for route, pax in route_traffic.items()}
    print(f"\nReal DGCA-based route weights (sum to 1.0):")
    for route, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {route}: {w}")

    weights_df = pd.DataFrame(
        [{"route": r, "passengers": route_traffic[r], "weight": w} for r, w in weights.items()]
    )
    weights_df.to_csv("route_weights.csv", index=False)
    print(f"\nSaved to: route_weights.csv")