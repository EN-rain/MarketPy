"""Phase 24 advanced order and strategy tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.models.market import Candle, MarketInfo, MarketState, OrderBookSnapshotPydantic, Side
from backend.app.models.portfolio import Portfolio
from backend.execution.advanced_orders import AdvancedOrderEngine
from backend.execution.order_manager import OrderManager, OrderStatus
from backend.strategies.pattern_strategy import PatternStrategy
from backend.strategies.regime_strategy import RegimeAdaptiveStrategy


def _sample_market_state(symbol: str = "BTCUSDT", *, bars: int = 40, drift: float = 0.3) -> MarketState:
    now = datetime.now(UTC)
    candles: list[Candle] = []
    price = 100.0
    for index in range(bars):
        ts = now - timedelta(minutes=(bars - index))
        close = price + (drift * index)
        candles.append(
            Candle(
                timestamp=ts,
                open=close - 0.1,
                high=close + 0.4,
                low=close - 0.4,
                close=close,
                mid=close,
                bid=close - 0.05,
                ask=close + 0.05,
                spread=0.1,
                volume=200.0 + index,
                trade_count=10,
            )
        )
    state = MarketState(
        info=MarketInfo(
            condition_id=symbol,
            question=f"{symbol} trend",
            token_id_yes=symbol,
            end_date=now + timedelta(days=30),
        ),
        orderbook=OrderBookSnapshotPydantic(
            token_id=symbol,
            timestamp=now,
            best_bid=candles[-1].bid,
            best_ask=candles[-1].ask,
            mid=candles[-1].mid,
            spread=0.1,
        ),
        candles=candles,
        updated_at=now,
    )
    return state


def test_bracket_trailing_iceberg_and_execution_schedules() -> None:
    manager = OrderManager()
    engine = AdvancedOrderEngine(manager)

    bracket = engine.place_bracket_order(
        market_id="BTCUSDT",
        side="BUY",
        entry_size=2.0,
        entry_price=100.0,
        stop_loss_price=97.0,
        take_profit_price=104.0,
    )
    engine.on_entry_filled(bracket.entry.order_id)
    assert manager.orders[bracket.stop_loss.order_id].metadata["active"] is True
    assert manager.orders[bracket.take_profit.order_id].metadata["active"] is True

    engine.on_oco_child_filled(bracket.take_profit.order_id)
    assert manager.orders[bracket.stop_loss.order_id].status == OrderStatus.CANCELLED

    trailing = manager.place_order(
        market_id="BTCUSDT",
        side="sell",
        size=1.0,
        order_type="trailing_stop",
        trail_percent=0.02,
        limit_price=95.0,
    )
    updated_stop = engine.update_trailing_stop(trailing.order_id, current_price=110.0)
    assert updated_stop >= 95.0

    iceberg = engine.place_iceberg_order(
        market_id="BTCUSDT",
        side="BUY",
        total_size=10.0,
        visible_size=3.0,
        limit_price=101.0,
    )
    next_state = engine.on_iceberg_slice_filled(iceberg.parent_id, filled_size=3.0)
    assert next_state.remaining_size == 7.0

    start = datetime.now(UTC)
    twap = engine.build_twap_schedule(total_size=12.0, slices=4, start_time=start, duration_seconds=120)
    vwap = engine.build_vwap_schedule(total_size=10.0, volume_profile=[1.0, 2.0, 1.0], start_time=start, interval_seconds=60)
    assert sum(item.size for item in twap) == 12.0
    assert round(sum(item.size for item in vwap), 8) == 10.0


def test_pattern_and_regime_strategies_generate_orders() -> None:
    bullish_state = _sample_market_state(drift=0.35)
    markets = {"BTCUSDT": bullish_state}
    portfolio = Portfolio()

    pattern_orders = PatternStrategy(min_confidence=0.5, base_order_size=50.0).on_bar(markets, portfolio)
    assert all(order.side in {Side.BUY, Side.SELL} for order in pattern_orders)

    regime_strategy = RegimeAdaptiveStrategy(base_order_size=50.0, momentum_threshold=0.0001)
    regime_orders = regime_strategy.on_bar(markets, portfolio)
    assert all(order.side in {Side.BUY, Side.SELL} for order in regime_orders)
