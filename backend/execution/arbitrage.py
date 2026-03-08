"""Arbitrage detection and execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.arbitrage.scanner import ArbitrageOpportunity, ArbitrageScanner


@dataclass(frozen=True, slots=True)
class ArbitrageExecutionResult:
    opportunity: ArbitrageOpportunity
    buy_order: dict[str, Any]
    sell_order: dict[str, Any]
    success: bool
    partial_fill: bool


@dataclass(frozen=True, slots=True)
class TriangularOpportunity:
    cycle: tuple[str, str, str]
    gross_edge_pct: float
    net_edge_pct: float


class ArbitrageDetector:
    """Facade over the historical arbitrage scanner with liquidity filtering."""

    def __init__(self, db_path: str = ":memory:", threshold_buffer_pct: float = 0.5) -> None:
        self.scanner = ArbitrageScanner(db_path=db_path, min_profit_threshold_pct=threshold_buffer_pct)
        self.threshold_buffer_pct = float(threshold_buffer_pct)

    def detect_arbitrage(
        self,
        *,
        symbol: str,
        exchange_prices: dict[str, float],
        transaction_costs_pct: float,
        liquidity_by_exchange: dict[str, float] | None = None,
        target_size: float = 1.0,
    ) -> list[ArbitrageOpportunity]:
        exchanges = list(exchange_prices.keys())
        filtered: list[ArbitrageOpportunity] = []
        for buy_exchange in exchanges:
            for sell_exchange in exchanges:
                if buy_exchange == sell_exchange:
                    continue
                buy_price = float(exchange_prices[buy_exchange])
                sell_price = float(exchange_prices[sell_exchange])
                if buy_price <= 0 or sell_price <= 0:
                    continue
                gross_profit_pct = ((sell_price - buy_price) / buy_price) * 100.0
                if gross_profit_pct + 1e-9 < (transaction_costs_pct + self.threshold_buffer_pct):
                    continue
                net_profit_pct = self.scanner.calculate_net_profit(
                    gross_profit_pct=gross_profit_pct,
                    fee_pct=transaction_costs_pct / 2.0,
                    slippage_pct=transaction_costs_pct / 2.0,
                )
                liquidity_ok = True
                if liquidity_by_exchange is not None:
                    liquidity_ok = (
                        liquidity_by_exchange.get(buy_exchange, 0.0) >= target_size
                        and liquidity_by_exchange.get(sell_exchange, 0.0) >= target_size
                    )
                if liquidity_ok and net_profit_pct > 0:
                    filtered.append(
                        ArbitrageOpportunity(
                            symbol=symbol,
                            buy_exchange=buy_exchange,
                            sell_exchange=sell_exchange,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            gross_profit_pct=float(gross_profit_pct),
                            net_profit_pct=float(net_profit_pct),
                            detected_at=datetime.now(UTC),
                        )
                    )
        return filtered

    def triangular_arbitrage(
        self,
        *,
        pair_prices: dict[tuple[str, str], float],
        fee_pct: float = 0.1,
        slippage_pct: float = 0.1,
    ) -> list[TriangularOpportunity]:
        assets = sorted({asset for pair in pair_prices for asset in pair})
        opportunities: list[TriangularOpportunity] = []
        for a in assets:
            for b in assets:
                for c in assets:
                    if len({a, b, c}) < 3:
                        continue
                    if (a, b) not in pair_prices or (b, c) not in pair_prices or (c, a) not in pair_prices:
                        continue
                    gross = pair_prices[(a, b)] * pair_prices[(b, c)] * pair_prices[(c, a)] - 1.0
                    gross_pct = gross * 100.0
                    net_pct = gross_pct - (3.0 * fee_pct) - (3.0 * slippage_pct)
                    if net_pct > 0:
                        opportunities.append(
                            TriangularOpportunity(
                                cycle=(a, b, c),
                                gross_edge_pct=float(gross_pct),
                                net_edge_pct=float(net_pct),
                            )
                        )
        return opportunities


class ArbitrageExecutor:
    """Executes two-leg arbitrage opportunities with simple partial-fill handling."""

    def __init__(self) -> None:
        self.execution_count = 0
        self.success_count = 0

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        *,
        buy_adapter,
        sell_adapter,
        size: float,
    ) -> ArbitrageExecutionResult:
        buy_order = await buy_adapter.place_order(
            {"symbol": opportunity.symbol, "side": "buy", "size": size, "type": "market"}
        )
        sell_order = await sell_adapter.place_order(
            {"symbol": opportunity.symbol, "side": "sell", "size": size, "type": "market"}
        )
        self.execution_count += 1
        buy_filled = float(buy_order.get("filled_size", size)) >= size
        sell_filled = float(sell_order.get("filled_size", size)) >= size
        success = buy_filled and sell_filled
        if success:
            self.success_count += 1
        return ArbitrageExecutionResult(
            opportunity=opportunity,
            buy_order=buy_order,
            sell_order=sell_order,
            success=success,
            partial_fill=not success,
        )

    @property
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return float(self.success_count / self.execution_count)
