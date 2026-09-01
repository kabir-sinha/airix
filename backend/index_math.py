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