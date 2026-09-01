"""
scrape_real_data.py
A real Playwright-based scraper: fills a search form, submits it, waits for
async-loaded results, and extracts structured fare data — the same technique
needed for a real flight-search site. Targets our local mock_site for
technical validation, respecting the robots.txt constraints we found on
real airline/OTA sites (see project notes).
"""

import time
import csv
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# ---- Config ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_SITE_URL = f"file://{os.path.join(SCRIPT_DIR, 'mock_site', 'index.html')}"
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "..", "backend", "fares_scraped.csv")

ROUTES = [("DEL", "BOM"), ("DEL", "BLR")]   # 1-2 routes, as planned
HORIZONS = [45, 30, 15, 7, 1]                # days before departure
POLITE_DELAY_SECONDS = 1.5                   # rate-limit ourselves between requests


def scrape_one_search(page, origin, destination, days_out):
    departure_date = (datetime.now() + timedelta(days=days_out)).strftime("%Y-%m-%d")

    # 1. Load the search form
    page.goto(MOCK_SITE_URL)

    # 2. Fill it out like a real user would
    page.select_option("#from", origin)
    page.select_option("#to", destination)
    page.fill("#date", departure_date)

    # 3. Submit and wait for navigation to the results page
    page.click("button[type='submit']")
    page.wait_for_url("**/results.html*")

    # 4. Wait for the ASYNC content — this is the part a naive scraper would miss
    page.wait_for_selector("[data-testid='flight-card']", timeout=5000)

    # 5. Extract structured data from each flight card
    cards = page.query_selector_all("[data-testid='flight-card']")
    results = []
    for card in cards:
        airline_text = card.query_selector("[data-testid='airline-name']").inner_text()
        airline_name = airline_text.split(" · ")[0]
        flight_code = airline_text.split(" · ")[1] if " · " in airline_text else ""
        fare_text = card.query_selector("[data-testid='fare-price']").inner_text()
        fare = int(fare_text.replace("₹", "").replace(",", ""))

        results.append({
            "route": f"{origin}-{destination}",
            "airline": airline_name,
            "flight": flight_code,
            "departure_date": departure_date,
            "collection_time": datetime.now().strftime("%Y-%m-%d"),
            "booking_horizon": f"T+{days_out}",
            "cabin": "Economy",
            "base_fare": round(fare / 1.18),
            "taxes": fare - round(fare / 1.18),
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
        page = browser.new_page()

        for origin, destination in ROUTES:
            for days_out in HORIZONS:
                print(f"Scraping {origin}-{destination} at T+{days_out}...")
                rows = scrape_one_search(page, origin, destination, days_out)
                all_rows.extend(rows)
                print(f"  -> collected {len(rows)} fare observations")
                time.sleep(POLITE_DELAY_SECONDS)  # be polite even to our own mock site

        browser.close()

    # Save to CSV, matching the AIRIX schema
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone. Scraped {len(all_rows)} total fare observations.")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()