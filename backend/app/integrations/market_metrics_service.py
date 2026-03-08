"""Periodic updater/service for CoinPaprika market metrics."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from backend.app.storage.metrics_store import MetricsStore

from .coinpaprika_client import CoinPaprikaClient


class MarketMetricsService:
    """Background service for updating and serving market metrics."""

    def __init__(
        self,
        client: CoinPaprikaClient,
        tracked_coin_ids: list[str],
        *,
        update_interval_seconds: float = 300.0,
        store: MetricsStore | None = None,
        now_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ):
        self.client = client
        self.tracked_coin_ids = tracked_coin_ids
        self.update_interval_seconds = update_interval_seconds
        self.store = store
        self._now = now_fn or time.monotonic
        self._sleep = sleep_fn or asyncio.sleep
        self._last_update: dict[str, float] = {}
        self._running = False

    def should_update(self, coin_id: str) -> bool:
        last = self._last_update.get(coin_id)
        if last is None:
            return True
        return (self._now() - last) >= self.update_interval_seconds

    async def update_coin(self, coin_id: str) -> bool:
        try:
            metrics = await self.client.get_market_metrics(coin_id)
            if self.store is not None:
                self.store.insert_market_metrics(metrics)
            self._last_update[coin_id] = self._now()
            return True
        except Exception:
            return False

    async def update_due_coins(self) -> int:
        updated = 0
        for coin_id in self.tracked_coin_ids:
            if self.should_update(coin_id):
                ok = await self.update_coin(coin_id)
                if ok:
                    updated += 1
        return updated

    async def run_periodic_updates(self, *, tick_seconds: float = 1.0) -> None:
        self._running = True
        try:
            while True:
                await self.update_due_coins()
                await self._sleep(tick_seconds)
        finally:
            self._running = False

    def get_metrics(self, coin_id: str) -> dict[str, Any] | None:
        return self.client.get_cached_metrics(
            coin_id, stale_after_seconds=self.update_interval_seconds
        )
