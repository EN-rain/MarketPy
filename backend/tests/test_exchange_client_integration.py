"""Unit tests for ExchangeClient integration behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.ingest.exchange_client import ExchangeClient, ExchangeConfig, ExchangeType


class _FakeExchange:
    def __init__(self) -> None:
        self.fail_once = True

    async def fetch_ohlcv(self, symbol: str, timeframe: str, since: int | None, limit: int):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("transient")
        return [
            [1_700_000_000_000, 100, 110, 95, 105, 42.0],
            [1_700_000_060_000, 105, 112, 101, 108, 37.0],
        ][:limit]

    async def fetch_order_book(self, symbol: str, limit: int):
        return {
            "timestamp": 1_700_000_000_000,
            "bids": [[100.0, 5.0]],
            "asks": [[101.0, 6.0]],
        }

    async def fetch_ticker(self, symbol: str):
        return {"symbol": symbol, "last": 101.0}

    async def fetch_trades(self, symbol: str, since: int | None, limit: int):
        return [{"id": "1", "price": 100.0}]

    async def fetch_time(self):
        return 1_700_000_000_000

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_fetch_ohlcv_retries_and_converts() -> None:
    fake = _FakeExchange()
    client = ExchangeClient(
        ExchangeConfig(exchange_type=ExchangeType.BINANCE, max_retries=2),
        exchange_factory=lambda _: fake,
    )
    candles = await client.fetch_ohlcv("BTCUSDT", timeframe="1m", limit=2)
    assert len(candles) == 2
    assert candles[0].close == 105.0
    assert candles[0].timestamp == datetime.fromtimestamp(1_700_000_000, UTC)


@pytest.mark.asyncio
async def test_fetch_order_book_conversion() -> None:
    client = ExchangeClient(
        ExchangeConfig(exchange_type=ExchangeType.BINANCE),
        exchange_factory=lambda _: _FakeExchange(),
    )
    snapshot = await client.fetch_order_book("BTCUSDT", limit=1)
    assert snapshot.best_bid == 100.0
    assert snapshot.best_ask == 101.0
    assert snapshot.mid == pytest.approx(100.5)
