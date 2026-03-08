"""Portfolio rebalancing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class RebalancePlan:
    trades: dict[str, float]
    turnover: float
    estimated_cost: float


class PortfolioRebalancer:
    def should_rebalance_scheduled(self, last_rebalance: datetime, now: datetime, frequency: str) -> bool:
        delta = now - last_rebalance
        if frequency == "daily":
            return delta >= timedelta(days=1)
        if frequency == "weekly":
            return delta >= timedelta(days=7)
        if frequency == "monthly":
            return delta >= timedelta(days=30)
        raise ValueError(f"Unsupported frequency: {frequency}")

    def should_rebalance_threshold(self, current_weights: dict[str, float], target_weights: dict[str, float], threshold: float = 0.05) -> bool:
        assets = set(current_weights) | set(target_weights)
        return any(abs(current_weights.get(asset, 0.0) - target_weights.get(asset, 0.0)) > threshold for asset in assets)

    def create_rebalance_plan(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        *,
        portfolio_value: float,
        fee_bps: float = 5.0,
    ) -> RebalancePlan:
        assets = set(current_weights) | set(target_weights)
        trades: dict[str, float] = {}
        for asset in assets:
            drift = target_weights.get(asset, 0.0) - current_weights.get(asset, 0.0)
            if abs(drift) < 0.005:
                continue
            trades[asset] = float(drift * portfolio_value)
        turnover = float(sum(abs(value) for value in trades.values()))
        estimated_cost = float(turnover * (fee_bps / 10_000.0))
        return RebalancePlan(trades=trades, turnover=turnover, estimated_cost=estimated_cost)

    def rebalance_now(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        *,
        portfolio_value: float,
        last_rebalance: datetime | None = None,
        frequency: str = "weekly",
        threshold: float = 0.05,
        now: datetime | None = None,
    ) -> RebalancePlan | None:
        current_time = now or datetime.now(UTC)
        if last_rebalance is not None and not self.should_rebalance_scheduled(last_rebalance, current_time, frequency):
            return None
        if not self.should_rebalance_threshold(current_weights, target_weights, threshold):
            return None
        return self.create_rebalance_plan(current_weights, target_weights, portfolio_value=portfolio_value)
