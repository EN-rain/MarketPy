"""Huobi exchange adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, OrderBook, Position, Ticker, Trade


class HuobiAdapter(ExchangeAdapter):
    websocket_url = "wss://api.huobi.pro/ws"
    rest_base_url = "https://api.huobi.pro"

    def __init__(self, *, rest_client: Any | None = None, stream_factory: Any | None = None) -> None:
        super().__init__("huobi", rate_limit_per_second=10)
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
            tick = payload.get("tick", payload)
            yield OrderBook(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                bids=[(float(p), float(s)) for p, s in tick.get("bids", [])],
                asks=[(float(p), float(s)) for p, s in tick.get("asks", [])],
            )

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            row = payload.get("tick", payload)
            yield Trade(
                symbol=symbol,
                trade_id=str(row.get("id", "")),
                price=float(row.get("price", 0.0)),
                quantity=float(row.get("amount", 0.0)),
                side=str(row.get("direction", "buy")).lower(),
                timestamp=datetime.now(UTC),
            )

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        return await self._rest_client.post("/v1/order/orders/place", payload=order)

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/market/detail/merged", params={"symbol": symbol.lower()})
        tick = payload.get("tick", payload)
        return Ticker(
            symbol=symbol,
            bid=float((tick.get("bid") or [0.0])[0]),
            ask=float((tick.get("ask") or [0.0])[0]),
            last=float(tick.get("close", 0.0)),
            volume_24h=float(tick.get("amount", 0.0)),
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []
