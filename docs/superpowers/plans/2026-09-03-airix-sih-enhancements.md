# AIRIX SIH26056 Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap between the current AIRIX prototype and the SIH26056 problem statement's explicit "Expected Solution" checklist — 30-day back-test, daily/weekly/monthly index, sector heatmap, fare decomposition, elasticity, scheduled extraction, anti-bot-technique demonstration, and expanded test coverage — without breaking the existing, already-passing 10-test math suite.

**Architecture:** Daily-granularity data flows through the existing five-stage pipeline (`generate_data.py` → `clean_data.py` → `calculate_dgca_weights.py` → `calculate_index.py` → `load_to_database.py`), now producing 35 days instead of 5 weekly rounds. Two new pure modules (`fare_breakdown.py`, `backtest_metrics.py`) and one extension to `index_math.py` (`chain_link_index`) carry the new math, each unit-tested in isolation the same way `index_math.py` already is. A new `aggregate_frequency.py` rolls the daily index up to weekly/monthly via chain-linking. The FastAPI layer and Next.js dashboard are extended, not restructured.

**Tech Stack:** Python 3.13, pandas, scipy, SQLAlchemy, FastAPI, pytest, APScheduler (new), Playwright; Next.js/React/Tailwind/Recharts.

**Spec:** [docs/superpowers/specs/2026-09-03-airix-sih-enhancements.md](../specs/2026-09-03-airix-sih-enhancements.md)

## Global Constraints

- All new backend scripts run from the `backend/` working directory, matching every existing script's use of relative CSV paths (`pd.read_csv("fares_cleaned.csv")`, etc.) — do not introduce absolute paths.
- Every new pure-math function goes in a small, dedicated module with its own test file, mirroring the existing `index_math.py` / `test_index_math.py` split — never inline untested statistical logic into a pipeline script.
- The synthetic backtest must be labeled `"synthetic_proxy_pending_dgca"` everywhere it surfaces (JSON responses, UI) — never presented as if it were real DGCA fare validation.
- `backend/airix.db` is gitignored and safe to delete/regenerate; the schema changes in this plan require deleting it once (see Task 3) — do not attempt an in-place ALTER TABLE migration.
- Existing tests (`test_index_math.py`, 10 tests) must keep passing unmodified throughout.

---

## File Structure

```
backend/
  fare_breakdown.py          NEW — pure fare-component split, shared by generator + scraper
  test_fare_breakdown.py     NEW
  generate_data.py           MODIFIED — daily granularity, true_index_daily.csv, round_dates.csv
  database.py                MODIFIED — collection_date column, fare-breakdown columns
  load_to_database.py        MODIFIED — reads round_dates.csv, writes new columns
  index_math.py              MODIFIED — + chain_link_index, + lead_time_elasticity
  test_index_math.py         MODIFIED — + tests for the two new functions
  aggregate_frequency.py     NEW — daily -> weekly/monthly chain-linking
  test_aggregate_frequency.py NEW
  clean_data.py              MODIFIED — refactored into pure functions, merges fares_scraped.csv
  test_clean_data.py         NEW
  backtest_metrics.py        NEW — pure error-metric functions
  test_backtest_metrics.py   NEW
  backtest_index.py          NEW — orchestrates the proxy backtest
  scheduler.py                NEW — daily pipeline scheduling
  test_scheduler.py           NEW
  conftest.py                 NEW — test-DB isolation for API tests
  test_api.py                  NEW
  main.py                     MODIFIED — frequency param, /api/backtest, /api/heatmap, elasticity + fare breakdown
  requirements.txt            MODIFIED — + apscheduler, + httpx (TestClient dep)
scraper/
  scrape_real_data.py         MODIFIED — UA rotation, session isolation, randomized delay, fare_breakdown
frontend/src/app/
  page.js                     MODIFIED — frequency toggle on trend chart, heatmap section
  routes/[route]/page.js      MODIFIED — elasticity stat, fare breakdown section
  validation/page.js          NEW — backtest results page
docs/
  PS_MAPPING.md                NEW — problem-statement-to-feature traceability
README.md                     MODIFIED — new scripts/pages documented
```

---

### Task 1: Fare breakdown helper

**Files:**
- Create: `backend/fare_breakdown.py`
- Test: `backend/test_fare_breakdown.py`

**Interfaces:**
- Produces: `split_total_fare(total_fare: float) -> dict[str, float]` with keys `base_fare, fuel_surcharge, udf, convenience_fee, gst`, values summing exactly to `total_fare`. Consumed by Task 2 (generator) and Task 7 (scraper).

- [ ] **Step 1: Write the failing tests**

```python
# backend/test_fare_breakdown.py
import pytest
from fare_breakdown import split_total_fare, FARE_COMPONENT_SHARES


def test_split_total_fare_sums_to_total():
    total = 5000
    components = split_total_fare(total)
    assert sum(components.values()) == total


def test_split_total_fare_has_all_components():
    components = split_total_fare(4321)
    assert set(components.keys()) == set(FARE_COMPONENT_SHARES.keys())


def test_split_total_fare_rejects_non_positive():
    with pytest.raises(ValueError):
        split_total_fare(0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest test_fare_breakdown.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fare_breakdown'`

- [ ] **Step 3: Write the implementation**

```python
# backend/fare_breakdown.py
"""
fare_breakdown.py
Pure function splitting a total fare into its components, matching how a
real Indian airline ticket price is composed: base fare + fuel surcharge +
user development fee (UDF) + convenience fee (OTA booking fee) + GST.
Shared by generate_data.py and scrape_real_data.py so both sources of
fare data produce the same shape, whether the total was built up from a
market model or observed whole from a page.
"""

FARE_COMPONENT_SHARES = {
    "base_fare": 0.76,
    "fuel_surcharge": 0.06,
    "udf": 0.03,
    "convenience_fee": 0.05,
    "gst": 0.10,
}


def split_total_fare(total_fare):
    """Splits a total fare into components that sum back to total_fare exactly."""
    if total_fare <= 0:
        raise ValueError("total_fare must be positive")
    components = {
        name: round(total_fare * share)
        for name, share in FARE_COMPONENT_SHARES.items()
    }
    # Rounding each component independently can drift the sum by a rupee or
    # two — correct it on base_fare so components always sum exactly.
    drift = total_fare - sum(components.values())
    components["base_fare"] += drift
    return components
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest test_fare_breakdown.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/fare_breakdown.py backend/test_fare_breakdown.py
git commit -m "feat: add shared fare-component breakdown helper"
```

---

### Task 2: Daily synthetic data generator

**Files:**
- Modify: `backend/generate_data.py` (full rewrite — file is 76 lines, entirely replaced)

**Interfaces:**
- Consumes: `split_total_fare` from Task 1.
- Produces: `backend/fares_synthetic.csv` (existing schema, now with `fuel_surcharge`, `udf`, `convenience_fee`, `gst` replacing the old flat computation, spanning `collection_round` 1..35 instead of 1..5), `backend/true_index_daily.csv` (columns `collection_round, route, true_index`) consumed by Task 9's backtest, `backend/round_dates.csv` (columns `collection_round, date`) consumed by Task 3's loader.

- [ ] **Step 1: Replace the generator**

```python
# backend/generate_data.py
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
```

- [ ] **Step 2: Run it and verify output shape**

Run: `cd backend && python3 generate_data.py`
Expected: prints "Generated 5250 synthetic fare records across 35 days." (10 routes × 3 airlines × 5 horizons × 35 days), and `fares_synthetic.csv`, `true_index_daily.csv`, `round_dates.csv` exist with 5250, 350, and 35 rows respectively (excluding headers).

Verify: `python3 -c "import pandas as pd; print(len(pd.read_csv('fares_synthetic.csv')), len(pd.read_csv('true_index_daily.csv')), len(pd.read_csv('round_dates.csv')))"`
Expected output: `5250 350 35`

- [ ] **Step 3: Commit**

```bash
git add backend/generate_data.py
git commit -m "feat: generate 35 days of daily synthetic fare data with ground-truth index"
```

---

### Task 3: Database schema + loader for daily dates and fare breakdown

**Files:**
- Modify: `backend/database.py:30-69`
- Modify: `backend/load_to_database.py`

**Interfaces:**
- Consumes: `round_dates.csv` from Task 2, the new `fuel_surcharge/udf/convenience_fee/gst` columns from Task 2's `fares_synthetic.csv` (via `fares_cleaned.csv`).
- Produces: `RouteIndexSnapshot.collection_date` (String), `FareObservation.fuel_surcharge/udf/convenience_fee/gst` (Float) — consumed by Task 6 (history dates), Task 11 (heatmap), Task 12 (fare breakdown API).

- [ ] **Step 1: Update the schema**

Replace `backend/database.py:30-38` (the `RouteIndexSnapshot` class):

```python
class RouteIndexSnapshot(Base):
    """Route-level index value for a specific route, in a specific run."""
    __tablename__ = "route_index_snapshots"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer)
    route = Column(String, index=True)
    collection_round = Column(Integer)
    collection_date = Column(String)
    index_value = Column(Float)
```

Replace `backend/database.py:51-69` (the `FareObservation` class):

```python
class FareObservation(Base):
    """Individual cleaned fare records, in a specific run."""
    __tablename__ = "fare_observations"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer)
    route = Column(String, index=True)
    airline = Column(String)
    flight = Column(String)
    departure_date = Column(String)
    collection_time = Column(String)
    booking_horizon = Column(String)
    base_fare = Column(Float)
    fuel_surcharge = Column(Float)
    udf = Column(Float)
    convenience_fee = Column(Float)
    gst = Column(Float)
    total_fare = Column(Float)
    availability = Column(String)
    source = Column(String)
    quality_status = Column(String)
    exclusion_reason = Column(String)
```

- [ ] **Step 2: Update the loader**

Replace `backend/load_to_database.py:1-19` (imports and CSV loads):

```python
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
round_dates = pd.read_csv("round_dates.csv").set_index("collection_round")["date"].to_dict()
```

Replace `backend/load_to_database.py:39-48` (the route index snapshot loop) with:

```python
# ---- Save route index snapshots (every route, every round) ----
route_cols = [c for c in route_indices.columns if c != "collection_round"]
for _, row in route_indices.iterrows():
    rnd = int(row["collection_round"])
    for route in route_cols:
        session.add(RouteIndexSnapshot(
            run_id=run.id,
            route=route,
            collection_round=rnd,
            collection_date=round_dates.get(rnd),
            index_value=float(row[route]),
        ))
```

Replace `backend/load_to_database.py:58-75` (the fare observation loop) with:

```python
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
        fuel_surcharge=float(row.get("fuel_surcharge", 0) or 0),
        udf=float(row.get("udf", 0) or 0),
        convenience_fee=float(row.get("convenience_fee", 0) or 0),
        gst=float(row.get("gst", 0) or 0),
        total_fare=float(row["total_fare"]),
        availability=row["availability"],
        source=row["source"],
        quality_status=row["quality_status"],
        exclusion_reason=row.get("exclusion_reason", ""),
    ))
```

(`row.get(..., 0) or 0` covers scraped rows merged in Task 8 before that task's fare_breakdown alignment is guaranteed complete — harmless once Task 7/8 land since scraped rows will always carry the new columns too.)

- [ ] **Step 3: Rebuild the database and verify**

```bash
cd backend
rm -f airix.db
python3 generate_data.py
python3 clean_data.py
python3 calculate_dgca_weights.py
python3 calculate_index.py
python3 load_to_database.py
```

Verify: `python3 -c "
from database import SessionLocal, RouteIndexSnapshot
s = SessionLocal()
snap = s.query(RouteIndexSnapshot).first()
print(snap.collection_date, snap.collection_round, snap.route, snap.index_value)
"`
Expected: prints a row with a real date string like `2026-07-01 1 ...` (not `None`).

- [ ] **Step 4: Commit**

```bash
git add backend/database.py backend/load_to_database.py
git commit -m "feat: store calendar dates and fare-component breakdown in the database"
```

---

### Task 4: `chain_link_index` for period aggregation

**Files:**
- Modify: `backend/index_math.py` (append function)
- Modify: `backend/test_index_math.py` (append tests)

**Interfaces:**
- Produces: `chain_link_index(index_values: list[float]) -> float` — geometric mean of a list of already-computed index values (each on a base of 100). Consumed by Task 5 (`aggregate_frequency.py`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_index_math.py`:

```python
# ---- chain_link_index ----

from index_math import chain_link_index


def test_chain_link_index_constant_series():
    assert chain_link_index([100, 100, 100]) == pytest.approx(100.0)

def test_chain_link_index_uses_geometric_mean():
    # gmean([80, 125]) == 100 exactly; arithmetic mean would give 102.5 —
    # proves this chains geometrically, consistent with Jevons.
    assert chain_link_index([80, 125]) == pytest.approx(100.0)

def test_chain_link_index_empty_raises():
    with pytest.raises(ValueError):
        chain_link_index([])
```

(Note: this duplicates the `from index_math import chain_link_index` alongside the existing top-of-file import — replace the file's top import line instead, from `from index_math import price_relative, jevons_index, weighted_airix, route_contributions` to also include `chain_link_index`, and drop the inline import added above.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest test_index_math.py -v -k chain_link`
Expected: FAIL — `ImportError: cannot import name 'chain_link_index'`

- [ ] **Step 3: Implement**

Append to `backend/index_math.py`:

```python
def chain_link_index(index_values):
    """
    Chain-links a series of already-computed index values (each already on
    a base of 100) into a single period index via their geometric mean.
    Used to roll a daily AIRIX series up into weekly/monthly periods
    without breaking the geometric-mean methodology used to build it.
    """
    if len(index_values) == 0:
        raise ValueError("index_values cannot be empty")
    return gmean(index_values)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest test_index_math.py -v`
Expected: PASS (13 tests — the original 10 plus 3 new)

- [ ] **Step 5: Commit**

```bash
git add backend/index_math.py backend/test_index_math.py
git commit -m "feat: add chain_link_index for weekly/monthly period aggregation"
```

---

### Task 5: `aggregate_frequency.py`

**Files:**
- Create: `backend/aggregate_frequency.py`
- Test: `backend/test_aggregate_frequency.py`

**Interfaces:**
- Consumes: `chain_link_index` from Task 4.
- Produces: `aggregate_series(daily_series: pd.Series, freq: str) -> pd.Series` where `freq` is `"daily" | "weekly" | "monthly"`, input/output indexed by `pandas.Timestamp`. Consumed by Task 6 (`/api/index/history`) and Task 11 (`/api/heatmap`).

- [ ] **Step 1: Write the failing tests**

```python
# backend/test_aggregate_frequency.py
import pytest
import pandas as pd
from aggregate_frequency import aggregate_series


def test_aggregate_series_daily_returns_input_unchanged():
    idx = pd.to_datetime(["2026-07-01", "2026-07-02"])
    series = pd.Series([100.0, 101.0], index=idx)
    result = aggregate_series(series, "daily")
    assert list(result.values) == [100.0, 101.0]

def test_aggregate_series_weekly_chain_links_within_week():
    idx = pd.to_datetime([f"2026-07-{d:02d}" for d in range(1, 8)])
    series = pd.Series([100.0] * 7, index=idx)
    result = aggregate_series(series, "weekly")
    assert len(result) == 1
    assert round(result.iloc[0], 1) == 100.0

def test_aggregate_series_rejects_unknown_frequency():
    series = pd.Series([100.0], index=pd.to_datetime(["2026-07-01"]))
    with pytest.raises(ValueError):
        aggregate_series(series, "yearly")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest test_aggregate_frequency.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aggregate_frequency'`

- [ ] **Step 3: Implement**

```python
# backend/aggregate_frequency.py
"""
aggregate_frequency.py
Aggregates a daily index series into weekly or monthly periods by chain-
linking the daily values (geometric mean within each period) rather than
arithmetically averaging them, so the result stays consistent with the
Jevons/geometric-mean methodology used throughout AIRIX.
"""

from index_math import chain_link_index

PANDAS_FREQ = {"daily": "D", "weekly": "W", "monthly": "ME"}


def aggregate_series(daily_series, freq):
    """
    daily_series: pandas Series indexed by pandas Timestamp, values = index numbers.
    freq: one of "daily", "weekly", "monthly".
    Returns a Series indexed by period-end date.
    """
    if freq not in PANDAS_FREQ:
        raise ValueError(f"freq must be one of {list(PANDAS_FREQ)}")
    if freq == "daily":
        return daily_series.sort_index()

    grouped = daily_series.sort_index().resample(PANDAS_FREQ[freq])
    return grouped.apply(
        lambda values: round(chain_link_index(values.tolist()), 1) if len(values) else None
    ).dropna()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest test_aggregate_frequency.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/aggregate_frequency.py backend/test_aggregate_frequency.py
git commit -m "feat: add daily-to-weekly/monthly index aggregation"
```

---

### Task 6: Frequency-aware `/api/index/history` + trend chart

**Files:**
- Modify: `backend/main.py:1-21` (imports), `backend/main.py:55-82` (`get_index_history`)
- Modify: `frontend/src/app/page.js:12-24` (state), `:36-56` (data loading), `:161-185` (trend section)

**Interfaces:**
- Consumes: `aggregate_series` from Task 5, `RouteIndexSnapshot.collection_date` from Task 3.
- Produces: `GET /api/index/history?freq=daily|weekly|monthly` returning `[{"date": "YYYY-MM-DD", "airix": float}, ...]` (replaces the old `collection_round`-keyed shape).

- [ ] **Step 1: Update main.py imports**

Replace `backend/main.py:11` (`from index_math import weighted_airix`) with:

```python
from index_math import weighted_airix
from aggregate_frequency import aggregate_series
```

- [ ] **Step 2: Rewrite the history endpoint**

Replace `backend/main.py:55-82` (`get_index_history` and its body) with:

```python
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
```

- [ ] **Step 3: Verify the API manually**

Run: `cd backend && uvicorn main:app --reload` (in one terminal), then in another:
`curl "http://127.0.0.1:8000/api/index/history?freq=weekly"`
Expected: a JSON array of `{"date": ..., "airix": ...}` objects, roughly 5 entries (35 days / 7).
`curl "http://127.0.0.1:8000/api/index/history?freq=bogus"`
Expected: `{"detail":"freq must be daily, weekly, or monthly"}` with HTTP 400.

- [ ] **Step 4: Update the frontend state and data loading**

In `frontend/src/app/page.js`, replace line 23 (`const [sortDir, setSortDir] = useState("desc");`) with:

```js
  const [sortDir, setSortDir] = useState("desc");
  const [freq, setFreq] = useState("weekly");
```

Replace `frontend/src/app/page.js:36-56` (the single data-loading `useEffect`) with:

```js
  useEffect(() => {
    async function loadData() {
      try {
        const [summaryRes, contribRes, routesRes] = await Promise.all([
          fetch(`${API_URL}/api/summary`),
          fetch(`${API_URL}/api/contributions`),
          fetch(`${API_URL}/api/routes`),
        ]);
        setSummary(await summaryRes.json());
        setContributions(await contribRes.json());
        setRoutes(await routesRes.json());
      } catch (err) {
        setError("Could not connect to the AIRIX API. Is the backend running?");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    async function loadHistory() {
      try {
        const res = await fetch(`${API_URL}/api/index/history?freq=${freq}`);
        setHistory(await res.json());
      } catch (err) {
        // Trend panel stays empty; the page-level error state already
        // covers a fully unreachable backend.
      }
    }
    loadHistory();
  }, [freq]);
```

- [ ] **Step 5: Update the trend chart**

Replace `frontend/src/app/page.js:161-185` (the "AIRIX Trend" `<section>`) with:

```jsx
        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-semibold">AIRIX Trend</h2>
            <div className="flex gap-1">
              {["daily", "weekly", "monthly"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFreq(f)}
                  className={`text-xs px-3 py-1 rounded border transition-colors ${
                    freq === f
                      ? "border-[var(--amber)] text-[var(--amber)]"
                      : "border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
                  }`}
                >
                  {f[0].toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={12} />
              <YAxis domain={["dataMin - 3", "dataMax + 3"]} stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                }}
                formatter={(value) => [value, "AIRIX"]}
              />
              <Line type="monotone" dataKey="airix" stroke="var(--amber)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </section>
```

- [ ] **Step 6: Verify in the browser**

Run: `cd frontend && npm run dev`, visit `http://localhost:3000` with the backend also running.
Expected: the trend chart renders with date labels, and clicking Daily/Weekly/Monthly changes the number of points on the chart.

- [ ] **Step 7: Commit**

```bash
git add backend/main.py frontend/src/app/page.js
git commit -m "feat: daily/weekly/monthly frequency for the AIRIX trend chart"
```

---

### Task 7: Scraper anti-bot technique demonstration

**Files:**
- Modify: `scraper/scrape_real_data.py` (full rewrite — file is 99 lines, entirely replaced)

**Interfaces:**
- Consumes: `split_total_fare` from Task 1 (via `sys.path` injection to `backend/`).
- Produces: `backend/fares_scraped.csv` with the same columns as `fares_synthetic.csv` (minus `record_id`/`collection_round`, added by Task 8's merge).

- [ ] **Step 1: Replace the scraper**

```python
# scraper/scrape_real_data.py
"""
scrape_real_data.py
A real Playwright-based scraper: fills a search form, submits it, waits for
async-loaded results, and extracts structured fare data — the same
technique needed for a real flight-search site. Targets our local
mock_site for technical validation, respecting the robots.txt constraints
we found on real airline/OTA sites (see project notes).

Also demonstrates the anti-bot-adjacent techniques a production scraper
would need against real targets: rotating User-Agent strings, randomized
inter-request delays (not a fixed interval), and a fresh browser session
(context) per route so cookies/state don't leak between unrelated
searches — the same isolation and rate-limiting discipline required by
the problem statement's "ethical scraping safeguards" clause.
"""

import time
import csv
import os
import random
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "backend"))
from fare_breakdown import split_total_fare  # noqa: E402

MOCK_SITE_URL = f"file://{os.path.join(SCRIPT_DIR, 'mock_site', 'index.html')}"
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "..", "backend", "fares_scraped.csv")

ROUTES = [("DEL", "BOM"), ("DEL", "BLR")]   # 1-2 routes, as planned
HORIZONS = [45, 30, 15, 7, 1]                # days before departure
DELAY_RANGE_SECONDS = (1.0, 2.5)             # randomized, not fixed, rate-limiting

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]


def scrape_one_search(page, origin, destination, days_out):
    departure_date = (datetime.now() + timedelta(days=days_out)).strftime("%Y-%m-%d")

    page.goto(MOCK_SITE_URL)
    page.select_option("#from", origin)
    page.select_option("#to", destination)
    page.fill("#date", departure_date)
    page.click("button[type='submit']")
    page.wait_for_url("**/results.html*")
    page.wait_for_selector("[data-testid='flight-card']", timeout=5000)

    cards = page.query_selector_all("[data-testid='flight-card']")
    results = []
    for card in cards:
        airline_text = card.query_selector("[data-testid='airline-name']").inner_text()
        airline_name = airline_text.split(" · ")[0]
        flight_code = airline_text.split(" · ")[1] if " · " in airline_text else ""
        fare_text = card.query_selector("[data-testid='fare-price']").inner_text()
        fare = int(fare_text.replace("₹", "").replace(",", ""))
        components = split_total_fare(fare)

        results.append({
            "route": f"{origin}-{destination}",
            "airline": airline_name,
            "flight": flight_code,
            "departure_date": departure_date,
            "collection_time": datetime.now().strftime("%Y-%m-%d"),
            "booking_horizon": f"T+{days_out}",
            "cabin": "Economy",
            "base_fare": components["base_fare"],
            "fuel_surcharge": components["fuel_surcharge"],
            "udf": components["udf"],
            "convenience_fee": components["convenience_fee"],
            "gst": components["gst"],
            "total_fare": fare,
            "availability": "Available",
            "source": "Scraped (technical demo site)",
            "quality_status": "Valid",
        })
    return results


def main():
    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for origin, destination in ROUTES:
            # A fresh context per route = a fresh session (cookies, storage)
            # with its own rotated User-Agent — mirrors how a real scraper
            # would isolate sessions per search identity.
            context = browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = context.new_page()

            for days_out in HORIZONS:
                print(f"Scraping {origin}-{destination} at T+{days_out}...")
                rows = scrape_one_search(page, origin, destination, days_out)
                all_rows.extend(rows)
                print(f"  -> collected {len(rows)} fare observations")
                time.sleep(random.uniform(*DELAY_RANGE_SECONDS))  # randomized rate-limiting

            context.close()

        browser.close()

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone. Scraped {len(all_rows)} total fare observations.")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run and manually verify**

Run: `cd scraper && python3 scrape_real_data.py`
Expected: prints varying delay-implied timings and "Done. Scraped 20 total fare observations." (2 routes × 5 horizons × 2 flights per mock result page — verify actual count against printed output). Then:
`python3 -c "import pandas as pd; df = pd.read_csv('../backend/fares_scraped.csv'); print(df.columns.tolist()); print(len(df))"`
Expected: columns include `fuel_surcharge, udf, convenience_fee, gst` (not `taxes`).

- [ ] **Step 3: Commit**

```bash
git add scraper/scrape_real_data.py
git commit -m "feat: demonstrate UA rotation, session isolation and randomized rate-limiting in the scraper"
```

---

### Task 8: Refactor `clean_data.py` into tested pure functions + merge scraped data

**Files:**
- Modify: `backend/clean_data.py` (full rewrite — file is 51 lines, entirely replaced)
- Test: `backend/test_clean_data.py`

**Interfaces:**
- Produces: `flag_missing_fares(df) -> df`, `flag_sold_out(df) -> df`, `flag_duplicates(df) -> df`, `flag_outliers(df) -> df`, `merge_scraped(synthetic_df, scraped_df) -> df` — each a pure function on a pandas DataFrame, orchestrated by the script's `if __name__ == "__main__"` block. Consumed by `test_clean_data.py`; the script itself is still what `calculate_index.py` depends on via `fares_cleaned.csv`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/test_clean_data.py
import pandas as pd
from clean_data import flag_missing_fares, flag_sold_out, flag_duplicates, flag_outliers, merge_scraped


def _base_df(rows):
    df = pd.DataFrame(rows)
    df["quality_status"] = "Valid"
    df["exclusion_reason"] = ""
    return df


def test_flag_missing_fares_excludes_nan_total_fare():
    df = _base_df([
        {"route": "DEL-BOM", "total_fare": 5000, "availability": "Available"},
        {"route": "DEL-BOM", "total_fare": None, "availability": "Available"},
    ])
    result = flag_missing_fares(df)
    assert result.loc[1, "quality_status"] == "Excluded"
    assert result.loc[1, "exclusion_reason"] == "Missing fare"
    assert result.loc[0, "quality_status"] == "Valid"


def test_flag_sold_out_flags_but_does_not_exclude():
    df = _base_df([
        {"route": "DEL-BOM", "total_fare": 5000, "availability": "Sold Out"},
    ])
    result = flag_sold_out(df)
    assert result.loc[0, "quality_status"] == "Flagged"
    assert result.loc[0, "exclusion_reason"] == "Sold out at collection time"


def test_flag_duplicates_excludes_repeats_within_same_round():
    df = _base_df([
        {"collection_round": 1, "route": "DEL-BOM", "airline": "IndiGo", "flight": "6E101",
         "booking_horizon": "T+1", "total_fare": 5000, "availability": "Available"},
        {"collection_round": 1, "route": "DEL-BOM", "airline": "IndiGo", "flight": "6E101",
         "booking_horizon": "T+1", "total_fare": 5100, "availability": "Available"},
    ])
    result = flag_duplicates(df)
    assert result.loc[0, "quality_status"] == "Valid"
    assert result.loc[1, "quality_status"] == "Excluded"
    assert result.loc[1, "exclusion_reason"] == "Duplicate observation"


def test_flag_outliers_flags_fares_far_from_route_mean():
    rows = [{"route": "DEL-BOM", "total_fare": 5000, "availability": "Available"} for _ in range(10)]
    rows.append({"route": "DEL-BOM", "total_fare": 50000, "availability": "Available"})
    df = _base_df(rows)
    result = flag_outliers(df)
    assert result.loc[10, "quality_status"] == "Flagged"
    assert result.loc[10, "exclusion_reason"] == "Outlier fare for this route"
    assert (result.loc[:9, "quality_status"] == "Valid").all()


def test_merge_scraped_stamps_latest_round_and_new_ids():
    synthetic = pd.DataFrame({
        "record_id": [1, 2],
        "collection_round": [1, 2],
        "route": ["DEL-BOM", "DEL-BOM"],
    })
    scraped = pd.DataFrame({
        "route": ["DEL-BOM", "DEL-BLR"],
    })
    merged = merge_scraped(synthetic, scraped)
    assert len(merged) == 4
    scraped_rows = merged[merged["record_id"] > 2]
    assert (scraped_rows["collection_round"] == 2).all()
    assert set(scraped_rows["record_id"]) == {3, 4}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest test_clean_data.py -v`
Expected: FAIL — `ImportError: cannot import name 'flag_missing_fares' from 'clean_data'` (the old script has no such function)

- [ ] **Step 3: Rewrite clean_data.py**

```python
# backend/clean_data.py
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

    if os.path.exists("fares_scraped.csv"):
        scraped = pd.read_csv("fares_scraped.csv")
        df = merge_scraped(synthetic, scraped)
        print(f"Merged {len(scraped)} scraped observations into the latest round.")
    else:
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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest test_clean_data.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full pipeline end-to-end and re-check the math tests**

```bash
cd backend
python3 generate_data.py
python3 clean_data.py
python3 calculate_dgca_weights.py
python3 calculate_index.py
python3 load_to_database.py
pytest -v
```
Expected: all tests pass (18 total: 13 in `test_index_math.py` + 5 in `test_clean_data.py`), and `clean_data.py`'s printed summary shows a "Merged N scraped observations..." line if `fares_scraped.csv` exists from Task 7.

- [ ] **Step 6: Commit**

```bash
git add backend/clean_data.py backend/test_clean_data.py
git commit -m "refactor: extract clean_data.py quality checks into tested pure functions, merge scraped data"
```

---

### Task 9: Backtest module

**Files:**
- Create: `backend/backtest_metrics.py`
- Test: `backend/test_backtest_metrics.py`
- Create: `backend/backtest_index.py`
- Modify: `backend/main.py` (add `/api/backtest`)

**Interfaces:**
- Consumes: `weighted_airix` from `index_math.py`, `true_index_daily.csv` from Task 2, `airix_trend.csv` and `route_weights.csv` from the existing pipeline.
- Produces: `mean_absolute_error/root_mean_squared_error/mean_absolute_pct_error(computed: list[float], reference: list[float]) -> float`; `backend/backtest_series.csv`, `backend/backtest_summary.json` (keys: `data_source, periods_compared, mae, rmse, mape_pct`); `GET /api/backtest` returning `{"summary": {...}, "series": [...]}`. Consumed by Task 10 (frontend validation page).

- [ ] **Step 1: Write the failing tests for the error metrics**

```python
# backend/test_backtest_metrics.py
import pytest
from backtest_metrics import mean_absolute_error, root_mean_squared_error, mean_absolute_pct_error


def test_mean_absolute_error_perfect_match_is_zero():
    assert mean_absolute_error([100, 101, 102], [100, 101, 102]) == 0

def test_mean_absolute_error_basic():
    assert mean_absolute_error([100, 110], [90, 120]) == pytest.approx(10.0)

def test_root_mean_squared_error_basic():
    # errors are 3 and 4 -> sqrt((9+16)/2) = sqrt(12.5)
    result = root_mean_squared_error([100, 100], [103, 96])
    assert result == pytest.approx(12.5 ** 0.5)

def test_mean_absolute_pct_error_basic():
    # |110-100|/100 = 0.10 -> 10%
    assert mean_absolute_pct_error([110], [100]) == pytest.approx(10.0)

def test_metrics_reject_mismatched_lengths():
    with pytest.raises(ValueError):
        mean_absolute_error([100], [100, 101])
    with pytest.raises(ValueError):
        root_mean_squared_error([100], [100, 101])
    with pytest.raises(ValueError):
        mean_absolute_pct_error([100], [100, 101])

def test_metrics_reject_empty_input():
    with pytest.raises(ValueError):
        mean_absolute_error([], [])
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest test_backtest_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest_metrics'`

- [ ] **Step 3: Implement the metrics module**

```python
# backend/backtest_metrics.py
"""
backtest_metrics.py
Pure, testable error-metric functions used to validate AIRIX's computed
index against a reference series (ground truth or, eventually, real DGCA
fare data). Kept separate from backtest_index.py the same way
index_math.py is kept separate from calculate_index.py.
"""
import math


def _check_inputs(computed, reference):
    if len(computed) != len(reference):
        raise ValueError("computed and reference must be the same length")
    if len(computed) == 0:
        raise ValueError("computed and reference cannot be empty")


def mean_absolute_error(computed, reference):
    _check_inputs(computed, reference)
    return sum(abs(c - r) for c, r in zip(computed, reference)) / len(computed)


def root_mean_squared_error(computed, reference):
    _check_inputs(computed, reference)
    return math.sqrt(sum((c - r) ** 2 for c, r in zip(computed, reference)) / len(computed))


def mean_absolute_pct_error(computed, reference):
    _check_inputs(computed, reference)
    errors = [abs((c - r) / r) for c, r in zip(computed, reference) if r != 0]
    if not errors:
        raise ValueError("reference values are all zero; cannot compute MAPE")
    return sum(errors) / len(errors) * 100
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest test_backtest_metrics.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Implement the backtest orchestration script**

```python
# backend/backtest_index.py
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
```

- [ ] **Step 6: Run it and verify output**

Run: `cd backend && python3 backtest_index.py`
Expected: prints "Backtest (synthetic_proxy_pending_dgca): 35 periods compared." with MAE/RMSE/MAPE values, and creates `backtest_series.csv` (35 rows) and `backtest_summary.json`. MAPE should be small (a few percent) — if it's huge (>50%), the noise parameters in Task 2's generator are miscalibrated relative to `2.5 * std` outlier flagging; re-check before proceeding.

- [ ] **Step 7: Add the API endpoint**

Add near the top of `backend/main.py` (with the other imports): `import json`

Append to `backend/main.py` (after the last existing endpoint, `get_data_quality`):

```python
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
```

- [ ] **Step 8: Verify the endpoint**

Run: `cd backend && uvicorn main:app --reload`, then `curl http://127.0.0.1:8000/api/backtest`
Expected: JSON with `summary.data_source == "synthetic_proxy_pending_dgca"` and a 35-entry `series` array.

- [ ] **Step 9: Commit**

```bash
git add backend/backtest_metrics.py backend/test_backtest_metrics.py backend/backtest_index.py backend/main.py
git commit -m "feat: add synthetic-proxy backtest module and /api/backtest endpoint"
```

---

### Task 10: Model Validation page

**Files:**
- Create: `frontend/src/app/validation/page.js`
- Modify: `frontend/src/app/page.js:123-128` (nav)

**Interfaces:**
- Consumes: `GET /api/backtest` from Task 9.

- [ ] **Step 1: Create the validation page**

```jsx
// frontend/src/app/validation/page.js
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const API_URL = "http://127.0.0.1:8000";

export default function Validation() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggleTheme() {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("airix-theme", next ? "dark" : "light");
  }

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch(`${API_URL}/api/backtest`);
        if (!res.ok) throw new Error("No backtest results found. Run backtest_index.py first.");
        setData(await res.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] font-mono-num text-sm">
        LOADING BACKTEST...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] flex-col gap-4">
        <p className="text-red-500">{error || "No data"}</p>
        <Link href="/" className="text-[var(--amber)] underline text-sm">Back to dashboard</Link>
      </div>
    );
  }

  const { summary, series } = data;
  const isProxy = summary.data_source.includes("synthetic");

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="bg-[var(--panel-navy)] text-[var(--panel-text)] border-b border-[var(--panel-border)]">
        <div className="max-w-4xl mx-auto px-6 sm:px-10 py-6">
          <div className="flex items-center justify-between mb-4">
            <Link href="/" className="text-xs text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors">
              ← Dashboard
            </Link>
            <button
              onClick={toggleTheme}
              className="text-xs font-medium text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors px-3 py-1.5 rounded border border-[var(--panel-border)]"
            >
              {isDark ? "Light" : "Dark"}
            </button>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Model Validation</h1>
          <p className="text-sm text-[var(--panel-text-muted)] mt-1">
            {summary.periods_compared}-period back-test of the computed index against a reference series
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 sm:px-10 py-10 space-y-8">
        {isProxy && (
          <div className="border border-[var(--amber)] rounded-lg bg-[var(--surface)] p-4 text-sm">
            <strong>Synthetic proxy backtest.</strong> No real DGCA monthly average-fare
            dataset is wired in yet, so this validates AIRIX against the known
            ground-truth index used to generate the synthetic data, not real
            market data. Run <code>backtest_index.py --reference &lt;dgca_file.csv&gt; --label real_dgca</code> once
            a real dataset is available to replace this.
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Periods Compared" value={summary.periods_compared} />
          <StatCard label="MAE" value={summary.mae} />
          <StatCard label="RMSE" value={summary.rmse} />
          <StatCard label="MAPE" value={`${summary.mape_pct}%`} color="var(--amber)" />
        </div>

        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <h2 className="text-sm font-semibold mb-6">Computed AIRIX vs. Reference Index</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="collection_round" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 13 }}
              />
              <Legend />
              <Line type="monotone" dataKey="computed_airix" name="Computed AIRIX" stroke="var(--amber)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="reference_airix" name="Reference" stroke="var(--teal)" strokeWidth={2} strokeDasharray="4 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      </main>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-5">
      <p className="text-xs text-[var(--text-muted)] mb-1">{label}</p>
      <p className="font-mono-num text-2xl font-semibold" style={{ color: color || "var(--text)" }}>
        {value}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Add a nav link**

Replace `frontend/src/app/page.js:123-128`:

```jsx
              <nav className="flex items-center gap-4 text-sm text-[var(--panel-text-muted)]">
                <span className="text-[var(--panel-text)] border-b border-[var(--amber)] pb-0.5">Dashboard</span>
                <a href="/data-quality" className="hover:text-[var(--panel-text)] transition-colors">
                  Data Quality
                </a>
                <a href="/validation" className="hover:text-[var(--panel-text)] transition-colors">
                  Model Validation
                </a>
              </nav>
```

- [ ] **Step 3: Verify in the browser**

Run: `cd frontend && npm run dev`, visit `http://localhost:3000/validation` with the backend running and `backtest_summary.json` present (from Task 9).
Expected: metric cards, a dashed reference line vs solid computed line, and the amber proxy-data disclaimer box.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/validation/page.js frontend/src/app/page.js
git commit -m "feat: add Model Validation page for the backtest results"
```

---

### Task 11: Sector-wise heatmap

**Files:**
- Modify: `backend/main.py` (append `/api/heatmap`)
- Modify: `frontend/src/app/page.js` (new `Heatmap` component + section)

**Interfaces:**
- Consumes: `aggregate_series` from Task 5, `RouteIndexSnapshot.collection_date` from Task 3.
- Produces: `GET /api/heatmap?freq=daily|weekly|monthly` returning `{"routes": [...], "periods": [...], "matrix": [[float|null, ...], ...]}` where `matrix[i][j]` is the index value for `routes[i]` at `periods[j]`.

- [ ] **Step 1: Add the heatmap endpoint**

Append to `backend/main.py`:

```python
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
```

- [ ] **Step 2: Verify the endpoint**

Run: `curl "http://127.0.0.1:8000/api/heatmap?freq=weekly"`
Expected: `routes` has 10 entries, `periods` has ~5 entries, `matrix` is 10×5.

- [ ] **Step 3: Add the frontend heatmap**

Add this component to `frontend/src/app/page.js` (after the `MiniStat` function at the end of the file):

```jsx
function Heatmap({ apiUrl }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(`${apiUrl}/api/heatmap?freq=weekly`)
      .then((res) => res.json())
      .then(setData)
      .catch(() => setData(null));
  }, [apiUrl]);

  if (!data || data.routes.length === 0) return null;

  const allValues = data.matrix.flat().filter((v) => v !== null);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);

  function colorFor(value) {
    if (value === null) return "var(--border)";
    const t = max === min ? 0.5 : (value - min) / (max - min);
    const teal = [20, 184, 166];
    const amber = [217, 119, 6];
    const rgb = teal.map((c, i) => Math.round(c + (amber[i] - c) * t));
    return `rgb(${rgb.join(",")})`;
  }

  return (
    <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6 overflow-x-auto">
      <h2 className="text-sm font-semibold mb-6">Sector-Wise Fare Index Heatmap (Weekly)</h2>
      <table className="text-xs border-separate" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th className="text-left pr-3 pb-1 text-[var(--text-muted)] font-medium">ROUTE</th>
            {data.periods.map((p) => (
              <th key={p} className="px-2 pb-1 text-[var(--text-muted)] font-medium font-mono-num">{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.routes.map((route, ri) => (
            <tr key={route}>
              <td className="pr-3 py-1 font-medium">{route}</td>
              {data.matrix[ri].map((value, ci) => (
                <td
                  key={ci}
                  title={value === null ? "no data" : `${route} — ${data.periods[ci]}: ${value}`}
                  className="w-14 h-8 text-center font-mono-num rounded"
                  style={{ background: colorFor(value), color: "#fff" }}
                >
                  {value === null ? "" : value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

Then render it in the main dashboard `<main>` block, immediately after the "AIRIX Trend" `</section>` closes and before the "Contributions panel" `<section>` begins:

```jsx
        <Heatmap apiUrl={API_URL} />
```

- [ ] **Step 4: Verify in the browser**

Run: `cd frontend && npm run dev`, visit `http://localhost:3000`.
Expected: a 10-row × ~5-column colored grid between the trend chart and the contributions chart, teal-to-amber gradient, tooltips on hover showing exact values.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py frontend/src/app/page.js
git commit -m "feat: add sector-wise fare index heatmap"
```

---

### Task 12: Lead-time elasticity + fare breakdown on route detail

**Files:**
- Modify: `backend/index_math.py` (append function), `backend/test_index_math.py` (append tests)
- Modify: `backend/main.py:11` (import), `backend/main.py:105-192` (`get_route_detail`)
- Modify: `frontend/src/app/routes/[route]/page.js:95-99` (stat grid), add new section after `:115`

**Interfaces:**
- Produces: `lead_time_elasticity(fares_by_horizon: dict[str, float]) -> float` (%fare-change per day of lead-time reduction). `GET /api/routes/{route}` response gains `elasticity_pct_per_day: float` and `fare_breakdown: dict[str, float]`.

- [ ] **Step 1: Write the failing test**

Append to `backend/test_index_math.py` (and add `lead_time_elasticity` to the top import line alongside `chain_link_index`):

```python
# ---- lead_time_elasticity ----

def test_lead_time_elasticity_rises_as_departure_approaches():
    # Fare climbs steadily as horizon shrinks -> positive elasticity
    fares = {"T+45": 900, "T+30": 950, "T+15": 1000, "T+7": 1030, "T+1": 1060}
    result = lead_time_elasticity(fares)
    assert result > 0

def test_lead_time_elasticity_zero_for_flat_fares():
    fares = {"T+45": 1000, "T+30": 1000, "T+15": 1000, "T+7": 1000, "T+1": 1000}
    assert lead_time_elasticity(fares) == pytest.approx(0.0)

def test_lead_time_elasticity_requires_two_horizons():
    with pytest.raises(ValueError):
        lead_time_elasticity({"T+1": 1000})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest test_index_math.py -v -k elasticity`
Expected: FAIL — `ImportError: cannot import name 'lead_time_elasticity'`

- [ ] **Step 3: Implement**

Append to `backend/index_math.py`:

```python
def lead_time_elasticity(fares_by_horizon):
    """
    Slope of fare vs. days-to-departure, expressed as %fare-change per day
    of lead-time reduction (positive = fares rise as departure approaches).
    fares_by_horizon: {"T+45": fare, "T+30": fare, ...}
    """
    if len(fares_by_horizon) < 2:
        raise ValueError("need at least two horizons to compute elasticity")

    points = sorted(
        (int(horizon.replace("T+", "")), fare) for horizon, fare in fares_by_horizon.items()
    )
    days = [p[0] for p in points]
    fares = [p[1] for p in points]
    n = len(points)
    mean_days = sum(days) / n
    mean_fare = sum(fares) / n

    numerator = sum((d - mean_days) * (f - mean_fare) for d, f in points)
    denominator = sum((d - mean_days) ** 2 for d in days)
    if denominator == 0:
        raise ValueError("all horizons have the same days-to-departure")

    slope_per_day = numerator / denominator  # rupees per additional day of lead time
    if mean_fare == 0:
        return 0.0
    return round(-slope_per_day / mean_fare * 100, 3)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest test_index_math.py -v`
Expected: PASS (16 tests total)

- [ ] **Step 5: Wire into the API**

Replace `backend/main.py:11` with:

```python
from index_math import weighted_airix, lead_time_elasticity
```
(if Task 6 already changed this line to include `aggregate_frequency`, add `lead_time_elasticity` to the existing `index_math` import instead of duplicating the line.)

In `get_route_detail` (`backend/main.py:105-192`), after the existing `fare_curve` block (originally lines 148-157) and before the `all_contribs` query, insert:

```python
        elasticity_pct_per_day = lead_time_elasticity(fare_curve)

        breakdown_fields = ["base_fare", "fuel_surcharge", "udf", "convenience_fee", "gst"]
        t1_fares = [f for f in fares if f.booking_horizon == "T+1"]
        fare_breakdown = {
            field: round(sum(getattr(f, field) for f in t1_fares) / len(t1_fares), 0) if t1_fares else 0
            for field in breakdown_fields
        }
```

Then add `"elasticity_pct_per_day": elasticity_pct_per_day,` and `"fare_breakdown": fare_breakdown,` to the function's final `return {...}` dict (originally lines 179-190).

- [ ] **Step 6: Verify the endpoint**

Run: `curl http://127.0.0.1:8000/api/routes/DEL-BOM`
Expected: JSON response includes `"elasticity_pct_per_day"` (a small positive number) and `"fare_breakdown"` with 5 keys summing close to `current_average_fare`.

- [ ] **Step 7: Update the route detail page**

Replace `frontend/src/app/routes/[route]/page.js:95-99`:

```jsx
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <StatCard label="Current Route Index" value={detail.current_index} />
          <StatCard label="Current Average Fare" value={`₹${detail.current_average_fare.toLocaleString("en-IN")}`} />
          <StatCard label="Lead-Time Increase" value={`+${detail.lead_time_increase_pct}%`} color="var(--amber)" />
          <StatCard label="Elasticity" value={`${detail.elasticity_pct_per_day}%/day`} color="var(--teal)" />
        </div>
```

Insert this new section immediately after the "Fare by Booking Horizon" `</section>` (originally ending at line 115), before the "Explain Movement" `<section>`:

```jsx
        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <h2 className="text-sm font-semibold mb-4">Fare Breakdown (T+1, average)</h2>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-sm">
            {Object.entries(detail.fare_breakdown).map(([component, value]) => (
              <div key={component}>
                <p className="text-xs text-[var(--text-muted)] capitalize mb-1">{component.replace("_", " ")}</p>
                <p className="font-mono-num">₹{value.toLocaleString("en-IN")}</p>
              </div>
            ))}
          </div>
        </section>
```

- [ ] **Step 8: Verify in the browser**

Run: `cd frontend && npm run dev`, visit `http://localhost:3000/routes/DEL-BOM`.
Expected: a 4th "Elasticity" stat card and a new "Fare Breakdown" section with 5 values.

- [ ] **Step 9: Commit**

```bash
git add backend/index_math.py backend/test_index_math.py backend/main.py frontend/src/app/routes/\[route\]/page.js
git commit -m "feat: add lead-time elasticity metric and fare breakdown to route detail"
```

---

### Task 13: Daily pipeline scheduler

**Files:**
- Create: `backend/scheduler.py`
- Test: `backend/test_scheduler.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `run_pipeline() -> None`, `PIPELINE_STAGES: list[str]` — consumed only by the smoke test and the `if __name__` block.

- [ ] **Step 1: Add the dependency**

Append to `backend/requirements.txt`:

```
APScheduler==3.11.0
```

Run: `cd backend && source venv/bin/activate && pip install APScheduler==3.11.0`

- [ ] **Step 2: Write the failing test**

```python
# backend/test_scheduler.py
from unittest.mock import patch, MagicMock
from scheduler import run_pipeline, PIPELINE_STAGES


def test_pipeline_stages_are_in_dependency_order():
    assert PIPELINE_STAGES == [
        "generate_data.py",
        "clean_data.py",
        "calculate_dgca_weights.py",
        "calculate_index.py",
        "backtest_index.py",
        "load_to_database.py",
    ]

def test_run_pipeline_calls_every_stage_in_order():
    with patch("scheduler.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        run_pipeline()
        called_stages = [call.args[0][1] for call in mock_run.call_args_list]
        assert called_stages == PIPELINE_STAGES

def test_run_pipeline_stops_on_first_failure():
    with patch("scheduler.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1),  # clean_data.py fails
        ]
        run_pipeline()
        assert mock_run.call_count == 2  # never reaches later stages
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend && pytest test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scheduler'`

- [ ] **Step 4: Implement**

```python
# backend/scheduler.py
"""
scheduler.py
Runs the full AIRIX pipeline once daily, unattended — satisfies the
problem statement's requirement for scheduled daily extraction. Each
stage is a subprocess call to the existing pipeline scripts so this file
adds scheduling only, without duplicating pipeline logic.
"""
import subprocess
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

PIPELINE_STAGES = [
    "generate_data.py",
    "clean_data.py",
    "calculate_dgca_weights.py",
    "calculate_index.py",
    "backtest_index.py",
    "load_to_database.py",
]

DAILY_RUN_HOUR = 2  # 02:00 local time — off-peak


def run_pipeline():
    print(f"[{datetime.now().isoformat()}] Starting AIRIX daily pipeline run...")
    for stage in PIPELINE_STAGES:
        print(f"  -> {stage}")
        result = subprocess.run([sys.executable, stage])
        if result.returncode != 0:
            print(f"  !! {stage} failed with exit code {result.returncode}; aborting run.")
            return
    print(f"[{datetime.now().isoformat()}] Pipeline run complete.")


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=DAILY_RUN_HOUR, id="airix_daily_pipeline")
    print(f"AIRIX scheduler started. Daily run scheduled at {DAILY_RUN_HOUR:02d}:00.")
    run_pipeline()  # run once immediately so a demo has fresh data
    scheduler.start()
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && pytest test_scheduler.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Manually verify the scheduler starts**

Run: `cd backend && timeout 15 python3 scheduler.py || true`
Expected: prints "AIRIX scheduler started..." followed by a full pipeline run's output (all 6 stages), then hangs waiting for the next cron trigger until the timeout kills it — confirms it runs standalone without crashing.

- [ ] **Step 7: Commit**

```bash
git add backend/scheduler.py backend/test_scheduler.py backend/requirements.txt
git commit -m "feat: add daily pipeline scheduler via APScheduler"
```

---

### Task 14: API test suite

**Files:**
- Modify: `backend/database.py:12` (configurable DB URL)
- Create: `backend/conftest.py`
- Create: `backend/test_api.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: every endpoint added in Tasks 6, 9, 11, 12 plus the pre-existing ones.

- [ ] **Step 1: Make the database URL configurable**

Replace `backend/database.py:12`:

```python
DATABASE_URL = os.environ.get("AIRIX_DB_URL", "sqlite:///airix.db")
```

Add `import os` to the top of `backend/database.py` alongside the existing imports.

- [ ] **Step 2: Add the test-client dependency**

Append to `backend/requirements.txt`:

```
httpx==0.28.1
```

Run: `cd backend && source venv/bin/activate && pip install httpx==0.28.1`

- [ ] **Step 3: Write conftest.py to isolate the test database**

```python
# backend/conftest.py
"""
conftest.py
Points every test at a throwaway SQLite file instead of the real
airix.db, and does it at import time (module-level, not inside a
fixture function) so it takes effect before database.py or main.py are
first imported by any test module.
"""
import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["AIRIX_DB_URL"] = f"sqlite:///{_tmp_db.name}"
```

- [ ] **Step 4: Write the failing tests**

```python
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


def test_backtest_missing_returns_404():
    res = client.get("/api/backtest")
    assert res.status_code == 404
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && pytest test_api.py -v`
Expected: PASS (7 tests). Note: `test_index_history_rejects_bad_freq` and any endpoint reading `route_weights.csv` rely on that file existing in `backend/` from the real pipeline — run `python3 calculate_dgca_weights.py` first if it's missing.

- [ ] **Step 6: Run the entire suite**

Run: `cd backend && pytest -v`
Expected: PASS — 16 (`test_index_math.py`) + 5 (`test_clean_data.py`) + 3 (`test_fare_breakdown.py`) + 3 (`test_aggregate_frequency.py`) + 6 (`test_backtest_metrics.py`) + 3 (`test_scheduler.py`) + 7 (`test_api.py`) = 43 tests, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add backend/database.py backend/conftest.py backend/test_api.py backend/requirements.txt
git commit -m "test: add isolated FastAPI endpoint test suite"
```

---

### Task 15: Documentation

**Files:**
- Create: `docs/PS_MAPPING.md`
- Modify: `README.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Write the traceability doc**

```markdown
# docs/PS_MAPPING.md
# SIH26056 Problem Statement → AIRIX Feature Mapping

| Problem statement requirement | AIRIX implementation |
|---|---|
| Scrape IndiGo, Air India, Air India Express, Akasa, SpiceJet + 5 major OTAs | `scraper/scrape_real_data.py` — real Playwright scraper (form-fill, async wait, structured extraction, UA rotation, session isolation, randomized rate-limiting). Demonstrated against `scraper/mock_site/` because IndiGo and ixigo's `robots.txt` explicitly disallow automated access to live fare pages (see README "On real-time data collection"); output is merged into the real pipeline via `clean_data.merge_scraped`. |
| Basket of city-pairs from DGCA passenger-traffic data | `backend/calculate_dgca_weights.py`, `backend/dgca_data/city_traffic.csv` |
| T+1/7/15/30/45 booking-horizon capture | `backend/generate_data.py` `HORIZONS`, `backend/scrape_real_data.py` `HORIZONS` |
| Anti-CAPTCHA / IP rotation / session mgmt / rate-limiting | `backend/scrape_real_data.py`: per-route browser context (session isolation), rotated `USER_AGENTS`, randomized `DELAY_RANGE_SECONDS` |
| Outlier/missing/sold-out handling | `backend/clean_data.py`: `flag_missing_fares`, `flag_sold_out`, `flag_duplicates`, `flag_outliers` |
| Base fare / taxes / UDF / convenience fee separation | `backend/fare_breakdown.py` `split_total_fare`; stored per-observation in `FareObservation` |
| Daily / weekly / monthly index frequency | `backend/aggregate_frequency.py`; `GET /api/index/history?freq=` and `GET /api/heatmap?freq=` |
| Price trend visualization | `frontend/src/app/page.js` — AIRIX Trend chart with frequency toggle |
| Sector-wise heatmap | `GET /api/heatmap`; `Heatmap` component in `frontend/src/app/page.js` |
| Lead-time elasticity curve | `backend/index_math.py` `lead_time_elasticity`; `frontend/src/app/routes/[route]/page.js` |
| API for NSO/RBI consumption | FastAPI app (`backend/main.py`), auto-documented at `/docs` |
| Index-construction methodology given routes and weights | Jevons Index (`backend/index_math.py` `jevons_index`) + real DGCA passenger-share weights (`route_weights.csv`), chain-linked across periods (`chain_link_index`) |
| Documentation | This file, `README.md` |
| Automated testing | `backend/test_*.py` — 43 tests across math, cleaning, aggregation, backtest metrics, scheduler, and API layers |
| ≥30-day back-test against DGCA monthly average-fare data | `backend/backtest_index.py` — currently a synthetic-proxy backtest (35 days, ground-truth-recovery validation) labeled `synthetic_proxy_pending_dgca`; accepts a real DGCA CSV via `--reference` once sourced |
| Scheduled daily extraction | `backend/scheduler.py` (APScheduler, daily cron) |
```

- [ ] **Step 2: Update the README**

In `README.md`, replace the **Backend** code block under "Running locally" (originally lines 40-51):

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 generate_data.py
python3 clean_data.py
python3 calculate_dgca_weights.py
python3 calculate_index.py
python3 backtest_index.py
python3 load_to_database.py
uvicorn main:app --reload
```

Add a new subsection immediately after the **Tests** block (originally lines 62-66):

```markdown
**Scheduling**
```bash
cd backend
python3 scheduler.py
```
Runs the full pipeline once immediately, then daily at 02:00. See `docs/PS_MAPPING.md` for how this and every other pipeline stage maps to the problem statement.

**Model validation**

Visit `http://localhost:3000/validation` for the back-test results (currently a synthetic-proxy validation — see the disclaimer on that page and in `docs/PS_MAPPING.md`).
```

- [ ] **Step 3: Commit**

```bash
git add docs/PS_MAPPING.md README.md
git commit -m "docs: add problem-statement traceability doc and update setup instructions"
```

---

## Self-Review Notes

- **Spec coverage:** all 10 gaps listed in the spec map to at least one task — backtest (9), scraper integration (8), frequencies (5/6/11), heatmap (11), fare decomposition (1/2/3/7), elasticity (12), scheduler (13), anti-bot demo (7), test coverage (8/9/13/14), traceability doc (15).
- **Sequencing:** Tasks 1→2→3 must run in order (fare_breakdown → generator → schema/loader) since each is a hard dependency of the next. Tasks 4→5→6 similarly chain. Task 7 depends on Task 1 only (not Task 2), so it can run any time after Task 1. Task 8 depends on Task 7's output schema. Task 9 depends on Task 2 (`true_index_daily.csv`) and Task 4 (imports `weighted_airix`, already present). Tasks 10/11/12 depend on Task 9/6/3 respectively. Task 13 depends on Task 9 (includes `backtest_index.py` in `PIPELINE_STAGES`). Task 14 depends on every endpoint added by 6/9/11/12. Task 15 should run last.
- **Type/name consistency check:** `collection_date` (Task 3) is used identically in Task 6, 11, 14. `fare_breakdown` dict keys (`base_fare, fuel_surcharge, udf, convenience_fee, gst`) are identical across Task 1, 3, 7, 12, 14, 15. `aggregate_series(series, freq)` signature from Task 5 is called the same way in Task 6 and Task 11.
