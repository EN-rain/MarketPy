"""Lightweight load-oriented sanity tests for realtime components."""

import asyncio
from datetime import datetime

import pytest

from backend.app.models.realtime import RealtimeMarketUpdate
from backend.app.models.realtime_config import BatcherConfig
from backend.app.realtime.message_batcher import MessageBatcher


@pytest.mark.asyncio
async def test_batcher_handles_burst_profile():
    flushed = []
    batcher = MessageBatcher(
        BatcherConfig(batch_window_ms=20, max_batch_size=100, enable_batching=True),
        flush_callback=lambda b: flushed.append(b),
    )
    for i in range(300):
        await batcher.add_update(
            RealtimeMarketUpdate(
                market_id="BTCUSDT",
                timestamp=datetime.now(),
                event_type="ticker",
                data={},
                mid=100 + i * 0.01,
            )
        )
    await asyncio.sleep(0.05)
    assert sum(len(batch.updates) for batch in flushed) == 300

