# AIRIX — Airfare Intelligence & Price Index Engine

[![Tests](https://github.com/kabir-sinha/airix/actions/workflows/tests.yml/badge.svg)](https://github.com/kabir-sinha/airix/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![SIH 2026](https://img.shields.io/badge/SIH%202026-SIH26056-orange)

**SIH26056 · Ministry of Statistics & Programme Implementation (MoSPI)**

AIRIX is a real-time statistical price index for Indian domestic airfares — built to help track how airfares move over time, which routes are driving that movement, and how prices change as departure approaches.

Airfares change constantly across airlines, routes, and booking dates. Looking at any single flight's price doesn't tell you how the overall market is moving. AIRIX systematically collects fare observations, makes them statistically comparable, and combines them into a single, defensible index — the same way a real government price index (like a CPI) is built.

![AIRIX overview dashboard: current index, routes, observations, data quality and the weekly trend](docs/screenshots/airix_overview.webp)

*Overview dashboard (synthetic demo data). Also included: route index, lead-time index, route detail with fare breakdown, data quality and model validation pages.*

## What it does

- **Collects** structured fare observations across routes, airlines, and 5 booking horizons (T+45 → T+1)
- **Cleans** the data with a transparent audit trail — nothing is silently dropped; every excluded or flagged observation records why
- **Measures** price movement using the **Jevons Index** (geometric mean of price relatives), the same statistical method used in real price indices
- **Weights** each route by its real share of domestic air traffic, sourced from actual DGCA passenger data — not an arbitrary assumption
- **Explains** what's driving any given movement in the index — which routes, by how much, and why
- **Validates** its own data quality, openly, with a dedicated audit page

## Why the Jevons Index

A simple arithmetic average of price changes gives misleading results — it treats a price doubling and a price halving asymmetrically. The Jevons Index (geometric mean of price relatives) avoids this, which is why it's a standard tool in real-world price index construction.

## Architecture

```
Fare data → Cleaning & audit trail → Jevons Index calc → SQLite (historical snapshots) → FastAPI → Next.js dashboard
```


- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: Next.js, React, Tailwind CSS, Recharts
- **Statistics**: Jevons Index, real DGCA-weighted aggregation ([Vonter/india-aviation-traffic](https://github.com/Vonter/india-aviation-traffic), ODbL-licensed)
- **Testing**: pytest — 43 tests across 7 files proving the core index math, data cleaning, fare-splitting, backtest metrics, scheduling, and API layers are correct
- **Data collection**: a working Playwright-based scraper, validated against a purpose-built mock booking site (see note below)

## On real-time data collection

The problem statement calls for automated web scraping of live airline/OTA fare pages. We built and validated a real, working scraper (Playwright — form-filling, async content handling, structured extraction). However, we found that major carriers and OTAs (verified: IndiGo, ixigo) explicitly disallow automated access to their live search/fare pages via `robots.txt`, protecting commercially sensitive pricing data — a restriction that's also the subject of ongoing litigation even for large aggregators (e.g. Ryanair v. Skyscanner, Ryanair v. Booking.com/Etraveli). In respect of that, our scraper is demonstrated against a representative mock booking interface rather than live production pages. A production deployment would connect the same architecture to a licensed data-sharing agreement or an official government-brokered access channel — the same pipeline real metasearch engines use.

## Design decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| **Jevons index** (geometric mean of price relatives) for each route | Treats a fare doubling and a fare halving symmetrically. It is also the formula MoSPI uses for elementary indices in India's CPI 2024 series. | Less intuitive to explain than a simple average, so the dashboard shows every route's contribution alongside the headline number. |
| **Route weights from DGCA passenger traffic**, not equal weights | A thin route should not move the index as much as DEL-BOM. With DGCA city-pair data, DEL-BOM carries 21% of the weight and DEL-BLR 15%. | Weights come from the latest full year of DGCA data and stay fixed until they are refreshed. |
| **Weekly and monthly values as the geometric mean of the daily index** | Keeps one geometric-mean method at every frequency instead of mixing formulas. | A weekly or monthly value summarises the daily index levels; it is not recomputed from raw fares. |
| **Synthetic data and a mock booking site** instead of scraping live airline and OTA pages | The live fare pages we checked disallow automated access, so the scraper is proven end to end on a site built for that purpose. | The index demonstrates the method, not the live market. Production would need a licensed or government-brokered fare feed. |
| **Nothing silently dropped** | Every flagged or excluded observation keeps its reason (sold out, duplicate, outlier, missing), and the Data Quality page shows the totals. | Slightly more storage and a more detailed schema. |
| **Every pipeline run kept as a dated snapshot** (SQLite) | History is never overwritten, so the results of every past run stay available. | SQLite suits a single scheduled pipeline; a multi-user deployment would move to a server database. |
| **Validation against known ground truth** | A 35-period back-test against the index used to generate the data gives MAE 5.36 index points (MAPE 5.3%), shown openly on the Model Validation page. | This is a synthetic proxy. The back-test already accepts a real DGCA average-fare file (`--reference`), which is the next step. |

## Running locally

**Backend**
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

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`.

**Tests**
```bash
cd backend
pytest -v
```

**Scheduling**
```bash
cd backend
python3 scheduler.py
```
Runs the full pipeline once immediately, then daily at 02:00. See `docs/PS_MAPPING.md` for how this and every other pipeline stage maps to the problem statement.

**Model validation**

Visit `http://localhost:3000/validation` for the back-test results (currently a synthetic-proxy validation — see the disclaimer on that page and in `docs/PS_MAPPING.md`).

## Repository map

```
backend/     pipeline scripts (generate → clean → weight → index → backtest → load), FastAPI app (main.py),
             index maths (index_math.py), scheduler, 43 pytest tests (test_*.py), dgca_data/
frontend/    Next.js dashboard: overview, routes, lead time, data quality, validation (see frontend/README.md)
scraper/     Playwright scraper and the mock booking site it is validated against
docs/        PS_MAPPING.md (problem statement → implementation), design notes
```

## Team

Built by **Team AIRIX**, Bennett University, for Smart India Hackathon 2026 (problem statement SIH26056, MoSPI). Team lead: [Kabir Sinha](https://github.com/kabir-sinha).

Sister project: [SOCRIX](https://github.com/kabir-sinha/socrix), SOC assurance analytics for NCIIPC (SIH26157).

## Security

Please report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Do not open public issues for security problems.

## Licence and data

All rights reserved during SIH 2026 evaluation. Third-party material keeps its own terms — see [NOTICE](NOTICE):

- Route weights use DGCA traffic data from [Vonter/india-aviation-traffic](https://github.com/Vonter/india-aviation-traffic), under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1.0/). `backend/dgca_data/city_traffic.csv` and the derived `backend/route_weights.csv` stay under ODbL. Data: DGCA and Ministry of Civil Aviation.
- Fare data is synthetic or comes from the bundled mock booking site; no live airline or OTA pages were scraped.

Not affiliated with or endorsed by MoSPI, DGCA or any airline.
