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
