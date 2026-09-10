# AIRIX SIH26056 Enhancement Spec

## Problem

AIRIX (Airfare Intelligence & Price Index Engine) is a working prototype for
SIH26056 (MoSPI). A gap analysis against the official problem statement
found the statistical core (Jevons Index, DGCA-weighted routes, audit
trail, tested math, API, dashboard) is solid, but several items the
problem statement names explicitly are missing or only partially done:

1. **No 30-day back-test** against a reference fare series — the PS's
   "Expected Solution" names this outright.
2. **Scraped data is disconnected from the real pipeline** — `fares_scraped.csv`
   exists but `clean_data.py` never reads it.
3. **No daily/weekly/monthly index frequencies** — only 5 weekly "rounds."
4. **No sector-wise heatmap** — named explicitly in the PS's dashboard requirements.
5. **Fare isn't decomposed** into base fare / fuel surcharge / UDF /
   convenience fee / GST — PS asks for this split explicitly; today it's
   just `base_fare` + a flat 18% `taxes`.
6. **No lead-time elasticity metric** — only a raw fare-by-horizon line.
7. **No scheduled daily extraction** — pipeline is run manually.
8. **No anti-bot technique demonstration** in the scraper (UA rotation,
   session isolation, randomized rate-limiting) — PS names these as
   required scraper capabilities.
9. **Test coverage is math-only** — `clean_data.py` and the API have zero tests.
10. **No PS-to-feature traceability doc** for judges.

## Decisions (confirmed with the user)

- **Scope:** build all of the above (no tiering/deferral).
- **Backtest data source:** no real DGCA monthly average-fare dataset is in
  hand yet, and the MoSPI portal (`esankhyiki.mospi.gov.in`) couldn't be
  crawled for one from this session (JS-rendered SPA). The backtest ships
  as a **synthetic proxy**: the data generator embeds a hidden "true"
  per-route daily index; the backtest checks whether AIRIX recovers that
  true signal from noisy simulated observations. It is labeled
  `"synthetic_proxy_pending_dgca"` everywhere it surfaces (JSON, UI) and
  built so a real DGCA CSV can be swapped in later via a documented
  `--reference` flag — this is not a stub, both paths are fully implemented.
- **Plan structure:** one combined, phase-ordered plan (not split into
  parallel sub-plans), since a solo/small team is executing this for a
  hackathon deadline.

## Design choices that affect multiple tasks

- **Daily granularity, not weekly rounds.** `collection_round` becomes a
  daily sequence number (1..35) instead of 5 weekly snapshots. This is
  required both for the 30-day backtest and for daily/weekly/monthly
  index frequencies, and it requires **no changes** to the existing
  round-indexed logic in `calculate_index.py` — that code already treats
  `ROUNDS` generically. Only the generator, the DB schema (needs a real
  calendar date per round), and anything presenting rounds as "weeks"
  need to change.
- **Weekly/monthly aggregation = chain-linking, not re-averaging.**
  Combining daily Jevons-index values into a period value is done via
  the geometric mean of the daily values in that period (a new
  `chain_link_index` function), not an arithmetic mean — staying
  consistent with the geometric-mean methodology used everywhere else in
  AIRIX. This only needs the already-computed daily index values, not a
  re-read of raw fare observations.
- **Fare decomposition is a fixed-proportion split of `total_fare`**,
  shared via one pure function (`fare_breakdown.split_total_fare`) used by
  both the synthetic generator (which computes `total_fare` from the
  market model, then splits it) and the scraper (which only observes
  `total_fare` from the mock site, then splits it the same way) — so both
  sources produce data in an identical shape.
- **Elasticity** is the slope of a linear regression of fare against
  days-to-departure, expressed as %fare-change per day of lead-time
  reduction — a real (if simple) elasticity estimate, not just the
  existing T+45→T+1 percentage delta.

## Out of scope

- Actually scraping real airline/OTA sites (explicitly against their
  robots.txt; already documented in the README as a deliberate choice).
- Authentication/authorization on the API.
- Deployment/containerization.
- Sourcing a real DGCA monthly average-fare CSV (left as a follow-up the
  user or teammate does separately; the backtest module is ready to
  consume it once it exists).
