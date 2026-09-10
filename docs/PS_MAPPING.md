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
