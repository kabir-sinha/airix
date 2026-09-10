"""
backtest_metrics.py
Pure, testable error-metric functions used to validate AIRIX's computed
index against a reference series (ground truth or, eventually, real DGCA
fare data). Kept separate from backtest_index.py the same way
index_math.py is kept separate from calculate_index.py.
"""
import math


def _check_inputs(computed, reference):
    if len(computed) != len(reference):
        raise ValueError("computed and reference must be the same length")
    if len(computed) == 0:
        raise ValueError("computed and reference cannot be empty")


def mean_absolute_error(computed, reference):
    _check_inputs(computed, reference)
    return sum(abs(c - r) for c, r in zip(computed, reference)) / len(computed)


def root_mean_squared_error(computed, reference):
    _check_inputs(computed, reference)
    return math.sqrt(sum((c - r) ** 2 for c, r in zip(computed, reference)) / len(computed))


def mean_absolute_pct_error(computed, reference):
    _check_inputs(computed, reference)
    errors = [abs((c - r) / r) for c, r in zip(computed, reference) if r != 0]
    if not errors:
        raise ValueError("reference values are all zero; cannot compute MAPE")
    return sum(errors) / len(errors) * 100
