"""Connection manager for multiple exchange adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .base import ExchangeAdapter


class ConnectionManager:
    def __init__(self, *, health_check_interval_seconds: int = 10) -> None:
        self.health_check_interval_seconds = health_check_interval_seconds
        self._adapters: dict[str, ExchangeAdapter] = {}
        self._listeners: list[Callable[[str, bool], None]] = []

    def add_exchange(self, name: str, adapter: ExchangeAdapter) -> None:
        self._adapters[name] = adapter

    def add_listener(self, listener: Callable[[str, bool], None]) -> None:
        self._listeners.append(listener)

    @property
    def adapters(self) -> dict[str, ExchangeAdapter]:
        return dict(self._adapters)

    async def connect_all(self) -> None:
        for adapter in self._adapters.values():
            await adapter.connect_with_retries()
            self._emit(adapter.exchange_name, adapter.health.connected)

    async def monitor_connections(self, *, iterations: int = 1) -> None:
        for _ in range(iterations):
            for adapter in self._adapters.values():
                if not adapter.health.connected:
                    await adapter.connect_with_retries()
                self._emit(adapter.exchange_name, adapter.health.connected)
            await asyncio.sleep(self.health_check_interval_seconds)

    def statuses(self) -> dict[str, bool]:
        return {name: adapter.health.connected for name, adapter in self._adapters.items()}

    def _emit(self, exchange_name: str, status: bool) -> None:
        for listener in self._listeners:
            listener(exchange_name, status)
