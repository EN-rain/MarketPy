"""Tests for canonical market data models.

This test suite validates the canonical MarketUpdate and OrderBookSnapshot
models defined in backend.app.models.market, which serve as the single
source of truth for market data structures across the application.
"""

from datetime import UTC, datetime

from backend.app.models.market import MarketUpdate, OrderBookSnapshot


def test_orderbook_snapshot_creation():
    """Test OrderBookSnapshot dataclass creation with all fields."""
    now = datetime.now(UTC)

    snapshot = OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=now,
        best_bid=49999.0,
        best_ask=50001.0,
        mid=50000.0,
        spread=2.0,
        bids=[(49999.0, 1.5), (49998.0, 2.0), (49997.0, 3.0)],
        asks=[(50001.0, 1.2), (50002.0, 1.8), (50003.0, 2.5)],
    )

    assert snapshot.token_id == "BTCUSDT"
    assert snapshot.timestamp == now
    assert snapshot.best_bid == 49999.0
    assert snapshot.best_ask == 50001.0
    assert snapshot.mid == 50000.0
    assert snapshot.spread == 2.0
    assert len(snapshot.bids) == 3
    assert len(snapshot.asks) == 3
    assert snapshot.bids[0] == (49999.0, 1.5)
    assert snapshot.asks[0] == (50001.0, 1.2)


def test_orderbook_snapshot_empty_books():
    """Test OrderBookSnapshot with empty bid/ask lists."""
    now = datetime.now(UTC)

    snapshot = OrderBookSnapshot(
        token_id="ETHUSDT",
        timestamp=now,
        best_bid=None,
        best_ask=None,
        mid=None,
        spread=None,
    )

    assert snapshot.bids == []
    assert snapshot.asks == []
    assert snapshot.best_bid is None
    assert snapshot.best_ask is None
    assert snapshot.mid is None
    assert snapshot.spread is None


def test_market_update_creation_full():
    """Test MarketUpdate dataclass creation with all fields."""
    now = datetime.now(UTC)

    orderbook = OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=now,
        best_bid=49999.0,
        best_ask=50001.0,
        mid=50000.0,
        spread=2.0,
        bids=[(49999.0, 1.5)],
        asks=[(50001.0, 1.2)],
    )

    update = MarketUpdate(
        market_id="BTCUSDT",
        timestamp=now,
        mid=50000.0,
        bid=49999.0,
        ask=50001.0,
        last_trade=50000.5,
        orderbook=orderbook,
        volume_24h=1000000.0,
        change_24h_pct=2.5,
    )

    assert update.market_id == "BTCUSDT"
    assert update.timestamp == now
    assert update.mid == 50000.0
    assert update.bid == 49999.0
    assert update.ask == 50001.0
    assert update.last_trade == 50000.5
    assert update.orderbook == orderbook
    assert update.volume_24h == 1000000.0
    assert update.change_24h_pct == 2.5


def test_market_update_minimal():
    """Test MarketUpdate with only required fields."""
    now = datetime.now(UTC)

    update = MarketUpdate(
        market_id="ETHUSDT",
        timestamp=now,
        mid=3000.0,
        bid=None,
        ask=None,
        last_trade=None,
        orderbook=None,
    )

    assert update.market_id == "ETHUSDT"
    assert update.timestamp == now
    assert update.mid == 3000.0
    assert update.bid is None
    assert update.ask is None
    assert update.last_trade is None
    assert update.orderbook is None
    assert update.volume_24h is None
    assert update.change_24h_pct is None


def test_market_update_with_optional_fields():
    """Test MarketUpdate with some optional fields populated."""
    now = datetime.now(UTC)

    update = MarketUpdate(
        market_id="SOLUSDT",
        timestamp=now,
        mid=100.0,
        bid=99.9,
        ask=100.1,
        last_trade=100.05,
        orderbook=None,
        volume_24h=500000.0,
    )

    assert update.market_id == "SOLUSDT"
    assert update.mid == 100.0
    assert update.bid == 99.9
    assert update.ask == 100.1
    assert update.last_trade == 100.05
    assert update.volume_24h == 500000.0
    assert update.change_24h_pct is None


def test_market_update_orderbook_integration():
    """Test MarketUpdate with embedded OrderBookSnapshot."""
    now = datetime.now(UTC)

    orderbook = OrderBookSnapshot(
        token_id="ADAUSDT",
        timestamp=now,
        best_bid=0.499,
        best_ask=0.501,
        mid=0.5,
        spread=0.002,
        bids=[(0.499, 10000.0), (0.498, 15000.0)],
        asks=[(0.501, 8000.0), (0.502, 12000.0)],
    )

    update = MarketUpdate(
        market_id="ADAUSDT",
        timestamp=now,
        mid=0.5,
        bid=0.499,
        ask=0.501,
        last_trade=0.5,
        orderbook=orderbook,
    )

    # Verify orderbook is properly embedded
    assert update.orderbook is not None
    assert update.orderbook.token_id == "ADAUSDT"
    assert update.orderbook.best_bid == 0.499
    assert update.orderbook.best_ask == 0.501
    assert len(update.orderbook.bids) == 2
    assert len(update.orderbook.asks) == 2


def test_orderbook_snapshot_tuple_format():
    """Test that bids/asks use tuple format (price, size)."""
    now = datetime.now(UTC)

    snapshot = OrderBookSnapshot(
        token_id="BTCUSDT",
        timestamp=now,
        best_bid=50000.0,
        best_ask=50001.0,
        mid=50000.5,
        spread=1.0,
        bids=[(50000.0, 1.0), (49999.0, 2.0)],
        asks=[(50001.0, 1.5), (50002.0, 2.5)],
    )

    # Verify tuple structure
    for price, size in snapshot.bids:
        assert isinstance(price, float)
        assert isinstance(size, float)

    for price, size in snapshot.asks:
        assert isinstance(price, float)
        assert isinstance(size, float)

    # Verify specific values
    assert snapshot.bids[0][0] == 50000.0  # price
    assert snapshot.bids[0][1] == 1.0      # size
    assert snapshot.asks[0][0] == 50001.0  # price
    assert snapshot.asks[0][1] == 1.5      # size
