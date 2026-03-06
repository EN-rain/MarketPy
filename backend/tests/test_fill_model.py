"""Tests for fill models."""

from datetime import UTC, datetime

import pytest

from backend.app.models.market import OrderBookSnapshot, Side
from backend.sim.fill_model import FillModelLevel, fill_order, fill_order_m1, fill_order_m2


def make_orderbook(bid: float = 0.60, ask: float = 0.64) -> OrderBookSnapshot:
    """Create a test orderbook."""
    mid = (bid + ask) / 2
    spread = ask - bid
    return OrderBookSnapshot(
        token_id="test-token",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        best_bid=bid,
        best_ask=ask,
        mid=mid,
        spread=spread,
        bids=[(bid, 100.0)],
        asks=[(ask, 100.0)],
    )


class TestFillModelM1:
    def test_buy_fills_at_mid(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m1(Side.BUY, 100, ob)
        assert result.filled is True
        assert result.fill_price == pytest.approx(0.62, abs=0.001)
        assert result.slippage == 0.0

    def test_sell_fills_at_mid(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m1(Side.SELL, 50, ob)
        assert result.filled is True
        assert result.fill_price == pytest.approx(0.62, abs=0.001)

    def test_empty_orderbook_no_fill(self):
        ob = OrderBookSnapshot(
            token_id="test",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            best_bid=None,
            best_ask=None,
            mid=None,
            spread=None,
            bids=[],
            asks=[],
        )
        result = fill_order_m1(Side.BUY, 100, ob)
        assert result.filled is False


class TestFillModelM2:
    def test_buy_fills_at_ask(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.BUY, 100, ob)
        assert result.filled is True
        assert result.fill_price == 0.64

    def test_sell_fills_at_bid(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.SELL, 100, ob)
        assert result.filled is True
        assert result.fill_price == 0.60

    def test_slippage_is_positive(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.BUY, 100, ob)
        assert result.slippage > 0

    def test_limit_buy_not_filled(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.BUY, 100, ob, limit_price=0.62)
        assert result.filled is False  # ask(0.64) > limit(0.62)

    def test_limit_buy_filled(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.BUY, 100, ob, limit_price=0.65)
        assert result.filled is True  # ask(0.64) <= limit(0.65)

    def test_limit_sell_not_filled(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.SELL, 100, ob, limit_price=0.62)
        assert result.filled is False  # bid(0.60) < limit(0.62)

    def test_fee_is_deducted(self):
        ob = make_orderbook(bid=0.60, ask=0.64)
        result = fill_order_m2(Side.BUY, 100, ob)
        assert result.fee > 0


class TestFillOrderDispatch:
    def test_m1_dispatch(self):
        ob = make_orderbook()
        result = fill_order(Side.BUY, 100, ob, model=FillModelLevel.M1_MID)
        assert result.filled
        assert result.fill_price == pytest.approx(0.62, abs=0.001)

    def test_m2_dispatch(self):
        ob = make_orderbook()
        result = fill_order(Side.BUY, 100, ob, model=FillModelLevel.M2_BIDASK)
        assert result.filled
        assert result.fill_price == 0.64
