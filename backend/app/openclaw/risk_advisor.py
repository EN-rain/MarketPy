"""Continuous risk monitoring and recommendation engine."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any

from .config import RiskLimitSettings
from .discord_bridge import DiscordBridge
from .logging import StructuredLogger


@dataclass(slots=True)
class RiskMetrics:
    total_notional: float
    largest_position_pct: float
    daily_pnl_pct: float
    drawdown_pct: float


class RiskAdvisor:
    """Monitors portfolio risk and emits proactive alerts."""

    def __init__(
        self,
        risk_limits: RiskLimitSettings,
        *,
        discord_bridge: DiscordBridge | None = None,
        monitor_interval_seconds: int = 60,
        logger: StructuredLogger | None = None,
    ):
        self._limits = risk_limits
        self._discord = discord_bridge
        self._interval = monitor_interval_seconds
        self._logger = logger or StructuredLogger("openclaw.risk_advisor")
        self._task: asyncio.Task[None] | None = None
        self._portfolio_provider = None

    def set_portfolio_provider(self, provider) -> None:
        """Provider should expose async `get_portfolio_state() -> dict`."""
        self._portfolio_provider = provider

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def calculate_metrics(self, portfolio_state: dict[str, Any]) -> RiskMetrics:
        positions = portfolio_state.get("positions", [])
        equity = float(portfolio_state.get("equity", 1.0) or 1.0)
        total_notional = sum(abs(float(item.get("notional", 0.0))) for item in positions)
        largest = max((abs(float(item.get("notional", 0.0))) for item in positions), default=0.0)
        largest_pct = (largest / equity) * 100.0 if equity else 0.0
        daily_pnl_pct = float(portfolio_state.get("daily_pnl_pct", 0.0))
        drawdown_pct = float(portfolio_state.get("drawdown_pct", 0.0))
        return RiskMetrics(
            total_notional=total_notional,
            largest_position_pct=largest_pct,
            daily_pnl_pct=daily_pnl_pct,
            drawdown_pct=drawdown_pct,
        )

    def check_limits(self, metrics: RiskMetrics, open_positions: int) -> list[str]:
        violations: list[str] = []
        if metrics.largest_position_pct > self._limits.max_position_size_pct:
            violations.append("Largest position exceeds max position size")
        if metrics.daily_pnl_pct <= -abs(self._limits.max_daily_loss_pct):
            violations.append("Daily loss threshold exceeded")
        if open_positions > self._limits.max_open_positions:
            violations.append("Max open positions exceeded")
        return violations

    def correlation_analysis(self, returns_by_symbol: dict[str, list[float]]) -> dict[str, float]:
        symbols = sorted(returns_by_symbol)
        correlations: dict[str, float] = {}
        for idx, left in enumerate(symbols):
            for right in symbols[idx + 1 :]:
                correlations[f"{left}:{right}"] = self._corr(
                    returns_by_symbol.get(left, []),
                    returns_by_symbol.get(right, []),
                )
        return correlations

    @staticmethod
    def _corr(xs: list[float], ys: list[float]) -> float:
        n = min(len(xs), len(ys))
        if n < 2:
            return 0.0
        a = xs[-n:]
        b = ys[-n:]
        avg_a = mean(a)
        avg_b = mean(b)
        std_a = pstdev(a)
        std_b = pstdev(b)
        if std_a == 0 or std_b == 0:
            return 0.0
        cov = sum((x - avg_a) * (y - avg_b) for x, y in zip(a, b, strict=False)) / n
        return max(-1.0, min(1.0, cov / (std_a * std_b)))

    def generate_recommendations(
        self,
        metrics: RiskMetrics,
        violations: list[str],
        correlations: dict[str, float],
    ) -> list[str]:
        recommendations: list[str] = []
        if "Largest position exceeds max position size" in violations:
            recommendations.append("Reduce single-position exposure to restore sizing limits.")
        if "Daily loss threshold exceeded" in violations:
            recommendations.append("Pause new trades and reduce risk until drawdown stabilizes.")
        if any(abs(value) > 0.8 for value in correlations.values()):
            recommendations.append("Portfolio is highly correlated; diversify symbols or hedge.")
        if metrics.drawdown_pct > 10:
            recommendations.append("Decrease leverage and use tighter stop-loss to cap drawdown.")
        if not recommendations:
            recommendations.append("Current risk profile is within configured limits.")
        return recommendations

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                if self._portfolio_provider is None:
                    continue
                state = await self._portfolio_provider.get_portfolio_state()
                metrics = self.calculate_metrics(state)
                violations = self.check_limits(
                    metrics, open_positions=len(state.get("positions", []))
                )
                if violations and self._discord:
                    channel_id = state.get("risk_channel_id")
                    if channel_id:
                        content = (
                            "⚠️ Risk alert: "
                            + "; ".join(violations)
                            + f" | daily_pnl_pct={metrics.daily_pnl_pct}"
                        )
                        await self._discord.send_message(channel_id, content)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error("Risk monitoring loop failed", {"error": str(exc)})

    def explain_risk_calculation(self, metrics: RiskMetrics) -> str:
        volatility_proxy = abs(metrics.drawdown_pct) / max(
            1.0, sqrt(max(metrics.total_notional, 1.0))
        )
        pnl_segment = (
            f"{metrics.largest_position_pct:.2f}% of equity, "
            f"daily PnL {metrics.daily_pnl_pct:.2f}%, "
        )
        return (
            "Risk summary: largest position "
            f"{pnl_segment}"
            f"drawdown {metrics.drawdown_pct:.2f}%, volatility proxy {volatility_proxy:.3f}."
        )
