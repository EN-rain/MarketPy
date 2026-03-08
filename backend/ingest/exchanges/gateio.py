"""Gate.io exchange adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, OrderBook, Position, Ticker, Trade


class GateAdapter(ExchangeAdapter):
    websocket_url = "wss://api.gateio.ws/ws/v4/"
    rest_base_url = "https://api.gateio.ws/api/v4"

    def __init__(self, *, rest_client: Any | None = None, stream_factory: Any | None = None) -> None:
        super().__init__("gateio", rate_limit_per_second=10)
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
                trade_id=str(payload.get("id", "")),
                price=float(payload.get("price", 0.0)),
                quantity=float(payload.get("amount", 0.0)),
                side=str(payload.get("side", "buy")).lower(),
                timestamp=datetime.now(UTC),
            )

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        return await self._rest_client.post("/spot/orders", payload=order)

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/spot/tickers", params={"currency_pair": symbol})
        data = payload[0] if isinstance(payload, list) and payload else payload
        return Ticker(
            symbol=symbol,
            bid=float(data.get("highest_bid", 0.0)),
            ask=float(data.get("lowest_ask", 0.0)),
            last=float(data.get("last", 0.0)),
            volume_24h=float(data.get("base_volume", 0.0)),
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []
