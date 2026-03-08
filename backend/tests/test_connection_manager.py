from __future__ import annotations

import pytest

from backend.ingest.exchanges.base import ExchangeAdapter
from backend.ingest.exchanges.manager import ConnectionManager


class FakeAdapter(ExchangeAdapter):
    def __init__(self, name: str, *, failures_before_success: int = 0) -> None:
        super().__init__(name, rate_limit_per_second=10)
        self.failures_before_success = failures_before_success

    async def connect(self) -> None:
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("temporary")
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    async def subscribe_order_book(self, symbol: str):
        if False:
            yield None

    async def subscribe_trades(self, symbol: str):
        if False:
            yield None

    async def place_order(self, order):
        return order

    async def get_ticker(self, symbol):
        raise NotImplementedError

    async def get_positions(self):
        return []

    async def get_balances(self):
        return []


@pytest.mark.asyncio
async def test_connection_manager_connects_and_emits_status() -> None:
    manager = ConnectionManager(health_check_interval_seconds=0)
    events: list[tuple[str, bool]] = []
    manager.add_listener(lambda name, status: events.append((name, status)))
    manager.add_exchange("binance", FakeAdapter("binance"))
    manager.add_exchange("coinbase", FakeAdapter("coinbase"))

    await manager.connect_all()

    assert manager.statuses() == {"binance": True, "coinbase": True}
    assert ("binance", True) in events
    assert ("coinbase", True) in events


@pytest.mark.asyncio
async def test_connection_manager_reconnects_disconnected_adapters() -> None:
    manager = ConnectionManager(health_check_interval_seconds=0)
    adapter = FakeAdapter("kraken", failures_before_success=1)
    manager.add_exchange("kraken", adapter)

    await manager.monitor_connections(iterations=1)

    assert manager.statuses()["kraken"] is True
