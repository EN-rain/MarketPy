"""Uniswap V3 adapter with pool and swap helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from .base import Balance, ExchangeAdapter, OrderBook, Position, Ticker, Trade


class UniswapAdapter(ExchangeAdapter):
    websocket_url = "wss://mainnet.infura.io/ws/v3/uniswap"
    rest_base_url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"

    def __init__(self, *, web3_client: Any | None = None, pools: dict[str, dict[str, float]] | None = None) -> None:
        super().__init__("uniswap", rate_limit_per_second=5)
        self._web3_client = web3_client
        self._pools = pools or {}

    async def connect(self) -> None:
        self.health.mark_connected()

    async def disconnect(self) -> None:
        self.health.mark_disconnected()

    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        pool = self._pools.get(symbol, {"bid": 0.0, "ask": 0.0, "liquidity": 0.0})
        yield OrderBook(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            bids=[(float(pool["bid"]), float(pool["liquidity"]))],
            asks=[(float(pool["ask"]), float(pool["liquidity"]))],
        )

    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        pool = self._pools.get(symbol, {"mid": 0.0})
        yield Trade(
            symbol=symbol,
            trade_id=f"{symbol}-swap",
            price=float(pool.get("mid", 0.0)),
            quantity=1.0,
            side="buy",
            timestamp=datetime.now(UTC),
        )

    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        pool = self._pools.get(order["symbol"], {"mid": 0.0, "slippage_bps": 25.0})
        slippage_bps = float(pool.get("slippage_bps", 25.0))
        if slippage_bps > float(order.get("max_slippage_bps", 50.0)):
            return {"status": "rejected", "reason": "slippage_protection"}
        return {
            "status": "filled",
            "filled_size": float(order.get("size", 0.0)),
            "execution_price": float(pool.get("mid", 0.0)),
            "gas_used": 150_000,
        }

    async def get_ticker(self, symbol: str) -> Ticker:
        pool = self._pools.get(symbol, {"bid": 0.0, "ask": 0.0, "mid": 0.0, "volume_24h": 0.0})
        return Ticker(
            symbol=symbol,
            bid=float(pool.get("bid", 0.0)),
            ask=float(pool.get("ask", 0.0)),
            last=float(pool.get("mid", 0.0)),
            volume_24h=float(pool.get("volume_24h", 0.0)),
            timestamp=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_balances(self) -> list[Balance]:
        return []

    async def get_liquidity_pool(self, symbol: str) -> dict[str, float]:
        return {key: float(value) for key, value in self._pools.get(symbol, {}).items()}
