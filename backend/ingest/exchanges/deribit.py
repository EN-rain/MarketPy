"""Deribit adapter for options and perpetual derivatives."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, OptionContract, OrderBook, Position, Ticker, Trade


class DeribitAdapter(ExchangeAdapter):
    websocket_url = "wss://www.deribit.com/ws/api/v2"
    rest_base_url = "https://www.deribit.com/api/v2"

    def __init__(self, *, rest_client: Any | None = None, stream_factory: Any | None = None) -> None:
        super().__init__("deribit", rate_limit_per_second=8)
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
            result = payload.get("result", payload)
            yield OrderBook(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                bids=[(float(p), float(s)) for p, s in result.get("bids", [])],
                asks=[(float(p), float(s)) for p, s in result.get("asks", [])],
            )

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            row = payload.get("result", payload)
            yield Trade(
                symbol=symbol,
                trade_id=str(row.get("trade_id", row.get("tradeId", ""))),
                price=float(row.get("price", 0.0)),
                quantity=float(row.get("amount", 0.0)),
                side=str(row.get("direction", "buy")).lower(),
                timestamp=datetime.now(UTC),
            )

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        return await self._rest_client.post("/private/buy", payload=order)

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/public/ticker", params={"instrument_name": symbol})
        data = payload.get("result", payload)
        return Ticker(
            symbol=symbol,
            bid=float(data.get("best_bid_price", 0.0)),
            ask=float(data.get("best_ask_price", 0.0)),
            last=float(data.get("last_price", 0.0)),
            volume_24h=float(data.get("stats", {}).get("volume", 0.0)),
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []

    async def get_option_chain(self, underlying: str) -> list[OptionContract]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get(
            "/public/get_instruments",
            params={"currency": underlying.upper(), "kind": "option", "expired": False},
        )
        rows = payload.get("result", payload.get("data", []))
        chain: list[OptionContract] = []
        for row in rows:
            expiry_ts = row.get("expiration_timestamp", 0)
            chain.append(
                OptionContract(
                    symbol=str(row.get("instrument_name")),
                    underlying=underlying.upper(),
                    strike=float(row.get("strike", 0.0)),
                    expiry=datetime.fromtimestamp(float(expiry_ts) / 1000, tz=UTC),
                    option_type=str(row.get("option_type", "call")),
                    mark_price=float(row.get("mark_price", 0.0)),
                    implied_volatility=float(row.get("mark_iv", 0.0)),
                )
            )
        return chain
