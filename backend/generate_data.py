"""
generate_data.py
Creates synthetic (fake but realistic) airfare data for the AIRIX prototype.
Simulates MULTIPLE weekly collection rounds so we can track a real calendar-time
trend (the actual AIRIX index) separately from the within-flight lead-time curve.
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

ROUTES = [
    "DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "DEL-HYD",
    "BOM-HYD", "BLR-HYD", "DEL-MAA", "BOM-MAA", "CCU-BLR"
]
AIRLINES = ["IndiGo", "Air India", "Akasa"]
HORIZONS = [45, 30, 15, 7, 1]

BASE_FARE_RANGE = {route: random.randint(2800, 5500) for route in ROUTES}

# ---- Simulate 5 weekly collection rounds ----
N_ROUNDS = 5
WEEKLY_DRIFT = 0.015  # ~1.5% average market drift per week (realistic-ish)

rows = []
record_id = 1

for round_num in range(N_ROUNDS):
    # Each round observes a flight departing ~45 days after that round's "as-of" date
    round_start = datetime(2026, 8, 1) + timedelta(weeks=round_num)
    departure_date = round_start + timedelta(days=45)

    # Market-wide drift compounds slightly each round, plus a little randomness
    market_drift = (1 + WEEKLY_DRIFT) ** round_num * random.uniform(0.98, 1.02)

    for route in ROUTES:
        base_price = BASE_FARE_RANGE[route] * market_drift

        for airline in AIRLINES:
            airline_multiplier = random.uniform(0.92, 1.12)

            for horizon in HORIZONS:
                horizon_multiplier = 1 + (45 - horizon) / 45 * random.uniform(0.8, 1.3)

                base_fare = round(base_price * airline_multiplier * horizon_multiplier, -1)
                taxes = round(base_fare * 0.18, -1)
                total_fare = base_fare + taxes

                collection_time = departure_date - timedelta(days=horizon)

                rows.append({
                    "record_id": record_id,
                    "collection_round": round_num + 1,
                    "route": route,
                    "airline": airline,
                    "flight": f"{airline[:2].upper()}{random.randint(100,999)}",
                    "departure_date": departure_date.strftime("%Y-%m-%d"),
                    "collection_time": collection_time.strftime("%Y-%m-%d"),
                    "booking_horizon": f"T+{horizon}",
                    "cabin": "Economy",
                    "base_fare": base_fare,
                    "taxes": taxes,
                    "total_fare": total_fare,
                    "availability": "Available" if random.random() > 0.05 else "Sold Out",
                    "source": random.choice(["Airline Site", "OTA"]),
                    "quality_status": "Valid"
                })
                record_id += 1

df = pd.DataFrame(rows)
df.to_csv("fares_synthetic.csv", index=False)

print(f"Generated {len(df)} synthetic fare records across {N_ROUNDS} collection rounds.")
print(f"Saved to: fares_synthetic.csv")
print(df.head())