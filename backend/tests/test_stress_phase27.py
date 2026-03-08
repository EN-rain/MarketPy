"""Phase 27 stress tests for extreme scenarios."""

from __future__ import annotations

from backend.risk.circuit_breakers import CircuitBreakerManager
from backend.risk.manager import RiskManager


def test_stress_flash_crash_and_liquidity_crisis() -> None:
    breakers = CircuitBreakerManager()
    status = breakers.evaluate(
        price_move_pct_1m=-0.20,
        liquidation_volume=10_000_000.0,
        average_liquidation_volume=1_000_000.0,
        outage_seconds=0.0,
        drawdown=0.05,
    )
    assert status.triggered is True


def test_stress_exchange_outage_and_high_volatility() -> None:
    breakers = CircuitBreakerManager()
    status = breakers.evaluate(
        price_move_pct_1m=-0.02,
        liquidation_volume=500_000.0,
        average_liquidation_volume=600_000.0,
        outage_seconds=180.0,
        drawdown=0.12,
    )
    assert status.triggered is True


def test_stress_data_quality_and_risk_response() -> None:
    manager = RiskManager()
    decision = manager.evaluate_all(
        portfolio_value=100_000.0,
        returns=[0.0] * 100,
        returns_by_asset={"BTC": [0.0] * 100, "ETH": [0.0] * 100},
        position_values={"BTC": 50_000.0, "ETH": 50_000.0},
        maintenance_margin_ratio=0.95,
        current_equity=80_000.0,
        regime="crisis",
        stablecoin_price=0.92,
        contract_metadata={"type": "perpetual"},
        exchange_metadata={"name": "stress-exchange"},
        current_price=100.0,
        liquidation_price=98.0,
        price_move_pct_1m=-0.05,
        liquidation_volume=2_000_000.0,
        average_liquidation_volume=500_000.0,
        outage_seconds=120.0,
        base_position_size=1000.0,
    )
    assert decision.adjusted_position_size == 0.0
