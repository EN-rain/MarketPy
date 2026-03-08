from __future__ import annotations

from backend.app.openclaw.config import RiskLimitSettings
from backend.app.openclaw.portfolio_optimizer import PortfolioOptimizer
from backend.app.openclaw.risk_advisor import RiskAdvisor


def test_risk_advisor_metrics_and_recommendations() -> None:
    advisor = RiskAdvisor(
        RiskLimitSettings(max_position_size_pct=20.0, max_daily_loss_pct=5.0, max_open_positions=3)
    )
    state = {
        "equity": 10000.0,
        "daily_pnl_pct": -6.0,
        "drawdown_pct": 12.0,
        "positions": [
            {"symbol": "BTCUSDT", "notional": 4000.0},
            {"symbol": "ETHUSDT", "notional": 3500.0},
            {"symbol": "SOLUSDT", "notional": 3000.0},
            {"symbol": "XRPUSDT", "notional": 500.0},
        ],
    }
    metrics = advisor.calculate_metrics(state)
    violations = advisor.check_limits(metrics, open_positions=len(state["positions"]))
    corr = advisor.correlation_analysis({"BTCUSDT": [0.01, 0.02], "ETHUSDT": [0.01, 0.02]})
    recs = advisor.generate_recommendations(metrics, violations, corr)
    assert violations
    assert recs
    assert "Risk summary" in advisor.explain_risk_calculation(metrics)


def test_portfolio_optimizer_metrics_and_what_if() -> None:
    optimizer = PortfolioOptimizer()
    metrics = optimizer.compute_metrics([0.01, -0.005, 0.02, 0.0])
    assert isinstance(metrics.total_return, float)
    assert isinstance(metrics.sharpe_ratio, float)
    analysis = optimizer.analyze_positions(
        [
            {"symbol": "BTCUSDT", "notional": 7000, "pnl_pct": -4.0},
            {"symbol": "ETHUSDT", "notional": 3000, "pnl_pct": 1.0},
        ]
    )
    what_if = optimizer.what_if_analysis(
        [{"symbol": "BTCUSDT", "notional": 7000, "pnl_pct": -4.0}],
        [{"symbol": "BTCUSDT", "notional_delta": -2000}],
    )
    report = optimizer.generate_report(metrics, analysis)
    assert what_if["projected_notional"] > 0
    assert "Portfolio Performance Report" in report
