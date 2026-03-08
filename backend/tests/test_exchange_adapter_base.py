from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from backend.ingest.exchanges.base import (
    Balance,
    ExchangeAdapter,
    OrderBook,
    Position,
    Ticker,
    Trade,
)


class FakeExchangeAdapter(ExchangeAdapter):
    def __init__(self, failures_before_success: int = 0) -> None:
        super().__init__("fake", rate_limit_per_second=10)
        self.failures_before_success = failures_before_success

    async def connect(self) -> None:
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("temporary failure")

    async def disconnect(self) -> None:
        return None

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        yield OrderBook(symbol=symbol, timestamp=datetime.now(UTC), bids=[(100.0, 1.0)], asks=[(101.0, 1.0)])

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        yield Trade(symbol=symbol, trade_id="t1", price=100.0, quantity=1.0, side="buy", timestamp=datetime.now(UTC))

    async def place_order(self, order: dict[str, object]) -> dict[str, object]:
        return {"status": "accepted", **order}

    async def get_ticker(self, symbol: str) -> Ticker:
        return Ticker(symbol=symbol, bid=100.0, ask=101.0, last=100.5, volume_24h=12.0, timestamp=datetime.now(UTC))

    async def get_positions(self) -> list[Position]:
        return [Position(symbol="BTCUSDT", side="long", quantity=1.0, entry_price=100.0, mark_price=101.0, leverage=2.0, unrealized_pnl=1.0)]

    async def get_balances(self) -> list[Balance]:
        return [Balance(asset="USDT", free=1000.0, locked=0.0, total=1000.0)]


@pytest.mark.asyncio
async def test_exchange_adapter_connects_with_retries() -> None:
    adapter = FakeExchangeAdapter(failures_before_success=2)

    await adapter.connect_with_retries(attempts=3)

    assert adapter.health.connected is True
    assert adapter.health.reconnect_attempts == 2


@pytest.mark.asyncio
async def test_exchange_adapter_rate_limiter_acquires_token() -> None:
    adapter = FakeExchangeAdapter()

    await asyncio.wait_for(adapter.rate_limiter.acquire(), timeout=0.1)


def test_exchange_adapter_uses_expected_backoff_sequence() -> None:
    assert FakeExchangeAdapter.reconnection_delays(5) == [1, 2, 4, 8, 16]
