"""Smart order routing across exchanges."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteDecision:
    exchange: str
    expected_cost_bps: float
    details: dict[str, float]


class SmartOrderRouter:
    """Chooses the exchange with the lowest expected execution cost."""

    def route_order(
        self,
        *,
        side: str,
        order_size: float,
        prices_by_exchange: dict[str, float],
        fee_bps_by_exchange: dict[str, float],
        liquidity_depth_by_exchange: dict[str, float],
        execution_quality_by_exchange: dict[str, float],
    ) -> RouteDecision:
        candidates: dict[str, float] = {}
        for exchange, price in prices_by_exchange.items():
            fee_bps = float(fee_bps_by_exchange.get(exchange, 0.0))
            depth = max(float(liquidity_depth_by_exchange.get(exchange, 1.0)), 1e-6)
            quality_penalty = max(0.0, float(execution_quality_by_exchange.get(exchange, 0.0)))
            market_impact_bps = (order_size / depth) * 10_000
            price_component = price * 0.0 if side.upper() in {"BUY", "SELL"} else 0.0
            candidates[exchange] = fee_bps + market_impact_bps + quality_penalty + price_component

        best_exchange = min(candidates, key=candidates.get)
        return RouteDecision(
            exchange=best_exchange,
            expected_cost_bps=float(candidates[best_exchange]),
            details={exchange: float(cost) for exchange, cost in candidates.items()},
        )
