"""Property tests for slippage tracking."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.execution.slippage_tracker import SlippageTracker


# Property 31: Slippage Calculation Accuracy
@given(
    expected=st.floats(min_value=1.0, max_value=200_000.0, allow_nan=False, allow_infinity=False),
    delta_bps=st.floats(min_value=-200.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    side=st.sampled_from(["BUY", "SELL"]),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_slippage_calculation_accuracy(
    expected: float, delta_bps: float, side: str
) -> None:
    tracker = SlippageTracker()
    executed = expected * (1 + (delta_bps / 10_000.0))
    record = tracker.record_execution(
        symbol="BTCUSDT",
        side=side,
        expected_price=expected,
        executed_price=executed,
        size=1.0,
        timestamp=datetime.now(UTC),
    )
    expected_slippage = delta_bps if side == "BUY" else -delta_bps
    assert record.slippage_bps == pytest.approx(expected_slippage, abs=1e-6)


# Property 32: Slippage Aggregation Grouping
@given(
    small=st.integers(min_value=1, max_value=10),
    medium=st.integers(min_value=1, max_value=10),
    large=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_slippage_aggregation_grouping(small: int, medium: int, large: int) -> None:
    tracker = SlippageTracker()
    now = datetime.now(UTC)
    for _ in range(small):
        tracker.record_execution("BTCUSDT", "BUY", 100.0, 100.1, 0.5, now)
    for _ in range(medium):
        tracker.record_execution("ETHUSDT", "BUY", 100.0, 100.2, 5.0, now)
    for _ in range(large):
        tracker.record_execution("BTCUSDT", "SELL", 100.0, 99.7, 20.0, now)

    analysis = tracker.analyze_patterns()
    assert analysis.count == (small + medium + large)
    assert "small" in analysis.by_size_bucket
    assert "medium" in analysis.by_size_bucket
    assert "large" in analysis.by_size_bucket
    assert "BTCUSDT" in analysis.by_symbol
    assert "ETHUSDT" in analysis.by_symbol
    assert now.hour in analysis.by_hour


# Property 33: Slippage Pattern Identification
@given(scale=st.floats(min_value=5.0, max_value=80.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_slippage_pattern_identification(scale: float) -> None:
    tracker = SlippageTracker()
    now = datetime.now(UTC)
    for i in range(1, 30):
        volatility = i / 30
        spread = i / 1000
        volume = 1_000_000 - (i * 20_000)
        delta_bps = scale * volatility
        expected = 100.0
        executed = expected * (1 + delta_bps / 10_000.0)
        tracker.record_execution(
            symbol="BTCUSDT",
            side="BUY",
            expected_price=expected,
            executed_price=executed,
            size=1 + (i % 5),
            timestamp=now,
            volatility=volatility,
            volume=volume,
            spread=spread,
        )

    analysis = tracker.analyze_patterns()
    assert analysis.condition_correlations["volatility"] > 0.5
    assert -1.0 <= analysis.condition_correlations["volume"] <= 1.0
    assert -1.0 <= analysis.condition_correlations["spread"] <= 1.0
