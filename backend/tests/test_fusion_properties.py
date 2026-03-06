"""Property tests for fusion signals."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.signals.fusion_engine import FusionSignalEngine


# Property 55: Fusion Signal Data Combination
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
@given(
    sentiment=st.floats(min_value=-2, max_value=2, allow_nan=False, allow_infinity=False),
    mempool=st.floats(min_value=-2, max_value=2, allow_nan=False, allow_infinity=False),
)
def test_property_fusion_signal_data_combination(sentiment: float, mempool: float) -> None:
    engine = FusionSignalEngine()
    signal = engine.generate_signal({"sentiment": sentiment, "mempool": mempool})
    assert "sentiment" in signal.components
    assert "mempool" in signal.components


# Property 56: Fusion Data Normalization
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
@given(
    values=st.lists(
        st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=100,
    )
)
def test_property_fusion_data_normalization(values: list[float]) -> None:
    engine = FusionSignalEngine()
    normalized = engine.normalize_features({"x": values})["x"]
    if normalized:
        mu = sum(normalized) / len(normalized)
        assert abs(mu) < 1e-6


# Property 57: Fusion Signal Confidence Scoring
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
@given(
    a=st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
    c=st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
)
def test_property_fusion_signal_confidence_scoring(a: float, b: float, c: float) -> None:
    engine = FusionSignalEngine()
    signal = engine.generate_signal({"sentiment": a, "mempool": b, "fees": c})
    assert 0.0 <= signal.confidence <= 1.0


# Property 58: Fusion Signal Backtesting
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
@given(
    signals=st.lists(
        st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=100,
    ),
    returns=st.lists(
        st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=100,
    ),
)
def test_property_fusion_signal_backtesting(signals: list[float], returns: list[float]) -> None:
    engine = FusionSignalEngine()
    perf = engine.backtest_signals(signals, returns)
    assert "total_return" in perf and "hit_rate" in perf
    assert 0.0 <= perf["hit_rate"] <= 1.0
