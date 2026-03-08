"""MessageBatcher aggregates market updates into batched messages."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from backend.app.models.realtime import BatchedMessage, BatchMetadata, RealtimeMarketUpdate
from backend.app.models.realtime_config import BatcherConfig


class MessageBatcher:
    """Aggregates non-critical updates into batched messages to reduce network overhead.
    
    Key features:
    - Maintains separate batches per market_id
    - Timer-based flushing: Flush when batch_window_ms expires (default 100ms)
    - Size-based flushing: Flush when batch reaches max_batch_size (default 50 updates)
    - Ordering preservation: Updates within a market maintain insertion order
    - Batch metadata: Include update_count, time_range_ms, first_timestamp, last_timestamp
    """

    def __init__(self, config: BatcherConfig, flush_callback: Callable[[BatchedMessage], None] | None = None):
        """Initialize MessageBatcher with configuration.
        
        Args:
            config: Configuration parameters for batching
            flush_callback: Optional callback to invoke when a batch is flushed
        """
        self.batch_window_ms = config.batch_window_ms
        self.max_batch_size = config.max_batch_size
        self.enable_batching = config.enable_batching
        self.flush_callback = flush_callback

        # Separate batches per market_id
        self.batches: dict[str, list[RealtimeMarketUpdate]] = {}

        # Timer tasks per market_id
        self.batch_timers: dict[str, asyncio.Task] = {}

    async def add_update(self, update: RealtimeMarketUpdate) -> None:
        """Add update to batch. Flush if batch full or timer expires.
        
        This method:
        1. Adds update to market's batch
        2. Starts timer if this is first update in batch
        3. Flushes immediately if batch size reaches max
        4. Cancels existing timer when flushing
        
        Args:
            update: The market update to add to the batch
        """
        if not self.enable_batching:
            # If batching is disabled, flush immediately
            if self.flush_callback:
                batch = BatchedMessage(
                    market_id=update.market_id,
                    updates=[update],
                    batch_metadata=BatchMetadata(
                        update_count=1,
                        time_range_ms=0.0,
                        first_timestamp=update.timestamp,
                        last_timestamp=update.timestamp
                    ),
                    timestamp=datetime.now()
                )
                self.flush_callback(batch)
            return

        market_id = update.market_id

        # Initialize batch for this market if it doesn't exist
        if market_id not in self.batches:
            self.batches[market_id] = []

        # Add update to batch
        self.batches[market_id].append(update)

        # Start timer if this is the first update in the batch
        if len(self.batches[market_id]) == 1:
            await self._start_batch_timer(market_id)

        # Flush immediately if batch size reaches max
        if len(self.batches[market_id]) >= self.max_batch_size:
            await self._cancel_batch_timer(market_id)
            batch = await self.flush_batch(market_id)
            if batch and self.flush_callback:
                self.flush_callback(batch)

    async def flush_batch(self, market_id: str) -> BatchedMessage | None:
        """Flush accumulated updates for a market.
        
        Args:
            market_id: The market identifier
            
        Returns:
            BatchedMessage if there were updates to flush, None otherwise
        """
        # Get the batch for this market
        if market_id not in self.batches or not self.batches[market_id]:
            return None

        updates = self.batches[market_id]

        # Create batch metadata
        metadata = self.get_batch_metadata(market_id)
        if metadata is None:
            return None

        # Create batched message
        batch = BatchedMessage(
            market_id=market_id,
            updates=updates.copy(),
            batch_metadata=metadata,
            timestamp=datetime.now()
        )

        # Clear the batch
        self.batches[market_id] = []

        return batch

    def get_batch_metadata(self, market_id: str) -> BatchMetadata | None:
        """Get metadata about current batch (count, time range).
        
        Args:
            market_id: The market identifier
            
        Returns:
            BatchMetadata if batch exists, None otherwise
        """
        if market_id not in self.batches or not self.batches[market_id]:
            return None

        updates = self.batches[market_id]
        update_count = len(updates)

        first_timestamp = updates[0].timestamp
        last_timestamp = updates[-1].timestamp

        # Calculate time range in milliseconds
        time_range_ms = (last_timestamp - first_timestamp).total_seconds() * 1000

        return BatchMetadata(
            update_count=update_count,
            time_range_ms=time_range_ms,
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp
        )

    async def _start_batch_timer(self, market_id: str) -> None:
        """Start timer for batch window. Flush when timer expires.
        
        Args:
            market_id: The market identifier
        """
        async def timer_callback():
            """Timer callback that flushes the batch when time expires."""
            await asyncio.sleep(self.batch_window_ms / 1000.0)

            # Flush the batch
            batch = await self.flush_batch(market_id)

            # Remove timer from tracking
            if market_id in self.batch_timers:
                del self.batch_timers[market_id]

            # Invoke callback if provided
            if batch and self.flush_callback:
                self.flush_callback(batch)

        # Create and store the timer task
        self.batch_timers[market_id] = asyncio.create_task(timer_callback())

    async def _cancel_batch_timer(self, market_id: str) -> None:
        """Cancel existing timer for a market.
        
        Args:
            market_id: The market identifier
        """
        if market_id in self.batch_timers:
            timer = self.batch_timers[market_id]
            if not timer.done():
                timer.cancel()
                try:
                    await timer
                except asyncio.CancelledError:
                    pass
            del self.batch_timers[market_id]
