"""Transaction cost analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True, slots=True)
class TCAResult:
    spread_cost: float
    market_impact: float
    slippage_cost: float
    fees: float
    opportunity_cost: float
    implementation_shortfall: float
    arrival_price_slippage: float
    vwap_comparison: float
    twap_comparison: float
    fill_rate: float


class TCAAnalyzer:
    """Computes transaction-cost components and benchmarks."""

    @staticmethod
    def market_impact(order_size: float, average_volume: float, k: float = 0.1) -> float:
        if average_volume <= 0 or order_size <= 0:
            return 0.0
        return float(k * sqrt(order_size / average_volume))

    def compute_tca(
        self,
        *,
        arrival_price: float,
        execution_price: float,
        expected_price: float,
        order_size: float,
        spread: float,
        fee_rate: float,
        average_volume: float,
        vwap_price: float,
        twap_price: float,
        filled_size: float | None = None,
    ) -> TCAResult:
        filled = float(filled_size if filled_size is not None else order_size)
        fill_rate = 0.0 if order_size <= 0 else min(1.0, filled / order_size)
        spread_cost = spread / max(arrival_price, 1e-9)
        impact = self.market_impact(order_size, average_volume)
        slippage_cost = (execution_price - expected_price) / max(expected_price, 1e-9)
        fees = fee_rate
        opportunity_cost = max(0.0, (order_size - filled) / max(order_size, 1e-9))
        implementation_shortfall = (execution_price - arrival_price) / max(arrival_price, 1e-9)
        arrival_slippage = (execution_price - arrival_price) / max(arrival_price, 1e-9)
        vwap_comparison = (execution_price - vwap_price) / max(vwap_price, 1e-9)
        twap_comparison = (execution_price - twap_price) / max(twap_price, 1e-9)
        return TCAResult(
            spread_cost=float(spread_cost),
            market_impact=float(impact),
            slippage_cost=float(slippage_cost),
            fees=float(fees),
            opportunity_cost=float(opportunity_cost),
            implementation_shortfall=float(implementation_shortfall),
            arrival_price_slippage=float(arrival_slippage),
            vwap_comparison=float(vwap_comparison),
            twap_comparison=float(twap_comparison),
            fill_rate=float(fill_rate),
        )
