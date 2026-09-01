"""
load_to_database.py
Takes the CSV output from calculate_index.py and saves it into the SQLite
database as a new dated snapshot — this is what lets AIRIX accumulate real
history over time instead of overwriting data on every run.
"""

import pandas as pd
from datetime import datetime
from database import SessionLocal, PipelineRun, RouteIndexSnapshot, RouteContribution, FareObservation, init_db

init_db()  # ensure tables exist
session = SessionLocal()

# ---- Load the CSVs produced by calculate_index.py ----
airix_trend = pd.read_csv("airix_trend.csv")
route_indices = pd.read_csv("route_indices_by_round.csv")
contributions = pd.read_csv("route_contributions.csv")
cleaned = pd.read_csv("fares_cleaned.csv")

current_airix = float(airix_trend["airix"].iloc[-1])
n_routes = route_indices.shape[1] - 1
n_observations = len(cleaned)
valid_count = (cleaned["quality_status"] == "Valid").sum()
data_quality_pct = round((valid_count / n_observations) * 100, 1)

# ---- Create the pipeline run record ----
run = PipelineRun(
    run_at=datetime.utcnow(),
    current_airix=current_airix,
    routes_tracked=n_routes,
    observations=n_observations,
    data_quality_pct=data_quality_pct,
)
session.add(run)
session.commit()  # commit now so run.id is generated
print(f"Created pipeline run #{run.id} — AIRIX: {current_airix}")

# ---- Save route index snapshots (every route, every round) ----
route_cols = [c for c in route_indices.columns if c != "collection_round"]
for _, row in route_indices.iterrows():
    for route in route_cols:
        session.add(RouteIndexSnapshot(
            run_id=run.id,
            route=route,
            collection_round=int(row["collection_round"]),
            index_value=float(row[route]),
        ))

# ---- Save route contributions ----
for _, row in contributions.iterrows():
    session.add(RouteContribution(
        run_id=run.id,
        route=row["route"],
        contribution_pp=float(row["contribution_pp"]),
    ))

# ---- Save individual fare observations ----
for _, row in cleaned.iterrows():
    session.add(FareObservation(
        run_id=run.id,
        route=row["route"],
        airline=row["airline"],
        flight=row["flight"],
        departure_date=row["departure_date"],
        collection_time=row["collection_time"],
        booking_horizon=row["booking_horizon"],
        base_fare=float(row["base_fare"]),
        taxes=float(row["taxes"]),
        total_fare=float(row["total_fare"]),
        availability=row["availability"],
        source=row["source"],
        quality_status=row["quality_status"],
        exclusion_reason=row.get("exclusion_reason", ""),
    ))

run_id = run.id  # capture this before closing the session

session.commit()
session.close()

print(f"Saved {len(route_indices) * len(route_cols)} route index snapshots")
print(f"Saved {len(contributions)} route contributions")
print(f"Saved {len(cleaned)} fare observations")
print(f"\nAll data loaded into airix.db under pipeline run #{run_id}")