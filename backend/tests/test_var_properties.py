"""Property tests for VaR calculator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.risk.var_calculator import VaRCalculator, VaRMethod

RETURN_STRATEGY = st.lists(
    st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
    min_size=20,
    max_size=250,
)


# Property 27: VaR Calculation Range
@given(
    portfolio_value=st.floats(
        min_value=1_000.0, max_value=5_000_000.0, allow_nan=False, allow_infinity=False
    ),
    returns=RETURN_STRATEGY,
    confidence=st.sampled_from([0.95, 0.99]),
    method=st.sampled_from([VaRMethod.HISTORICAL, VaRMethod.PARAMETRIC, VaRMethod.MONTE_CARLO]),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_var_calculation_range(
    portfolio_value: float, returns: list[float], confidence: float, method: VaRMethod
) -> None:
    calc = VaRCalculator()
    result = calc.calculate_var(
        portfolio_value=portfolio_value,
        returns=returns,
        confidence_level=confidence,
        method=method,
        simulations=1000,
        seed=123,
    )
    assert result.var_percent >= 0.0
    assert result.var_percent <= 1.0
    assert result.var_dollar >= 0.0
    assert result.var_dollar <= portfolio_value


# Property 13: Periodic Update Interval Compliance
@given(interval_seconds=st.integers(min_value=1, max_value=1800))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_periodic_update_interval_compliance(interval_seconds: int) -> None:
    calc = VaRCalculator(update_interval_seconds=interval_seconds)
    now = datetime.now(UTC)
    assert calc.should_recalculate(now, None) is True
    assert calc.should_recalculate(now, now - timedelta(seconds=interval_seconds - 1)) is False
    assert calc.should_recalculate(now, now - timedelta(seconds=interval_seconds)) is True


# Property 14: Alert Threshold Triggering
@given(
    threshold=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    var_percent=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_alert_threshold_triggering(threshold: float, var_percent: float) -> None:
    calc = VaRCalculator()
    result = calc.calculate_var(
        portfolio_value=100_000.0,
        returns=[-var_percent, 0.001, 0.002, -0.003, 0.004] * 8,
        confidence_level=0.95,
        method=VaRMethod.HISTORICAL,
    )
    expected = result.var_percent >= threshold
    assert calc.check_var_threshold(result, threshold) is expected
