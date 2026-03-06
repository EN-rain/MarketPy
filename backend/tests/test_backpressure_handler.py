"""Unit tests for BackpressureHandler."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.app.models.realtime_config import BackpressureConfig
from backend.app.realtime.backpressure_handler import BackpressureHandler


class _FakeWebSocket:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.sent = []

    async def send_json(self, payload):
        if self.should_fail:
            raise RuntimeError("send failed")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_mark_slow_on_send_failure():
    handler = BackpressureHandler(
        BackpressureConfig(send_buffer_threshold=10, slow_client_timeout=1, drop_non_critical_for_slow=True)
    )
    ws = _FakeWebSocket(should_fail=True)
    ok = await handler.send_with_backpressure("c1", ws, {"x": 1}, is_critical=False)
    assert ok is False
    assert handler.slow_clients["c1"].is_slow is True


@pytest.mark.asyncio
async def test_drop_non_critical_for_slow_client():
    handler = BackpressureHandler(
        BackpressureConfig(send_buffer_threshold=10, slow_client_timeout=30, drop_non_critical_for_slow=True)
    )
    ws = _FakeWebSocket()
    handler.mark_slow_client("c2")
    ok = await handler.send_with_backpressure("c2", ws, {"x": 1}, is_critical=False)
    assert ok is False
    assert handler.slow_clients["c2"].dropped_messages == 1


def test_disconnect_timeout():
    handler = BackpressureHandler(
        BackpressureConfig(send_buffer_threshold=10, slow_client_timeout=1, drop_non_critical_for_slow=True)
    )
    handler.mark_slow_client("c3")
    handler.slow_clients["c3"].marked_slow_at = datetime.now(UTC) - timedelta(seconds=2)
    assert handler.should_disconnect("c3") is True

