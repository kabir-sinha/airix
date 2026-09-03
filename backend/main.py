"""
main.py
The FastAPI backend for AIRIX. Reads from the SQLite database (airix.db),
always serving the latest pipeline run's data.
"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
import pandas as pd
from index_math import weighted_airix
from aggregate_frequency import aggregate_series
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
def get_index_history(freq: str = "daily"):
    if freq not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="freq must be daily, weekly, or monthly")
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        weights_df = pd.read_csv("route_weights.csv").set_index("route")["weight"]
        weights = weights_df.to_dict()

        snaps = (
            session.query(RouteIndexSnapshot)
            .filter(RouteIndexSnapshot.run_id == latest.id)
            .all()
        )
        by_round = {}
        dates_by_round = {}
        for s in snaps:
            by_round.setdefault(s.collection_round, {})[s.route] = s.index_value
            dates_by_round[s.collection_round] = s.collection_date

        daily_values = {}
        for rnd, route_indices in by_round.items():
            date = dates_by_round.get(rnd)
            if not date:
                continue
            daily_values[pd.Timestamp(date)] = round(weighted_airix(route_indices, weights), 1)

        daily_series = pd.Series(daily_values).sort_index()
        aggregated = aggregate_series(daily_series, freq)
        return [
            {"date": ts.strftime("%Y-%m-%d"), "airix": float(value)}
            for ts, value in aggregated.items()
        ]
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


@app.get("/api/backtest")
def get_backtest():
    try:
        with open("backtest_summary.json") as f:
            summary = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No backtest results found. Run backtest_index.py first.")
    series_df = pd.read_csv("backtest_series.csv")
    return {
        "summary": summary,
        "series": series_df.to_dict(orient="records"),
    }


@app.get("/api/heatmap")
def get_heatmap(freq: str = "weekly"):
    if freq not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="freq must be daily, weekly, or monthly")
    session = SessionLocal()
    try:
        latest = get_latest_run(session)
        snaps = (
            session.query(RouteIndexSnapshot)
            .filter(RouteIndexSnapshot.run_id == latest.id)
            .all()
        )
        df = pd.DataFrame([
            {"route": s.route, "date": s.collection_date, "index_value": s.index_value}
            for s in snaps if s.collection_date
        ])
        if df.empty:
            return {"routes": [], "periods": [], "matrix": []}
        df["date"] = pd.to_datetime(df["date"])

        route_series = {}
        periods = set()
        for route, group in df.groupby("route"):
            series = group.set_index("date")["index_value"].sort_index()
            aggregated = aggregate_series(series, freq)
            route_series[route] = aggregated
            periods.update(aggregated.index)

        sorted_periods = sorted(periods)
        routes = sorted(route_series.keys())
        matrix = [
            [
                round(float(route_series[route][period]), 1) if period in route_series[route].index else None
                for period in sorted_periods
            ]
            for route in routes
        ]
        return {
            "routes": routes,
            "periods": [p.strftime("%Y-%m-%d") for p in sorted_periods],
            "matrix": matrix,
        }
    finally:
        session.close()