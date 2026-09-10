"""
index_math.py
Pure, testable functions implementing the Jevons Index math used by AIRIX.
Kept separate from the pipeline scripts (which handle CSVs/database) so the
core statistics can be unit tested in isolation.
"""

from scipy.stats import gmean


def price_relative(observed_fare, base_fare):
    """Ratio of an observed fare to a reference base fare."""
    if base_fare == 0:
        raise ValueError("base_fare cannot be zero")
    return observed_fare / base_fare


def jevons_index(price_relatives):
    """
    Geometric mean of a list of price relatives, scaled to a base of 100.
    This is the Jevons Index formula — using geometric (not arithmetic) mean
    is what makes it treat percentage increases/decreases symmetrically.
    """
    if len(price_relatives) == 0:
        raise ValueError("price_relatives cannot be empty")
    return gmean(price_relatives) * 100


def weighted_airix(route_indices: dict, weights: dict):
    """
    Weighted average of route indices using given weights.
    Weights are expected to sum to ~1.0 (e.g. real DGCA passenger-share weights).
    """
    total = 0.0
    for route, index_value in route_indices.items():
        total += index_value * weights.get(route, 0)
    return total


def route_contributions(route_index_change: dict, weights: dict):
    """
    Each route's contribution (in index points) to an overall AIRIX change.
    Sum of all contributions should equal the total AIRIX change.
    """
    return {route: change * weights.get(route, 0) for route, change in route_index_change.items()}


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