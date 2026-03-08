"""Tests for exchange time synchronization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.ingest.time_synchronizer import TimeSynchronizer


class _FakeClient:
    async def fetch_server_time(self) -> datetime:
        return datetime.now(UTC) + timedelta(milliseconds=500)


@pytest.mark.asyncio
async def test_time_round_trip() -> None:
    sync = TimeSynchronizer(_FakeClient())  # type: ignore[arg-type]
    await sync.initialize()
    now = datetime.now(UTC)
    converted = sync.system_to_exchange(now)
    restored = sync.exchange_to_system(converted)
    assert abs((restored - now).total_seconds()) < 0.01
