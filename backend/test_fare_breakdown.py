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
