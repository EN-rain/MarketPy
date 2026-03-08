"""Binance exchange adapter built on the normalized exchange base layer."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from .base import Balance, ExchangeAdapter, OrderBook, Position, Ticker, Trade


StreamFactory = Callable[[str, str], AsyncIterator[dict[str, Any]]]


class BinanceAdapter(ExchangeAdapter):
    websocket_url = "wss://stream.binance.com:9443/ws"
    rest_base_url = "https://api.binance.com"

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        rest_client: Any | None = None,
        stream_factory: StreamFactory | None = None,
    ) -> None:
        super().__init__("binance", rate_limit_per_second=10)
        self.api_key = api_key
        self.api_secret = api_secret
        self._rest_client = rest_client
        self._stream_factory = stream_factory

    async def connect(self) -> None:
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    def sign_params(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{query}&signature={signature}"

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for order book subscriptions")
        async for payload in self._stream_factory("order_book", symbol):
            self.health.mark_heartbeat()
            yield self._normalize_order_book(symbol, payload)

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            self.health.mark_heartbeat()
            yield self._normalize_trade(symbol, payload)

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        await self.rate_limiter.acquire()
        signed_query = self.sign_params(order)
        return await self._rest_client.post(
            "/api/v3/order",
            headers={"X-MBX-APIKEY": self.api_key},
            content=signed_query,
        )

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/api/v3/ticker/bookTicker", params={"symbol": symbol})
        return Ticker(
            symbol=symbol,
            bid=float(payload.get("bidPrice", 0.0)) if payload.get("bidPrice") is not None else None,
            ask=float(payload.get("askPrice", 0.0)) if payload.get("askPrice") is not None else None,
            last=float(payload.get("lastPrice", 0.0)) if payload.get("lastPrice") is not None else None,
            volume_24h=float(payload.get("volume", 0.0)) if payload.get("volume") is not None else None,
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get("/api/v3/account")
        positions = payload.get("positions", [])
        return [
            Position(
                symbol=item["symbol"],
                side="long" if float(item.get("positionAmt", 0.0)) >= 0 else "short",
                quantity=abs(float(item.get("positionAmt", 0.0))),
                entry_price=float(item.get("entryPrice", 0.0)),
                mark_price=float(item.get("markPrice", 0.0)) if item.get("markPrice") is not None else None,
                leverage=float(item.get("leverage", 0.0)) if item.get("leverage") is not None else None,
                unrealized_pnl=float(item.get("unRealizedProfit", 0.0)) if item.get("unRealizedProfit") is not None else None,
            )
            for item in positions
        ]

    async def get_balances(self) -> list[Balance]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get("/api/v3/account")
        balances = payload.get("balances", [])
        return [
            Balance(
                asset=item["asset"],
                free=float(item.get("free", 0.0)),
                locked=float(item.get("locked", 0.0)),
                total=float(item.get("free", 0.0)) + float(item.get("locked", 0.0)),
            )
            for item in balances
        ]

    @staticmethod
    def _normalize_order_book(symbol: str, payload: dict[str, Any]) -> OrderBook:
        return OrderBook(
            symbol=symbol,
            timestamp=datetime.fromtimestamp(payload["T"] / 1000, UTC),
            bids=[(float(price), float(size)) for price, size in payload.get("b", [])],
            asks=[(float(price), float(size)) for price, size in payload.get("a", [])],
        )

    @staticmethod
    def _normalize_trade(symbol: str, payload: dict[str, Any]) -> Trade:
        return Trade(
            symbol=symbol,
            trade_id=str(payload["t"]),
            price=float(payload["p"]),
            quantity=float(payload["q"]),
            side="sell" if payload.get("m") else "buy",
            timestamp=datetime.fromtimestamp(payload["T"] / 1000, UTC),
        )
