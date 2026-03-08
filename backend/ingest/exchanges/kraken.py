"""Kraken exchange adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, OrderBook, Position, Ticker, Trade


StreamFactory = Callable[[str, str], AsyncIterator[dict[str, Any]]]


class KrakenAdapter(ExchangeAdapter):
    websocket_url = "wss://ws.kraken.com"
    rest_base_url = "https://api.kraken.com"

    def __init__(self, *, rest_client: Any | None = None, stream_factory: StreamFactory | None = None) -> None:
        super().__init__("kraken", rate_limit_per_second=5)
        self._rest_client = rest_client
        self._stream_factory = stream_factory

    async def connect(self) -> None:
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for order book subscriptions")
        async for payload in self._stream_factory("order_book", symbol):
            yield OrderBook(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                bids=[(float(p), float(s)) for p, s in payload.get("bids", [])],
                asks=[(float(p), float(s)) for p, s in payload.get("asks", [])],
            )

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            yield Trade(
                symbol=symbol,
                trade_id=str(payload["trade_id"]),
                price=float(payload["price"]),
                quantity=float(payload["volume"]),
                side=str(payload["side"]),
                timestamp=datetime.now(UTC),
            )

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        await self.rate_limiter.acquire()
        return await self._rest_client.post("/0/private/AddOrder", payload=order)

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/0/public/Ticker", params={"pair": symbol})
        entry = next(iter(payload["result"].values()))
        return Ticker(
            symbol=symbol,
            bid=float(entry["b"][0]),
            ask=float(entry["a"][0]),
            last=float(entry["c"][0]),
            volume_24h=float(entry["v"][1]),
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []
