"""Phase 18 arbitrage tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.arbitrage.scanner import ArbitrageOpportunity
from backend.execution.arbitrage import ArbitrageDetector, ArbitrageExecutor


@pytest.mark.property_test
@settings(max_examples=60)
@given(
    transaction_costs=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    extra_edge=st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False),
)
def test_property_arbitrage_detection_threshold(transaction_costs: float, extra_edge: float) -> None:
    detector = ArbitrageDetector()
    buy_price = 100.0
    gross_pct = transaction_costs + extra_edge + 0.2
    sell_price = buy_price * (1.0 + gross_pct / 100.0)
    opps = detector.detect_arbitrage(
        symbol="BTCUSDT",
        exchange_prices={"binance": buy_price, "okx": sell_price},
        transaction_costs_pct=transaction_costs,
        liquidity_by_exchange={"binance": 10.0, "okx": 10.0},
        target_size=1.0,
    )
    assert opps


class _Adapter:
    async def place_order(self, order):
        return {"status": "filled", "filled_size": order["size"], "order": order}


@pytest.mark.asyncio
async def test_arbitrage_execution_and_triangular_detection() -> None:
    detector = ArbitrageDetector()
    opp = ArbitrageOpportunity(
        symbol="BTCUSDT",
        buy_exchange="binance",
        sell_exchange="okx",
        buy_price=100.0,
        sell_price=101.5,
        gross_profit_pct=1.5,
        net_profit_pct=1.3,
        detected_at=datetime.now(UTC),
    )
    executor = ArbitrageExecutor()
    result = await executor.execute_arbitrage(opp, buy_adapter=_Adapter(), sell_adapter=_Adapter(), size=2.0)
    triangles = detector.triangular_arbitrage(
        pair_prices={("BTC", "USD"): 100000.0, ("USD", "ETH"): 0.0004, ("ETH", "BTC"): 0.03},
        fee_pct=0.01,
        slippage_pct=0.01,
    )

    assert result.success is True
    assert executor.success_rate == pytest.approx(1.0)
    assert triangles
