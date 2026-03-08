"""Phase 21 portfolio management tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from backend.portfolio.attribution import PerformanceAttributor
from backend.portfolio.optimizer import PortfolioOptimizer
from backend.portfolio.rebalancer import PortfolioRebalancer


def _returns_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "BTC": [0.01, -0.005, 0.008, 0.012, -0.002],
            "ETH": [0.015, -0.01, 0.006, 0.02, -0.003],
            "SOL": [0.02, -0.015, 0.01, 0.03, -0.005],
        }
    )


def test_portfolio_optimizer_methods_generate_normalized_weights() -> None:
    optimizer = PortfolioOptimizer()
    returns = _returns_frame()

    mv = optimizer.mean_variance(returns).weights
    rp = optimizer.risk_parity(returns).weights
    bl = optimizer.black_litterman(returns, {"BTC": 0.02, "ETH": 0.01, "SOL": 0.015}).weights

    for weights in (mv, rp, bl):
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        assert all(value >= 0.0 for value in weights.values())


def test_rebalancer_and_attribution_reports() -> None:
    rebalancer = PortfolioRebalancer()
    now = datetime(2026, 3, 7, tzinfo=UTC)
    last = now - timedelta(days=8)

    assert rebalancer.should_rebalance_scheduled(last, now, "weekly") is True
    plan = rebalancer.rebalance_now(
        {"BTC": 0.5, "ETH": 0.3, "SOL": 0.2},
        {"BTC": 0.4, "ETH": 0.4, "SOL": 0.2},
        portfolio_value=100_000,
        last_rebalance=last,
        frequency="weekly",
    )
    assert plan is not None
    assert plan.turnover > 0.0
    assert plan.estimated_cost > 0.0

    attribution_frame = pd.DataFrame(
        {
            "timestamp": [now - timedelta(days=2), now - timedelta(days=1), now],
            "strategy": ["trend", "mean_reversion", "trend"],
            "regime": ["bull", "sideways", "bull"],
            "return": [0.01, -0.002, 0.005],
        }
    )
    report = PerformanceAttributor().generate_report(attribution_frame)
    assert abs(report.total_return - 0.013) < 1e-9
    assert "trend" in report.by_strategy
    assert "bull" in report.by_regime
    assert report.by_period
