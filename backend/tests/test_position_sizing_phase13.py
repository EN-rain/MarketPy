"""Phase 13 position sizing tests."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.risk.manager import RiskManager
from backend.strategies.position_sizing import PositionSizer


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    edge=st.floats(min_value=0.0001, max_value=0.2, allow_nan=False, allow_infinity=False),
    volatility=st.floats(min_value=0.01, max_value=0.5, allow_nan=False, allow_infinity=False),
    portfolio_value=st.floats(min_value=1_000.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_kelly_sizing_formula(edge: float, volatility: float, portfolio_value: float) -> None:
    sizer = PositionSizer(kelly_fraction=0.1)
    result = sizer.compute_kelly_size(
        edge=edge,
        volatility=volatility,
        portfolio_value=portfolio_value,
        regime="ranging",
        confidence=1.0,
    )
    expected_raw = edge / (volatility**2)
    assert result.raw_kelly_fraction == pytest.approx(expected_raw, rel=1e-6)
    assert result.size >= 0.0


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    edge=st.floats(min_value=0.0001, max_value=0.01, allow_nan=False, allow_infinity=False),
    volatility=st.floats(min_value=0.2, max_value=1.0, allow_nan=False, allow_infinity=False),
    portfolio_value=st.floats(min_value=1_000.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_minimum_position_size(edge: float, volatility: float, portfolio_value: float) -> None:
    sizer = PositionSizer(kelly_fraction=0.01, min_position_fraction=0.01)
    result = sizer.compute_kelly_size(
        edge=edge,
        volatility=volatility,
        portfolio_value=portfolio_value,
        regime="ranging",
        confidence=1.0,
    )
    if result.size > 0:
        assert result.size >= portfolio_value * 0.01


def test_risk_manager_integrates_position_sizer() -> None:
    manager = RiskManager()
    size = manager.adjust_position_size(
        base_position_size=1000.0,
        regime="high_volatility",
        margin_ratio=1.2,
        drawdown=0.05,
        portfolio_value=50_000.0,
        edge=0.02,
        volatility=0.1,
        confidence=0.7,
    )
    assert 0.0 < size < 10_000.0
