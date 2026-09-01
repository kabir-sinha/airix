"""
main.py
The FastAPI backend for AIRIX. Reads from the SQLite database (airix.db),
always serving the latest pipeline run's data.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
import pandas as pd
from index_math import weighted_airix
from database import SessionLocal, PipelineRun, RouteIndexSnapshot, RouteContribution, FareObservation

app = FastAPI(title="AIRIX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_latest_run(session):
    run = session.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="No pipeline runs found. Run load_to_database.py first.")
    return run


@app.get("/api/summary")
def get_summary():
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        previous = (
            session.query(PipelineRun)
            .filter(PipelineRun.id < latest.id)
            .order_by(PipelineRun.id.desc())
            .first()
        )
        change = round(latest.current_airix - previous.current_airix, 1) if previous else 0.0

        return {
            "current_airix": round(latest.current_airix, 1),
            "change_vs_previous": change,
            "routes_tracked": latest.routes_tracked,
            "observations": latest.observations,
            "data_quality_pct": latest.data_quality_pct,
        }
    finally:
        session.close()


@app.get("/api/index/history")
def get_index_history():
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        weights_df = pd.read_csv("route_weights.csv").set_index("route")["weight"]
        weights = weights_df.to_dict()

        rows = (
            session.query(RouteIndexSnapshot.collection_round)
            .filter(RouteIndexSnapshot.run_id == latest.id)
            .distinct()
            .all()
        )
        history = []
        rounds = sorted(set(r[0] for r in rows))
        for rnd in rounds:
            snaps = (
                session.query(RouteIndexSnapshot)
                .filter(RouteIndexSnapshot.run_id == latest.id, RouteIndexSnapshot.collection_round == rnd)
                .all()
            )
            route_indices = {s.route: s.index_value for s in snaps}
            airix = weighted_airix(route_indices, weights)
            history.append({"collection_round": rnd, "airix": round(airix, 1)})
        return history
    finally:
        session.close()


@app.get("/api/routes")
def get_routes():
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        max_round = (
            session.query(func.max(RouteIndexSnapshot.collection_round))
            .filter(RouteIndexSnapshot.run_id == latest.id)
            .scalar()
        )
        snaps = (
            session.query(RouteIndexSnapshot)
            .filter(RouteIndexSnapshot.run_id == latest.id, RouteIndexSnapshot.collection_round == max_round)
            .all()
        )
        return [{"route": s.route, "current_index": round(s.index_value, 1)} for s in snaps]
    finally:
        session.close()


@app.get("/api/routes/{route}")
def get_route_detail(route: str):
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        max_round = (
            session.query(func.max(RouteIndexSnapshot.collection_round))
            .filter(RouteIndexSnapshot.run_id == latest.id)
            .scalar()
        )
        current_snap = (
            session.query(RouteIndexSnapshot)
            .filter(
                RouteIndexSnapshot.run_id == latest.id,
                RouteIndexSnapshot.route == route,
                RouteIndexSnapshot.collection_round == max_round,
            )
            .first()
        )
        if not current_snap:
            raise HTTPException(status_code=404, detail=f"Route '{route}' not found")

        previous_snap = (
            session.query(RouteIndexSnapshot)
            .filter(
                RouteIndexSnapshot.run_id == latest.id,
                RouteIndexSnapshot.route == route,
                RouteIndexSnapshot.collection_round == max_round - 1,
            )
            .first()
        )
        own_index_change = (
            round(current_snap.index_value - previous_snap.index_value, 2) if previous_snap else None
        )

        fares = (
            session.query(FareObservation)
            .filter(FareObservation.run_id == latest.id, FareObservation.route == route)
            .all()
        )
        if not fares:
            raise HTTPException(status_code=404, detail=f"No fare data for '{route}'")

        horizons = ["T+45", "T+30", "T+15", "T+7", "T+1"]
        fare_curve = {}
        for h in horizons:
            matching = [f.total_fare for f in fares if f.booking_horizon == h]
            fare_curve[h] = round(sum(matching) / len(matching), 0) if matching else 0

        lead_time_increase_pct = (
            round(((fare_curve["T+1"] - fare_curve["T+45"]) / fare_curve["T+45"]) * 100, 1)
            if fare_curve["T+45"] else 0
        )

        all_contribs = (
            session.query(RouteContribution)
            .filter(RouteContribution.run_id == latest.id)
            .order_by(RouteContribution.contribution_pp.desc())
            .all()
        )
        rank = None
        this_contribution = 0.0
        for i, c in enumerate(all_contribs):
            if c.route == route:
                rank = i + 1
                this_contribution = round(c.contribution_pp, 2)
                break

        try:
            weights_df = pd.read_csv("route_weights.csv").set_index("route")["weight"]
            weight_pct = round(float(weights_df.get(route, 0)) * 100, 1)
        except Exception:
            weight_pct = None

        return {
            "route": route,
            "current_index": round(current_snap.index_value, 1),
            "own_index_change": own_index_change,
            "current_average_fare": fare_curve["T+1"],
            "fare_by_horizon": fare_curve,
            "lead_time_increase_pct": lead_time_increase_pct,
            "contribution_pp": this_contribution,
            "contribution_rank": rank,
            "total_routes": len(all_contribs),
            "dgca_weight_pct": weight_pct,
        }
    finally:
        session.close()


@app.get("/api/contributions")
def get_contributions():
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        contribs = (
            session.query(RouteContribution)
            .filter(RouteContribution.run_id == latest.id)
            .order_by(RouteContribution.contribution_pp.desc())
            .all()
        )
        return [{"route": c.route, "contribution_pp": round(c.contribution_pp, 2)} for c in contribs]
    finally:
        session.close()


@app.get("/api/data-quality")
def get_data_quality():
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        fares = session.query(FareObservation).filter(FareObservation.run_id == latest.id).all()

        by_status = {}
        by_reason = {}
        by_route = {}

        for f in fares:
            by_status[f.quality_status] = by_status.get(f.quality_status, 0) + 1

            if f.quality_status != "Valid" and f.exclusion_reason:
                by_reason[f.exclusion_reason] = by_reason.get(f.exclusion_reason, 0) + 1

            if f.route not in by_route:
                by_route[f.route] = {"Valid": 0, "Flagged": 0, "Excluded": 0}
            by_route[f.route][f.quality_status] = by_route[f.route].get(f.quality_status, 0) + 1

        valid_count = by_status.get("Valid", 0)
        quality_pct = round((valid_count / len(fares)) * 100, 1) if fares else 0

        return {
            "total_observations": len(fares),
            "quality_pct": quality_pct,
            "by_status": by_status,
            "by_reason": by_reason,
            "by_route": by_route,
        }
    finally:
        session.close()