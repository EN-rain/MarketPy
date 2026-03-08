"""Bybit exchange adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, MarginAccount, OptionContract, OrderBook, PerpetualPosition, Position, Ticker, Trade


StreamFactory = Callable[[str, str], AsyncIterator[dict[str, Any]]]


class BybitAdapter(ExchangeAdapter):
    websocket_url = "wss://stream.bybit.com/v5/public/linear"
    rest_base_url = "https://api.bybit.com"

    def __init__(self, *, rest_client: Any | None = None, stream_factory: StreamFactory | None = None, market_type: str = "linear") -> None:
        super().__init__("bybit", rate_limit_per_second=10)
        self._rest_client = rest_client
        self._stream_factory = stream_factory
        self.market_type = market_type

    async def connect(self) -> None:
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for order book subscriptions")
        async for payload in self._stream_factory("order_book", symbol):
            yield OrderBook(symbol=symbol, timestamp=datetime.now(UTC), bids=[(float(p), float(s)) for p, s in payload.get("b", [])], asks=[(float(p), float(s)) for p, s in payload.get("a", [])])

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if self._stream_factory is None:
            raise RuntimeError("stream_factory is required for trade subscriptions")
        async for payload in self._stream_factory("trade", symbol):
            yield Trade(symbol=symbol, trade_id=str(payload["i"]), price=float(payload["p"]), quantity=float(payload["v"]), side=str(payload["S"]).lower(), timestamp=datetime.now(UTC))

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for order placement")
        await self.rate_limiter.acquire()
        return await self._rest_client.post("/v5/order/create", payload={**order, "category": self.market_type})

    async def get_ticker(self, symbol: str) -> Ticker:
        if self._rest_client is None:
            raise RuntimeError("rest_client is required for ticker requests")
        payload = await self._rest_client.get("/v5/market/tickers", params={"category": self.market_type, "symbol": symbol})
        entry = payload["result"]["list"][0]
        return Ticker(symbol=symbol, bid=float(entry["bid1Price"]), ask=float(entry["ask1Price"]), last=float(entry["lastPrice"]), volume_24h=float(entry["volume24h"]), timestamp=datetime.now(UTC))

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []

    async def get_funding_rates(self, symbols: list[str]) -> dict[str, float]:
        if self._rest_client is None:
            return {symbol: 0.0 for symbol in symbols}
        results: dict[str, float] = {}
        for symbol in symbols:
            payload = await self._rest_client.get(
                "/v5/market/funding/history",
                params={"category": self.market_type, "symbol": symbol},
            )
            history = payload.get("result", {}).get("list", [])
            results[symbol] = float(history[0]["fundingRate"]) if history else 0.0
        return results

    async def get_perpetual_positions(self) -> list[PerpetualPosition]:
        if self._rest_client is None:
            return []
        payload = await self._rest_client.get("/v5/position/list", params={"category": self.market_type})
        positions: list[PerpetualPosition] = []
        for entry in payload.get("result", {}).get("list", []):
            size = float(entry.get("size", 0.0))
            if size == 0:
                continue
            mark_price = float(entry.get("markPrice", entry.get("avgPrice", 0.0)))
            entry_price = float(entry.get("avgPrice", mark_price))
            maintenance_margin = float(entry.get("positionIM", 0.0))
            equity = max(float(entry.get("positionBalance", maintenance_margin or 1.0)), 1e-9)
            positions.append(
                PerpetualPosition(
                    symbol=str(entry.get("symbol")),
                    side=str(entry.get("side", "Buy")).lower(),
                    quantity=size,
                    entry_price=entry_price,
                    mark_price=mark_price,
                    leverage=float(entry.get("leverage", 1.0)),
                    unrealized_pnl=float(entry.get("unrealisedPnl", 0.0)),
                    funding_rate=float(entry.get("cumRealisedPnl", 0.0)),
                    margin_ratio=equity / max(maintenance_margin, 1e-9),
                    maintenance_margin=maintenance_margin,
                    notional_value=mark_price * size,
                )
            )
        return positions

    async def get_margin_account(self) -> MarginAccount:
        if self._rest_client is None:
            return await super().get_margin_account()
        payload = await self._rest_client.get("/v5/account/wallet-balance", params={"accountType": "UNIFIED"})
        accounts = payload.get("result", {}).get("list", [])
        if not accounts:
            return await super().get_margin_account()
        account = accounts[0]
        equity = float(account.get("totalEquity", 0.0))
        maintenance = max(float(account.get("totalMaintenanceMargin", 0.0)), 1e-9)
        used = float(account.get("totalInitialMargin", 0.0))
        free = float(account.get("totalAvailableBalance", max(equity - used, 0.0)))
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
            "/v5/market/instruments-info",
            params={"category": "option", "baseCoin": underlying},
        )
        contracts: list[OptionContract] = []
        for entry in payload.get("result", {}).get("list", []):
            symbol = str(entry.get("symbol"))
            parts = symbol.split("-")
            strike = float(parts[-2]) if len(parts) >= 2 else 0.0
            option_type = parts[-1].lower() if parts else "call"
            expiry_token = parts[-3] if len(parts) >= 3 else "30DEC26"
            try:
                expiry = datetime.strptime(expiry_token, "%d%b%y").replace(tzinfo=UTC)
            except ValueError:
                expiry = datetime.now(UTC)
            contracts.append(
                OptionContract(
                    symbol=symbol,
                    underlying=underlying,
                    strike=strike,
                    expiry=expiry,
                    option_type="call" if option_type.startswith("c") else "put",
                    mark_price=float(entry.get("markPrice", 0.0)),
                    implied_volatility=float(entry.get("markIv", 0.0)),
                )
            )
        return contracts
