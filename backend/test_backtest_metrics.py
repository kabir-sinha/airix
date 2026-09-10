import pytest
from backtest_metrics import mean_absolute_error, root_mean_squared_error, mean_absolute_pct_error


def test_mean_absolute_error_perfect_match_is_zero():
    assert mean_absolute_error([100, 101, 102], [100, 101, 102]) == 0

def test_mean_absolute_error_basic():
    assert mean_absolute_error([100, 110], [90, 120]) == pytest.approx(10.0)

def test_root_mean_squared_error_basic():
    # errors are 3 and 4 -> sqrt((9+16)/2) = sqrt(12.5)
    result = root_mean_squared_error([100, 100], [103, 96])
    assert result == pytest.approx(12.5 ** 0.5)

def test_mean_absolute_pct_error_basic():
    # |110-100|/100 = 0.10 -> 10%
    assert mean_absolute_pct_error([110], [100]) == pytest.approx(10.0)

def test_metrics_reject_mismatched_lengths():
    with pytest.raises(ValueError):
        mean_absolute_error([100], [100, 101])
    with pytest.raises(ValueError):
        root_mean_squared_error([100], [100, 101])
    with pytest.raises(ValueError):
        mean_absolute_pct_error([100], [100, 101])

def test_metrics_reject_empty_input():
    with pytest.raises(ValueError):
        mean_absolute_error([], [])
