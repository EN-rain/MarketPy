"""Periodic updater for CoinDesk BPI snapshots."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from .coindesk_client import CoinDeskClient


class BPIService:
    """Service for periodic BPI updates at 15-minute intervals."""

    def __init__(
        self,
        client: CoinDeskClient,
        *,
        update_interval_seconds: float = CoinDeskClient.UPDATE_INTERVAL_SECONDS,
        now_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ):
        self.client = client
        self.update_interval_seconds = update_interval_seconds
        self._now = now_fn or time.monotonic
        self._sleep = sleep_fn or asyncio.sleep
        self._last_update: float | None = None

    def should_update(self) -> bool:
        if self._last_update is None:
            return True
        return (self._now() - self._last_update) >= self.update_interval_seconds

    async def update_if_due(self) -> bool:
        if not self.should_update():
            return False
        await self.client.get_bpi(["USD", "EUR", "GBP"])
        self._last_update = self._now()
        return True

    async def run_periodic_updates(self, *, tick_seconds: float = 1.0) -> None:
        while True:
            await self.update_if_due()
            await self._sleep(tick_seconds)

