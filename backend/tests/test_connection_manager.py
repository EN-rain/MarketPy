"""Unit tests for realtime ConnectionManager."""

import pytest

from backend.app.models.realtime_config import BackpressureConfig, RateLimiterConfig
from backend.app.realtime.backpressure_handler import BackpressureHandler
from backend.app.realtime.connection_manager import ConnectionManager
from backend.app.realtime.health_monitor import HealthMonitor
from backend.app.realtime.rate_limiter import RateLimiter


class _FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        self.messages.append(payload)


@pytest.fixture
def manager():
    return ConnectionManager(
        rate_limiter=RateLimiter(RateLimiterConfig(max_messages_per_second=100, burst_size=100)),
        backpressure_handler=BackpressureHandler(BackpressureConfig()),
        health_monitor=HealthMonitor(),
    )


@pytest.mark.asyncio
async def test_connect_disconnect(manager):
    ws = _FakeWebSocket()
    await manager.connect(ws, "c1")
    assert ws.accepted is True
    assert "c1" in manager.active_client_ids
    await manager.disconnect("c1")
    assert "c1" not in manager.active_client_ids


@pytest.mark.asyncio
async def test_broadcast_sends_to_all(manager):
    ws1 = _FakeWebSocket()
    ws2 = _FakeWebSocket()
    await manager.connect(ws1, "a")
    await manager.connect(ws2, "b")
    await manager.broadcast({"type": "x"}, is_critical=False)
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1

