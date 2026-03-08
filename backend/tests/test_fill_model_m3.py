"""Tests for M3 depth-based fill model."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.models.market import OrderBookSnapshot, Side
from backend.sim.fill_model import fill_order_m3


def _depth_orderbook() -> OrderBookSnapshot:
    return OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        best_bid=99.0,
        best_ask=100.0,
        mid=99.5,
        spread=1.0,
        bids=[(99.0, 10.0), (98.5, 10.0), (98.0, 10.0)],
        asks=[(100.0, 10.0), (100.5, 10.0), (101.0, 10.0)],
    )


def test_m3_weighted_average_fill() -> None:
    result = fill_order_m3(Side.BUY, 15.0, _depth_orderbook(), max_depth_pct=1.0)
    assert result.filled is True
    # 10@100 + 5@100.5 = 1502.5 / 15 = 100.1667
    assert abs(result.fill_price - 100.1667) < 1e-3


def test_m3_depth_limit_rejection() -> None:
    # total ask depth=30, 10% rule -> max size 3
    result = fill_order_m3(Side.BUY, 5.0, _depth_orderbook(), max_depth_pct=0.10)
    assert result.filled is False
    assert result.reason == "depth_limit_exceeded"
