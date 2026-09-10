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
