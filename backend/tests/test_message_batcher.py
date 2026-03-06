"""Unit tests for MessageBatcher component."""

import asyncio
from datetime import datetime, timedelta

import pytest

from backend.app.models.realtime import BatchedMessage, RealtimeMarketUpdate
from backend.app.models.realtime_config import BatcherConfig
from backend.app.realtime.message_batcher import MessageBatcher


class TestMessageBatcher:
    """Test suite for MessageBatcher."""

    @pytest.fixture
    def config(self):
        """Create default batcher config."""
        return BatcherConfig(
            batch_window_ms=100,
            max_batch_size=50,
            enable_batching=True
        )

    @pytest.fixture
    def batcher(self, config):
        """Create MessageBatcher instance."""
        return MessageBatcher(config)

    @pytest.mark.asyncio
    async def test_empty_batch_handling(self, batcher):
        """Flushing an empty batch should return None."""
        result = await batcher.flush_batch("BTC/USD")

        assert result is None

    @pytest.mark.asyncio
    async def test_single_update_batch(self, batcher):
        """Single update should be batched and flushed."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        await batcher.add_update(update)

        # Wait for timer to expire
        await asyncio.sleep(0.15)

        assert len(flushed_batches) == 1
        assert flushed_batches[0].market_id == "BTC/USD"
        assert len(flushed_batches[0].updates) == 1
        assert flushed_batches[0].updates[0] == update

    @pytest.mark.asyncio
    async def test_batch_exactly_at_size_limit(self, batcher):
        """Batch exactly at size limit should flush immediately."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add exactly max_batch_size updates
        for i in range(batcher.max_batch_size):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Should flush immediately without waiting for timer
        assert len(flushed_batches) == 1
        assert len(flushed_batches[0].updates) == batcher.max_batch_size

    @pytest.mark.asyncio
    async def test_timer_expiration_with_partial_batch(self, batcher):
        """Timer expiration should flush partial batch."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add 5 updates (less than max_batch_size)
        for i in range(5):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Wait for timer to expire
        await asyncio.sleep(0.15)

        assert len(flushed_batches) == 1
        assert len(flushed_batches[0].updates) == 5

    @pytest.mark.asyncio
    async def test_concurrent_adds_from_multiple_markets(self, batcher):
        """Updates from different markets should be batched separately."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add updates for two different markets
        update1 = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        update2 = RealtimeMarketUpdate(
            market_id="ETH/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=3000.0
        )

        await batcher.add_update(update1)
        await batcher.add_update(update2)

        # Wait for timers to expire
        await asyncio.sleep(0.15)

        # Should have two separate batches
        assert len(flushed_batches) == 2

        # Check that each market has its own batch
        market_ids = {batch.market_id for batch in flushed_batches}
        assert market_ids == {"BTC/USD", "ETH/USD"}

    @pytest.mark.asyncio
    async def test_ordering_preservation(self, batcher):
        """Updates should maintain insertion order within a batch."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add updates with different prices
        prices = [50000.0, 50100.0, 50200.0, 50300.0, 50400.0]
        for price in prices:
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=price
            )
            await batcher.add_update(update)

        # Wait for timer to expire
        await asyncio.sleep(0.15)

        assert len(flushed_batches) == 1

        # Check ordering
        batch_prices = [u.mid for u in flushed_batches[0].updates]
        assert batch_prices == prices

    @pytest.mark.asyncio
    async def test_batch_metadata_completeness(self, batcher):
        """Batch metadata should contain correct information."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add updates with specific timestamps
        base_time = datetime.now()
        for i in range(5):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=base_time + timedelta(milliseconds=i * 10),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Wait for timer to expire
        await asyncio.sleep(0.15)

        assert len(flushed_batches) == 1

        metadata = flushed_batches[0].batch_metadata
        assert metadata.update_count == 5
        assert metadata.first_timestamp == base_time
        assert metadata.last_timestamp == base_time + timedelta(milliseconds=40)
        assert metadata.time_range_ms == pytest.approx(40.0, abs=1.0)

    @pytest.mark.asyncio
    async def test_get_batch_metadata_for_nonexistent_market(self, batcher):
        """Getting metadata for nonexistent market should return None."""
        metadata = batcher.get_batch_metadata("NONEXISTENT")

        assert metadata is None

    @pytest.mark.asyncio
    async def test_get_batch_metadata_for_empty_batch(self, batcher):
        """Getting metadata for empty batch should return None."""
        # Initialize batch but don't add updates
        batcher.batches["BTC/USD"] = []

        metadata = batcher.get_batch_metadata("BTC/USD")

        assert metadata is None

    @pytest.mark.asyncio
    async def test_flush_clears_batch(self, batcher):
        """Flushing should clear the batch."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        await batcher.add_update(update)

        # Manually flush
        batch = await batcher.flush_batch("BTC/USD")

        assert batch is not None
        assert len(batcher.batches.get("BTC/USD", [])) == 0

    @pytest.mark.asyncio
    async def test_timer_cancellation_on_size_flush(self, batcher):
        """Timer should be cancelled when batch flushes due to size."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add max_batch_size updates to trigger size-based flush
        for i in range(batcher.max_batch_size):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Timer should be cancelled
        assert "BTC/USD" not in batcher.batch_timers

        # Wait to ensure no additional flush from timer
        await asyncio.sleep(0.15)

        # Should only have one flush (from size limit)
        assert len(flushed_batches) == 1

    @pytest.mark.asyncio
    async def test_batching_disabled(self):
        """When batching is disabled, updates should flush immediately."""
        config = BatcherConfig(
            batch_window_ms=100,
            max_batch_size=50,
            enable_batching=False
        )
        batcher = MessageBatcher(config)

        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add multiple updates
        for i in range(5):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Should flush immediately for each update
        assert len(flushed_batches) == 5

        # Each batch should contain only one update
        for batch in flushed_batches:
            assert len(batch.updates) == 1

    @pytest.mark.asyncio
    async def test_multiple_flushes_for_same_market(self, batcher):
        """Multiple batches for the same market should work correctly."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # First batch
        for i in range(5):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Wait for first batch to flush
        await asyncio.sleep(0.15)

        # Second batch
        for i in range(5):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=51000.0 + i
            )
            await batcher.add_update(update)

        # Wait for second batch to flush
        await asyncio.sleep(0.15)

        assert len(flushed_batches) == 2
        assert all(batch.market_id == "BTC/USD" for batch in flushed_batches)

    @pytest.mark.asyncio
    async def test_batch_message_structure(self, batcher):
        """BatchedMessage should have correct structure."""
        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        await batcher.add_update(update)
        await asyncio.sleep(0.15)

        assert len(flushed_batches) == 1

        batch = flushed_batches[0]
        assert isinstance(batch, BatchedMessage)
        assert batch.type == "batched_update"
        assert batch.market_id == "BTC/USD"
        assert isinstance(batch.updates, list)
        assert batch.batch_metadata is not None
        assert isinstance(batch.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_no_callback_provided(self, batcher):
        """Batcher should work without callback."""
        # No callback set
        batcher.flush_callback = None

        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        # Should not raise exception
        await batcher.add_update(update)
        await asyncio.sleep(0.15)

    @pytest.mark.asyncio
    async def test_configurable_batch_window(self):
        """Batch window should be configurable."""
        config = BatcherConfig(
            batch_window_ms=50,  # Shorter window
            max_batch_size=50,
            enable_batching=True
        )
        batcher = MessageBatcher(config)

        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        await batcher.add_update(update)

        # Wait for shorter timer
        await asyncio.sleep(0.08)

        assert len(flushed_batches) == 1

    @pytest.mark.asyncio
    async def test_configurable_max_batch_size(self):
        """Max batch size should be configurable."""
        config = BatcherConfig(
            batch_window_ms=100,
            max_batch_size=10,  # Smaller max size
            enable_batching=True
        )
        batcher = MessageBatcher(config)

        flushed_batches = []

        def callback(batch):
            flushed_batches.append(batch)

        batcher.flush_callback = callback

        # Add 10 updates to trigger size-based flush
        for i in range(10):
            update = RealtimeMarketUpdate(
                market_id="BTC/USD",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=50000.0 + i
            )
            await batcher.add_update(update)

        # Should flush immediately
        assert len(flushed_batches) == 1
        assert len(flushed_batches[0].updates) == 10
