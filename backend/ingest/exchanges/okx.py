"""OKX exchange adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, MarginAccount, OptionContract, OrderBook, PerpetualPosition, Position, Ticker, Trade


StreamFactory = Callable[[str, str], AsyncIterator[dict[str, Any]]]


class OKXAdapter(ExchangeAdapter):
    websocket_url = "wss://ws.okx.com:8443/ws/v5/public"
    rest_base_url = "https://www.okx.com"

    def __init__(self, *, rest_client: Any | None = None, stream_factory: StreamFactory | None = None, instrument_type: str = "SPOT") -> None:
        super().__init__("okx", rate_limit_per_second=10)
        self._rest_client = rest_client
        self._stream_factory = stream_factory
        self.instrument_type = instrument_type

    async def connect(self) -> None:
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for order book subscriptions")
        async for payload in self._stream_factory("order_book", symbol):
            entry = payload["data"][0]
            yield OrderBook(symbol=symbol, timestamp=datetime.now(UTC), bids=[(float(p), float(s)) for p, s, *_ in entry.get("bids", [])], asks=[(float(p), float(s)) for p, s, *_ in entry.get("asks", [])])

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            entry = payload["data"][0]
            yield Trade(symbol=symbol, trade_id=str(entry["tradeId"]), price=float(entry["px"]), quantity=float(entry["sz"]), side=str(entry["side"]), timestamp=datetime.now(UTC))

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        await self.rate_limiter.acquire()
        return await self._rest_client.post("/api/v5/trade/order", payload={**order, "instType": self.instrument_type})

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/api/v5/market/ticker", params={"instId": symbol})
        entry = payload["data"][0]
        return Ticker(symbol=symbol, bid=float(entry["bidPx"]), ask=float(entry["askPx"]), last=float(entry["last"]), volume_24h=float(entry["vol24h"]), timestamp=datetime.now(UTC))

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []

    async def get_funding_rates(self, symbols: list[str]) -> dict[str, float]:
        if self._rest_client is None:
            return {symbol: 0.0 for symbol in symbols}
        results: dict[str, float] = {}
        for symbol in symbols:
            payload = await self._rest_client.get("/api/v5/public/funding-rate", params={"instId": symbol})
            data = payload.get("data", [])
            results[symbol] = float(data[0]["fundingRate"]) if data else 0.0
        return results

    async def get_perpetual_positions(self) -> list[PerpetualPosition]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get("/api/v5/account/positions", params={"instType": "SWAP"})
        positions: list[PerpetualPosition] = []
        for entry in payload.get("data", []):
            size = abs(float(entry.get("pos", 0.0)))
            if size == 0:
                continue
            mark_price = float(entry.get("markPx", entry.get("avgPx", 0.0)))
            maintenance = float(entry.get("mmr", 0.0))
            margin = max(float(entry.get("margin", maintenance or 1.0)), 1e-9)
            positions.append(
                PerpetualPosition(
                    symbol=str(entry.get("instId")),
                    side="long" if float(entry.get("pos", 0.0)) >= 0 else "short",
                    quantity=size,
                    entry_price=float(entry.get("avgPx", mark_price)),
                    mark_price=mark_price,
                    leverage=float(entry.get("lever", 1.0)),
                    unrealized_pnl=float(entry.get("upl", 0.0)),
                    funding_rate=float(entry.get("fundingFee", 0.0)),
                    margin_ratio=margin / max(maintenance, 1e-9),
                    maintenance_margin=maintenance,
                    notional_value=mark_price * size,
                )
            )
        return positions

    async def get_margin_account(self) -> MarginAccount:
        if self._rest_client is None:
            return await super().get_margin_account()
        payload = await self._rest_client.get("/api/v5/account/balance")
        data = payload.get("data", [])
        if not data:
            return await super().get_margin_account()
        account = data[0]
        equity = float(account.get("totalEq", 0.0))
        maintenance = max(float(account.get("mmr", 0.0)), 1e-9)
        used = float(account.get("imr", 0.0))
        free = float(account.get("adjEq", max(equity - used, 0.0)))
        return MarginAccount(
            equity=equity,
            used_margin=used,
            free_margin=free,
            margin_ratio=equity / maintenance,
            maintenance_margin=maintenance,
        )

    async def get_option_chain(self, underlying: str) -> list[OptionContract]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get(
            "/api/v5/public/instruments",
            params={"instType": "OPTION", "uly": underlying},
        )
        contracts: list[OptionContract] = []
        for entry in payload.get("data", []):
            expiry_ms = int(entry.get("expTime", 0))
            expiry = datetime.fromtimestamp(expiry_ms / 1000, tz=UTC) if expiry_ms else datetime.now(UTC)
            contracts.append(
                OptionContract(
                    symbol=str(entry.get("instId")),
                    underlying=underlying,
                    strike=float(entry.get("stk", 0.0)),
                    expiry=expiry,
                    option_type=str(entry.get("optType", "C")).lower().replace("c", "call").replace("p", "put"),
                    mark_price=float(entry.get("markPx", 0.0)),
                    implied_volatility=float(entry.get("markVol", 0.0)),
                )
            )
        return contracts
