"""Coinbase exchange adapter built on the normalized exchange base layer."""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, OrderBook, Position, Ticker, Trade


StreamFactory = Callable[[str, str], AsyncIterator[dict[str, Any]]]


class CoinbaseAdapter(ExchangeAdapter):
    websocket_url = "wss://ws-feed.exchange.coinbase.com"
    rest_base_url = "https://api.exchange.coinbase.com"

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        rest_client: Any | None = None,
        stream_factory: StreamFactory | None = None,
    ) -> None:
        super().__init__("coinbase", rate_limit_per_second=10)
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self._rest_client = rest_client
        self._stream_factory = stream_factory

    async def connect(self) -> None:
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    def auth_headers(self, method: str, request_path: str, body: str, timestamp: str) -> dict[str, str]:
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        secret = base64.b64decode(self.api_secret.encode("utf-8"))
        signature = base64.b64encode(hmac.new(secret, message.encode("utf-8"), hashlib.sha256).digest()).decode("utf-8")
        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-PASSPHRASE": self.passphrase,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-SIGN": signature,
        }

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for order book subscriptions")
        async for payload in self._stream_factory("order_book", symbol):
            self.health.mark_heartbeat()
            yield OrderBook(
                symbol=symbol,
                timestamp=datetime.fromisoformat(payload["time"].replace("Z", "+00:00")),
                bids=[(float(price), float(size)) for price, size in payload.get("bids", [])],
                asks=[(float(price), float(size)) for price, size in payload.get("asks", [])],
            )

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            self.health.mark_heartbeat()
            yield Trade(
                symbol=symbol,
                trade_id=str(payload["trade_id"]),
                price=float(payload["price"]),
                quantity=float(payload["size"]),
                side=str(payload["side"]),
                timestamp=datetime.fromisoformat(payload["time"].replace("Z", "+00:00")),
            )

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        body = str(order)
        timestamp = str(int(datetime.now(UTC).timestamp()))
        headers = self.auth_headers("POST", "/orders", body, timestamp)
        await self.rate_limiter.acquire()
        return await self._rest_client.post("/orders", headers=headers, content=body)

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get(f"/products/{symbol}/ticker")
        return Ticker(
            symbol=symbol,
            bid=float(payload.get("bid", 0.0)) if payload.get("bid") is not None else None,
            ask=float(payload.get("ask", 0.0)) if payload.get("ask") is not None else None,
            last=float(payload.get("price", 0.0)) if payload.get("price") is not None else None,
            volume_24h=float(payload.get("volume", 0.0)) if payload.get("volume") is not None else None,
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get("/accounts")
        return [
            Balance(
                asset=item["currency"],
                free=float(item.get("available", 0.0)),
                locked=max(float(item.get("balance", 0.0)) - float(item.get("available", 0.0)), 0.0),
                total=float(item.get("balance", 0.0)),
            )
            for item in payload
        ]
