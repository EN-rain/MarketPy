"""Additional Phase 12 risk control tests."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.risk.correlation_calculator import CorrelationCalculator
from backend.risk.circuit_breakers import CircuitBreakerManager
from backend.risk.crypto_risk import CryptoRiskManager
from backend.risk.drawdown import DrawdownController
from backend.risk.manager import RiskManager
from backend.risk.position_risk import PositionRiskManager


def _correlation_matrix():
    return CorrelationCalculator().calculate_correlations(
        {"BTC": [0.01] * 30, "ETH": [0.01] * 30, "SOL": [-0.01] * 30}
    )


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    portfolio_value=st.floats(min_value=1_000.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    single_position_pct=st.floats(min_value=0.0, max_value=0.6, allow_nan=False, allow_infinity=False),
)
def test_property_single_position_size_limit(portfolio_value: float, single_position_pct: float) -> None:
    manager = PositionRiskManager()
    position_value = portfolio_value * single_position_pct
    result = manager.check_position_limits(
        position_values={"BTC": position_value, "ETH": portfolio_value * 0.05},
        portfolio_value=portfolio_value,
        correlation_matrix=_correlation_matrix(),
        maintenance_margin_ratio=2.0,
    )
    if single_position_pct > 0.20:
        assert "single_position_limit_exceeded" in result.reasons
    else:
        assert "single_position_limit_exceeded" not in result.reasons


@pytest.mark.property_test
@settings(max_examples=25)
@given(drawdown=st.floats(min_value=0.10, max_value=0.199, allow_nan=False, allow_infinity=False))
def test_property_drawdown_position_reduction(drawdown: float) -> None:
    controller = DrawdownController()
    controller.peak_equity = 100_000.0
    equity = 100_000.0 * (1.0 - drawdown)
    status = controller.check_drawdown_limits(
        current_equity=equity,
        position_values={"BTC": 10_000.0, "ETH": 8_000.0},
    )
    assert status.reduce_positions is True
    assert status.halt_trading is False
    assert status.adjusted_positions["BTC"] == pytest.approx(5_000.0)


@pytest.mark.property_test
@settings(max_examples=25)
@given(drawdown=st.floats(min_value=0.20, max_value=0.6, allow_nan=False, allow_infinity=False))
def test_property_drawdown_trading_halt(drawdown: float) -> None:
    controller = DrawdownController()
    controller.peak_equity = 100_000.0
    equity = 100_000.0 * (1.0 - drawdown)
    status = controller.check_drawdown_limits(
        current_equity=equity,
        position_values={"BTC": 10_000.0, "ETH": 8_000.0},
    )
    assert status.halt_trading is True
    assert all(value == 0.0 for value in status.adjusted_positions.values())


def test_crypto_risk_circuit_breakers_and_manager_checkpoint() -> None:
    crypto = CryptoRiskManager()
    snapshot = crypto.snapshot(
        stablecoin_price=0.94,
        contract_metadata={"audit_count": 0, "critical_issues": 2, "has_admin_keys": True},
        exchange_metadata={"uptime": 0.95, "proof_of_reserves": False, "regulated": False},
        current_price=100.0,
        liquidation_price=85.0,
        margin_ratio=1.2,
    )
    assert snapshot.stablecoin_depeg is True
    assert snapshot.margin_ratio_reduction < 1.0

    breakers = CircuitBreakerManager().evaluate(
        price_move_pct_1m=-0.15,
        liquidation_volume=2000.0,
        average_liquidation_volume=100.0,
        outage_seconds=20.0,
        drawdown=0.25,
    )
    assert breakers.triggered is True

    manager = RiskManager()
    decision = manager.evaluate_all(
        portfolio_value=50_000.0,
        returns=[0.01, -0.02, 0.015, -0.01] * 10,
        returns_by_asset={
            "BTC": [0.01, -0.02, 0.015, -0.01] * 10,
            "ETH": [0.01, -0.018, 0.014, -0.009] * 10,
        },
        position_values={"BTC": 8_000.0, "ETH": 4_000.0},
        maintenance_margin_ratio=1.2,
        current_equity=40_000.0,
        regime="crisis",
        stablecoin_price=0.96,
        contract_metadata={"audit_count": 1, "critical_issues": 1, "has_admin_keys": True},
        exchange_metadata={"uptime": 0.99, "proof_of_reserves": True, "regulated": True},
        current_price=100.0,
        liquidation_price=90.0,
        price_move_pct_1m=-0.12,
        liquidation_volume=1500.0,
        average_liquidation_volume=100.0,
        outage_seconds=0.0,
        base_position_size=1000.0,
    )
    assert decision.adjusted_position_size < 1000.0
    assert decision.circuit_breakers.flash_crash is True


@pytest.mark.property_test
@settings(max_examples=25)
@given(margin_ratio=st.floats(min_value=0.5, max_value=2.5, allow_nan=False, allow_infinity=False))
def test_property_margin_ratio_position_reduction(margin_ratio: float) -> None:
    manager = CryptoRiskManager()
    reduction = manager.reduce_for_margin_ratio(margin_ratio)
    assert 0.0 <= reduction <= 1.0
    if margin_ratio < 1.5:
        assert reduction < 1.0
    else:
        assert reduction == 1.0
