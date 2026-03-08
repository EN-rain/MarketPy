"""Integration tests for enhanced realtime update flow."""

import asyncio
from datetime import datetime

import pytest

from backend.app.models.realtime import RealtimeMarketUpdate, UpdatePriority
from backend.app.models.realtime_config import (
    BackpressureConfig,
    BatcherConfig,
    PrioritizerConfig,
    RateLimiterConfig,
)
from backend.app.realtime.backpressure_handler import BackpressureHandler
from backend.app.realtime.connection_manager import ConnectionManager
from backend.app.realtime.health_monitor import HealthMonitor
from backend.app.realtime.message_batcher import MessageBatcher
from backend.app.realtime.rate_limiter import RateLimiter
from backend.app.realtime.update_prioritizer import UpdatePrioritizer


class _FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def accept(self):
        return None

    async def send_json(self, payload):
        self.messages.append(payload)


@pytest.mark.asyncio
async def test_critical_bypass_vs_batched_flow():
    sent_batches = []
    batcher = MessageBatcher(
        BatcherConfig(batch_window_ms=5, max_batch_size=50, enable_batching=True),
        flush_callback=lambda b: sent_batches.append(b),
    )
    prioritizer = UpdatePrioritizer(PrioritizerConfig(price_change_threshold=0.01))

    critical = RealtimeMarketUpdate(
        market_id="BTCUSDT",
        timestamp=datetime.now(),
        event_type="order_fill",
        data={},
        priority=UpdatePriority.CRITICAL,
    )
    non_critical = RealtimeMarketUpdate(
        market_id="BTCUSDT",
        timestamp=datetime.now(),
        event_type="ticker",
        data={},
        mid=100.0,
    )

    assert prioritizer.is_critical(critical, previous_state=None) is True
    assert prioritizer.is_critical(non_critical, previous_state=None) is True
    # Non-first updates should be non-critical and batched.
    await batcher.add_update(non_critical)
    await asyncio.sleep(0.01)
    assert len(sent_batches) >= 1


@pytest.mark.asyncio
async def test_connection_manager_with_realtime_components():
    manager = ConnectionManager(
        rate_limiter=RateLimiter(RateLimiterConfig(max_messages_per_second=100, burst_size=100)),
        backpressure_handler=BackpressureHandler(BackpressureConfig()),
        health_monitor=HealthMonitor(),
    )
    ws = _FakeWebSocket()
    await manager.connect(ws, "client-1")
    await manager.broadcast({"type": "market_update", "data": {"x": 1}})
    assert len(ws.messages) == 1
