"""
test_index_math.py
Unit tests proving the Jevons Index math in index_math.py is correct.
Run with: pytest
"""

import pytest
from index_math import price_relative, jevons_index, weighted_airix, route_contributions


# ---- price_relative ----

def test_price_relative_basic():
    # Fare doubled from base -> price relative should be 2.0
    assert price_relative(200, 100) == 2.0

def test_price_relative_no_change():
    # Fare identical to base -> price relative should be exactly 1.0
    assert price_relative(150, 150) == 1.0

def test_price_relative_zero_base_raises():
    # A zero base fare is undefined (division by zero) -> should raise, not crash silently
    with pytest.raises(ValueError):
        price_relative(100, 0)


# ---- jevons_index ----

def test_jevons_index_no_change():
    # If every price relative is exactly 1.0 (no price change anywhere),
    # the index must be exactly 100 (the base level).
    result = jevons_index([1.0, 1.0, 1.0, 1.0])
    assert result == pytest.approx(100.0)

def test_jevons_index_uniform_increase():
    # If every fare rose by exactly 10%, the index should be exactly 110.
    result = jevons_index([1.1, 1.1, 1.1])
    assert result == pytest.approx(110.0)

def test_jevons_index_uses_geometric_not_arithmetic_mean():
    # This is the key property that makes Jevons the right choice:
    # geometric mean of [0.5, 2.0] is 1.0 (100 - unchanged on average),
    # but arithmetic mean would incorrectly give 1.25 (125).
    result = jevons_index([0.5, 2.0])
    assert result == pytest.approx(100.0)

def test_jevons_index_empty_list_raises():
    with pytest.raises(ValueError):
        jevons_index([])


# ---- weighted_airix ----

def test_weighted_airix_equal_weights():
    indices = {"A": 100, "B": 200}
    weights = {"A": 0.5, "B": 0.5}
    # Simple average when weights are equal: (100*0.5 + 200*0.5) = 150
    assert weighted_airix(indices, weights) == pytest.approx(150.0)

def test_weighted_airix_heavier_route_dominates():
    indices = {"A": 100, "B": 200}
    weights = {"A": 0.9, "B": 0.1}
    # Route A is weighted much more heavily, so result should be much closer to 100 than 150
    result = weighted_airix(indices, weights)
    assert result == pytest.approx(110.0)


# ---- route_contributions ----

def test_route_contributions_sum_matches_total_change():
    changes = {"A": 10, "B": -4}
    weights = {"A": 0.3, "B": 0.7}
    contributions = route_contributions(changes, weights)
    # A's contribution: 10 * 0.3 = 3.0
    # B's contribution: -4 * 0.7 = -2.8
    assert contributions["A"] == pytest.approx(3.0)
    assert contributions["B"] == pytest.approx(-2.8)
    # Contributions should sum to the weighted total change
    assert sum(contributions.values()) == pytest.approx(0.2)