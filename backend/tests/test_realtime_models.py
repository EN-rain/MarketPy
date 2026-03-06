"""Tests for realtime data models."""

from datetime import datetime

from backend.app.models.realtime import (
    BatchedMessage,
    BatchMetadata,
    ConnectionMetrics,
    PreviousMarketState,
    ProcessingMetrics,
    RealtimeMarketUpdate,
    UpdatePriority,
)


def test_update_priority_enum():
    """Test UpdatePriority enum values."""
    assert UpdatePriority.CRITICAL.value == "CRITICAL"
    assert UpdatePriority.NON_CRITICAL.value == "NON_CRITICAL"


def test_market_update_creation():
    """Test MarketUpdate dataclass creation with all fields."""
    now = datetime.now()
    update = RealtimeMarketUpdate(
        market_id="BTCUSDT",
        timestamp=now,
        event_type="ticker",
        data={"price": 50000.0},
        bid=49999.0,
        ask=50001.0,
        mid=50000.0,
        spread=2.0,
        last_trade=50000.0,
        priority=UpdatePriority.CRITICAL,
        sequence_number=123,
        processing_latency_ms=5.5,
    )

    assert update.market_id == "BTCUSDT"
    assert update.timestamp == now
    assert update.event_type == "ticker"
    assert update.data == {"price": 50000.0}
    assert update.bid == 49999.0
    assert update.ask == 50001.0
    assert update.mid == 50000.0
    assert update.spread == 2.0
    assert update.last_trade == 50000.0
    assert update.priority == UpdatePriority.CRITICAL
    assert update.sequence_number == 123
    assert update.processing_latency_ms == 5.5


def test_market_update_defaults():
    """Test MarketUpdate with default values."""
    now = datetime.now()
    update = RealtimeMarketUpdate(
        market_id="ETHUSDT",
        timestamp=now,
        event_type="trade",
        data={},
    )

    assert update.bid is None
    assert update.ask is None
    assert update.mid is None
    assert update.spread is None
    assert update.last_trade is None
    assert update.priority == UpdatePriority.NON_CRITICAL
    assert update.sequence_number == 0
    assert update.processing_latency_ms == 0.0


def test_batch_metadata_creation():
    """Test BatchMetadata dataclass creation."""
    first_ts = datetime.now()
    last_ts = datetime.now()

    metadata = BatchMetadata(
        update_count=10,
        time_range_ms=100.5,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
    )

    assert metadata.update_count == 10
    assert metadata.time_range_ms == 100.5
    assert metadata.first_timestamp == first_ts
    assert metadata.last_timestamp == last_ts


def test_batched_message_creation():
    """Test BatchedMessage dataclass creation."""
    now = datetime.now()
    update1 = RealtimeMarketUpdate(
        market_id="BTCUSDT",
        timestamp=now,
        event_type="ticker",
        data={},
    )
    update2 = RealtimeMarketUpdate(
        market_id="BTCUSDT",
        timestamp=now,
        event_type="ticker",
        data={},
    )

    metadata = BatchMetadata(
        update_count=2,
        time_range_ms=50.0,
        first_timestamp=now,
        last_timestamp=now,
    )

    batched = BatchedMessage(
        market_id="BTCUSDT",
        updates=[update1, update2],
        batch_metadata=metadata,
        timestamp=now,
    )

    assert batched.market_id == "BTCUSDT"
    assert len(batched.updates) == 2
    assert batched.batch_metadata == metadata
    assert batched.timestamp == now
    assert batched.type == "batched_update"


def test_connection_metrics_creation():
    """Test ConnectionMetrics dataclass creation."""
    connected_at = datetime.now()
    last_activity = datetime.now()

    metrics = ConnectionMetrics(
        client_id="client-123",
        connected_at=connected_at,
        connection_duration_seconds=120.5,
        messages_sent=100,
        messages_failed=2,
        messages_dropped=5,
        average_latency_ms=15.3,
        is_slow=False,
        last_activity=last_activity,
    )

    assert metrics.client_id == "client-123"
    assert metrics.connected_at == connected_at
    assert metrics.connection_duration_seconds == 120.5
    assert metrics.messages_sent == 100
    assert metrics.messages_failed == 2
    assert metrics.messages_dropped == 5
    assert metrics.average_latency_ms == 15.3
    assert metrics.is_slow is False
    assert metrics.last_activity == last_activity


def test_processing_metrics_creation():
    """Test ProcessingMetrics dataclass creation."""
    last_update = datetime.now()

    metrics = ProcessingMetrics(
        market_id="BTCUSDT",
        updates_processed=1000,
        average_latency_ms=10.5,
        p95_latency_ms=25.0,
        p99_latency_ms=45.0,
        errors=3,
        last_update=last_update,
    )

    assert metrics.market_id == "BTCUSDT"
    assert metrics.updates_processed == 1000
    assert metrics.average_latency_ms == 10.5
    assert metrics.p95_latency_ms == 25.0
    assert metrics.p99_latency_ms == 45.0
    assert metrics.errors == 3
    assert metrics.last_update == last_update


def test_previous_market_state_creation():
    """Test PreviousMarketState dataclass creation."""
    last_update = datetime.now()

    state = PreviousMarketState(
        market_id="BTCUSDT",
        last_price=50000.0,
        last_bid=49999.0,
        last_ask=50001.0,
        last_volume=100.5,
        last_update=last_update,
        price_history=[49000.0, 49500.0, 50000.0],
    )

    assert state.market_id == "BTCUSDT"
    assert state.last_price == 50000.0
    assert state.last_bid == 49999.0
    assert state.last_ask == 50001.0
    assert state.last_volume == 100.5
    assert state.last_update == last_update
    assert state.price_history == [49000.0, 49500.0, 50000.0]


def test_previous_market_state_defaults():
    """Test PreviousMarketState with default values."""
    state = PreviousMarketState(market_id="ETHUSDT")

    assert state.market_id == "ETHUSDT"
    assert state.last_price is None
    assert state.last_bid is None
    assert state.last_ask is None
    assert state.last_volume is None
    assert state.last_update is None
    assert state.price_history == []
