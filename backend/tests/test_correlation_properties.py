"""Property tests for correlation calculations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.risk.correlation_calculator import CorrelationCalculator, CorrelationMatrix

RETURNS = st.lists(
    st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False),
    min_size=10,
    max_size=120,
)


# Property 17: Correlation Calculation Correctness
@given(
    btc=RETURNS,
    eth=RETURNS,
    sol=RETURNS,
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_correlation_calculation_correctness(
    btc: list[float], eth: list[float], sol: list[float]
) -> None:
    calc = CorrelationCalculator(window_days=30)
    result = calc.calculate_correlations({"BTC": btc, "ETH": eth, "SOL": sol})

    assert len(result.assets) == len(result.matrix)
    for row in result.matrix:
        for value in row:
            assert -1.0 <= value <= 1.0


# Property 30: Correlation Shift Detection
@given(
    old=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.2001, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_correlation_shift_detection(old: float, delta: float) -> None:
    calc = CorrelationCalculator(window_days=30)
    up = max(-1.0, min(1.0, old + delta))
    down = max(-1.0, min(1.0, old - delta))
    new = up if abs(up - old) > 0.2 else down
    if abs(new - old) <= 0.2:
        new = 1.0 if old < 0 else -1.0

    prev = CorrelationMatrix(
        assets=["BTC", "ETH"],
        matrix=[
            [1.0, old],
            [old, 1.0],
        ],
        window_days=30,
        timestamp=datetime.now(UTC) - timedelta(days=1),
    )
    curr = CorrelationMatrix(
        assets=["BTC", "ETH"],
        matrix=[
            [1.0, new],
            [new, 1.0],
        ],
        window_days=30,
        timestamp=datetime.now(UTC),
    )
    shifts = calc.detect_correlation_shifts(prev, curr, threshold=0.2)
    assert shifts
    assert shifts[0][0] == "BTC"
    assert shifts[0][1] == "ETH"
