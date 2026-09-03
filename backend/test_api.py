# backend/test_api.py
import pytest
from fastapi.testclient import TestClient
from database import Base, engine, SessionLocal, PipelineRun, RouteIndexSnapshot, RouteContribution, FareObservation
import main

client = TestClient(main.app)


@pytest.fixture(scope="module", autouse=True)
def seed_database():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    run = PipelineRun(current_airix=102.5, routes_tracked=2, observations=5, data_quality_pct=95.0)
    session.add(run)
    session.commit()

    session.add_all([
        RouteIndexSnapshot(run_id=run.id, route="DEL-BOM", collection_round=1, collection_date="2026-07-01", index_value=100.0),
        RouteIndexSnapshot(run_id=run.id, route="DEL-BOM", collection_round=2, collection_date="2026-07-02", index_value=102.0),
        RouteIndexSnapshot(run_id=run.id, route="DEL-BLR", collection_round=1, collection_date="2026-07-01", index_value=100.0),
        RouteIndexSnapshot(run_id=run.id, route="DEL-BLR", collection_round=2, collection_date="2026-07-02", index_value=98.0),
    ])
    session.add_all([
        RouteContribution(run_id=run.id, route="DEL-BOM", contribution_pp=1.2),
        RouteContribution(run_id=run.id, route="DEL-BLR", contribution_pp=-0.4),
    ])
    for horizon, fare in [("T+45", 4000), ("T+30", 4200), ("T+15", 4500), ("T+7", 4800), ("T+1", 5200)]:
        session.add(FareObservation(
            run_id=run.id, route="DEL-BOM", airline="IndiGo", flight="6E101",
            departure_date="2026-08-15", collection_time="2026-07-01", booking_horizon=horizon,
            base_fare=fare * 0.76, fuel_surcharge=fare * 0.06, udf=fare * 0.03,
            convenience_fee=fare * 0.05, gst=fare * 0.10, total_fare=fare,
            availability="Available", source="Airline Site", quality_status="Valid", exclusion_reason="",
        ))
    session.commit()
    session.close()
    yield
    Base.metadata.drop_all(engine)


def test_summary_endpoint():
    res = client.get("/api/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["current_airix"] == 102.5
    assert body["routes_tracked"] == 2


def test_routes_endpoint_returns_latest_round_only():
    res = client.get("/api/routes")
    assert res.status_code == 200
    routes = {r["route"]: r["current_index"] for r in res.json()}
    assert routes == {"DEL-BOM": 102.0, "DEL-BLR": 98.0}


def test_route_detail_not_found():
    res = client.get("/api/routes/UNKNOWN-ROUTE")
    assert res.status_code == 404


def test_route_detail_success_includes_elasticity_and_breakdown():
    res = client.get("/api/routes/DEL-BOM")
    assert res.status_code == 200
    body = res.json()
    assert body["route"] == "DEL-BOM"
    assert body["current_average_fare"] == 5200
    assert "elasticity_pct_per_day" in body
    assert set(body["fare_breakdown"].keys()) == {"base_fare", "fuel_surcharge", "udf", "convenience_fee", "gst"}


def test_contributions_endpoint_sorted_desc():
    res = client.get("/api/contributions")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["route"] == "DEL-BOM"


def test_index_history_rejects_bad_freq():
    res = client.get("/api/index/history?freq=bogus")
    assert res.status_code == 400


def test_backtest_missing_returns_404(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    res = client.get("/api/backtest")
    assert res.status_code == 404
