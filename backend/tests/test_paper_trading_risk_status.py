"""Tests for paper trading risk status reporting."""

from __future__ import annotations

from backend.paper_trading.engine import PaperTradingEngine, RiskLimits


def test_risk_status_defaults() -> None:
    engine = PaperTradingEngine(
        initial_cash=10_000.0,
        risk_limits=RiskLimits(
            max_position_per_market=100.0,
            max_total_exposure=1_000.0,
            max_daily_loss=200.0,
        ),
    )
    status = engine.get_risk_status()
    assert status["limits"]["max_position_per_market"] == 100.0
    assert status["metrics"]["current_exposure"] == 0.0
    assert status["status"]["position_limit_ok"] is True
