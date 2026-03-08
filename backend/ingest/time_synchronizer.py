"""Exchange clock synchronization utilities."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from backend.ingest.exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class TimeSynchronizer:
    """Synchronizes system clock with exchange server time."""

    def __init__(
        self,
        exchange_client: ExchangeClient,
        sync_interval_seconds: int = 300,
        warning_threshold_ms: int = 1000,
    ) -> None:
        self.exchange_client = exchange_client
        self.sync_interval_seconds = sync_interval_seconds
        self.warning_threshold_ms = warning_threshold_ms
        self._offset = timedelta(0)
        self._last_sync: datetime | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def initialize(self) -> None:
        await self.refresh()

    async def refresh(self) -> None:
        system_time = datetime.now(UTC)
        exchange_time = await self.exchange_client.fetch_server_time()
        self._offset = exchange_time - system_time
        self._last_sync = datetime.now(UTC)
        offset_ms = abs(self._offset.total_seconds() * 1000)
        if offset_ms > self.warning_threshold_ms:
            logger.warning(
                "Exchange clock offset exceeds threshold: offset_ms=%.2f threshold_ms=%s",
                offset_ms,
                self.warning_threshold_ms,
            )

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self.initialize()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.sync_interval_seconds)
            try:
                await self.refresh()
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("Time sync refresh failed: %s", exc)

    def system_to_exchange(self, timestamp: datetime) -> datetime:
        return timestamp + self._offset

    def exchange_to_system(self, timestamp: datetime) -> datetime:
        return timestamp - self._offset

    def get_offset(self) -> timedelta:
        return self._offset

    def get_last_sync(self) -> datetime | None:
        return self._last_sync
