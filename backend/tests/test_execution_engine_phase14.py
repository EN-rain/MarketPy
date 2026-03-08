"""Phase 14 execution engine tests."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.execution.order_manager import OrderManager, OrderStatus
from backend.execution.router import SmartOrderRouter


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    fee_a=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    fee_b=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_property_fee_schedule_application(fee_a: float, fee_b: float) -> None:
    router = SmartOrderRouter()
    decision = router.route_order(
        side="BUY",
        order_size=1.0,
        prices_by_exchange={"a": 100.0, "b": 100.0},
        fee_bps_by_exchange={"a": fee_a, "b": fee_b},
        liquidity_depth_by_exchange={"a": 1000.0, "b": 1000.0},
        execution_quality_by_exchange={"a": 0.0, "b": 0.0},
    )
    cheaper = "a" if fee_a <= fee_b else "b"
    assert decision.exchange == cheaper


def test_routing_and_order_manager_checkpoint() -> None:
    router = SmartOrderRouter()
    decision = router.route_order(
        side="BUY",
        order_size=5.0,
        prices_by_exchange={"binance": 100.0, "coinbase": 100.0, "kraken": 100.0},
        fee_bps_by_exchange={"binance": 8.0, "coinbase": 10.0, "kraken": 6.0},
        liquidity_depth_by_exchange={"binance": 5_000.0, "coinbase": 2_000.0, "kraken": 20_000.0},
        execution_quality_by_exchange={"binance": 1.0, "coinbase": 2.0, "kraken": 0.5},
    )
    assert decision.exchange == "kraken"

    manager = OrderManager()
    market = manager.place_order(
        market_id="BTCUSDT",
        side="buy",
        size=1.5,
        order_type="market",
    )
    trailing = manager.place_order(
        market_id="BTCUSDT",
        side="sell",
        size=1.0,
        order_type="trailing_stop",
        trail_percent=0.02,
    )
    manager.update_status(market.order_id, OrderStatus.FILLED)
    manager.modify_order(trailing.order_id, trail_percent=0.03)
    manager.cancel_order(trailing.order_id)

    assert manager.orders[market.order_id].status == OrderStatus.FILLED
    assert manager.orders[trailing.order_id].trail_percent == 0.03
    assert manager.orders[trailing.order_id].status == OrderStatus.CANCELLED
