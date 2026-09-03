"""
generate_data.py
Creates synthetic (fake but realistic) daily airfare data for the AIRIX
prototype, spanning >=30 days so the pipeline can be back-tested per the
problem statement's requirement. Each route also gets a hidden "true
index" per day — the ground-truth market signal our noisy synthetic
observations are sampled around — saved separately to
true_index_daily.csv so backtest_index.py can check whether AIRIX
recovers it from noisy per-observation data.
"""

import pandas as pd
import random
from datetime import datetime, timedelta
from fare_breakdown import split_total_fare

random.seed(42)

ROUTES = [
    "DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "DEL-HYD",
    "BOM-HYD", "BLR-HYD", "DEL-MAA", "BOM-MAA", "CCU-BLR"
]
AIRLINES = ["IndiGo", "Air India", "Akasa"]
HORIZONS = [45, 30, 15, 7, 1]

BASE_FARE_RANGE = {route: random.randint(2800, 5500) for route in ROUTES}
ROUTE_DAILY_DRIFT = {route: random.uniform(-0.003, 0.006) for route in ROUTES}

N_DAYS = 35  # >30 days so backtest_index.py has enough overlap to validate
FIRST_DAY = datetime(2026, 7, 1)

rows = []
true_index_rows = []
round_dates = []
record_id = 1

for day_num in range(1, N_DAYS + 1):
    collection_round = day_num
    round_start = FIRST_DAY + timedelta(days=day_num - 1)
    departure_date = round_start + timedelta(days=45)
    round_dates.append({"collection_round": collection_round, "date": round_start.strftime("%Y-%m-%d")})

    for route in ROUTES:
        # Hidden ground-truth index for this route/day: what a real DGCA
        # average-fare series would show if we had one. Individual fare
        # observations below are noisy samples around this true signal.
        true_index = 100 * (1 + ROUTE_DAILY_DRIFT[route]) ** day_num * random.uniform(0.995, 1.005)
        true_index_rows.append({
            "collection_round": collection_round,
            "route": route,
            "true_index": round(true_index, 3),
        })
        route_price_level = BASE_FARE_RANGE[route] * (true_index / 100)

        for airline in AIRLINES:
            airline_multiplier = random.uniform(0.92, 1.12)

            for horizon in HORIZONS:
                horizon_multiplier = 1 + (45 - horizon) / 45 * random.uniform(0.8, 1.3)
                observation_noise = random.uniform(0.97, 1.03)

                total_fare = round(
                    route_price_level * airline_multiplier * horizon_multiplier * observation_noise, -1
                )
                components = split_total_fare(total_fare)

                collection_time = departure_date - timedelta(days=horizon)

                rows.append({
                    "record_id": record_id,
                    "collection_round": collection_round,
                    "route": route,
                    "airline": airline,
                    "flight": f"{airline[:2].upper()}{random.randint(100,999)}",
                    "departure_date": departure_date.strftime("%Y-%m-%d"),
                    "collection_time": collection_time.strftime("%Y-%m-%d"),
                    "booking_horizon": f"T+{horizon}",
                    "cabin": "Economy",
                    "base_fare": components["base_fare"],
                    "fuel_surcharge": components["fuel_surcharge"],
                    "udf": components["udf"],
                    "convenience_fee": components["convenience_fee"],
                    "gst": components["gst"],
                    "total_fare": total_fare,
                    "availability": "Available" if random.random() > 0.05 else "Sold Out",
                    "source": random.choice(["Airline Site", "OTA"]),
                    "quality_status": "Valid"
                })
                record_id += 1

df = pd.DataFrame(rows)
df.to_csv("fares_synthetic.csv", index=False)

true_index_df = pd.DataFrame(true_index_rows)
true_index_df.to_csv("true_index_daily.csv", index=False)

round_dates_df = pd.DataFrame(round_dates)
round_dates_df.to_csv("round_dates.csv", index=False)

print(f"Generated {len(df)} synthetic fare records across {N_DAYS} days.")
print(f"Saved to: fares_synthetic.csv, true_index_daily.csv, round_dates.csv")
print(df.head())