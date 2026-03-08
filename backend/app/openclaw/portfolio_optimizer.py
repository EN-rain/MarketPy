"""Portfolio analytics and optimization recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any

from .logging import StructuredLogger


@dataclass(slots=True)
class PortfolioMetrics:
    total_return: float
    sharpe_ratio: float
    volatility: float
    max_drawdown: float


class PortfolioOptimizer:
    """Computes portfolio metrics and recommends rebalancing actions."""

    def __init__(self, logger: StructuredLogger | None = None):
        self._logger = logger or StructuredLogger("openclaw.portfolio_optimizer")

    def compute_metrics(
        self, returns: list[float], risk_free_rate: float = 0.0
    ) -> PortfolioMetrics:
        if not returns:
            return PortfolioMetrics(0.0, 0.0, 0.0, 0.0)

        cumulative = 1.0
        max_cumulative = 1.0
        max_drawdown = 0.0
        for period_return in returns:
            cumulative *= 1.0 + period_return
            max_cumulative = max(max_cumulative, cumulative)
            drawdown = (max_cumulative - cumulative) / max_cumulative
            max_drawdown = max(max_drawdown, drawdown)

        avg = mean(returns)
        vol = pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = 0.0 if vol == 0 else ((avg - risk_free_rate) / vol) * sqrt(252)
        total_return = cumulative - 1.0
        return PortfolioMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe,
            volatility=vol * sqrt(252),
            max_drawdown=max_drawdown,
        )

    def compare_to_benchmark(
        self,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
    ) -> dict[str, Any]:
        portfolio_metrics = self.compute_metrics(portfolio_returns)
        benchmark_metrics = self.compute_metrics(benchmark_returns)
        return {
            "portfolio": portfolio_metrics,
            "benchmark": benchmark_metrics,
            "alpha": portfolio_metrics.total_return - benchmark_metrics.total_return,
            "sharpe_delta": portfolio_metrics.sharpe_ratio - benchmark_metrics.sharpe_ratio,
        }

    def analyze_positions(self, positions: list[dict[str, Any]]) -> dict[str, Any]:
        underperformers = []
        concentration = {}
        total_notional = sum(abs(float(pos.get("notional", 0.0))) for pos in positions) or 1.0
        for position in positions:
            symbol = str(position.get("symbol", "UNKNOWN"))
            pnl_pct = float(position.get("pnl_pct", 0.0))
            notional = abs(float(position.get("notional", 0.0)))
            concentration[symbol] = (notional / total_notional) * 100.0
            if pnl_pct < -3.0:
                underperformers.append(symbol)

        recommendations = []
        for symbol, pct in concentration.items():
            if pct > 30:
                recommendations.append(
                    f"Reduce concentration in {symbol} ({pct:.1f}% of portfolio)."
                )
        for symbol in underperformers:
            recommendations.append(
                f"Review stop-loss / thesis for underperforming position {symbol}."
            )
        if not recommendations:
            recommendations.append("No major concentration or underperformance issues detected.")

        return {
            "concentration_pct": concentration,
            "underperformers": underperformers,
            "recommendations": recommendations,
        }

    def what_if_analysis(
        self,
        positions: list[dict[str, Any]],
        proposed_changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current_notional = sum(abs(float(pos.get("notional", 0.0))) for pos in positions)
        adjusted_positions = [dict(pos) for pos in positions]

        for change in proposed_changes:
            symbol = str(change.get("symbol", ""))
            delta = float(change.get("notional_delta", 0.0))
            for position in adjusted_positions:
                if str(position.get("symbol")) == symbol:
                    position["notional"] = float(position.get("notional", 0.0)) + delta
                    break
            else:
                adjusted_positions.append({"symbol": symbol, "notional": delta, "pnl_pct": 0.0})

        projected_notional = sum(abs(float(pos.get("notional", 0.0))) for pos in adjusted_positions)
        leverage_impact = (
            0.0 if current_notional == 0 else (projected_notional / current_notional) - 1.0
        )
        return {
            "current_notional": current_notional,
            "projected_notional": projected_notional,
            "leverage_impact_pct": leverage_impact * 100.0,
            "projected_positions": adjusted_positions,
        }

    def generate_report(
        self,
        metrics: PortfolioMetrics,
        position_analysis: dict[str, Any],
        benchmark_comparison: dict[str, Any] | None = None,
    ) -> str:
        lines = [
            "Portfolio Performance Report",
            f"- Total Return: {metrics.total_return:.2%}",
            f"- Sharpe Ratio: {metrics.sharpe_ratio:.2f}",
            f"- Volatility (ann.): {metrics.volatility:.2%}",
            f"- Max Drawdown: {metrics.max_drawdown:.2%}",
            f"- Recommendations: {' | '.join(position_analysis.get('recommendations', []))}",
        ]
        if benchmark_comparison:
            lines.append(f"- Alpha vs Benchmark: {benchmark_comparison['alpha']:.2%}")
            lines.append(f"- Sharpe Delta vs Benchmark: {benchmark_comparison['sharpe_delta']:.2f}")
        return "\n".join(lines)
