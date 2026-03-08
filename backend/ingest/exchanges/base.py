"""Base exchange adapter architecture for normalized multi-exchange support."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class OrderBook:
    symbol: str
    timestamp: datetime
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]


@dataclass(slots=True)
class Trade:
    symbol: str
    trade_id: str
    price: float
    quantity: float
    side: str
    timestamp: datetime


@dataclass(slots=True)
class Ticker:
    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    volume_24h: float | None
    timestamp: datetime


@dataclass(slots=True)
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    mark_price: float | None
    leverage: float | None
    unrealized_pnl: float | None


@dataclass(slots=True)
class PerpetualPosition(Position):
    funding_rate: float | None = None
    margin_ratio: float | None = None
    maintenance_margin: float | None = None
    notional_value: float | None = None


@dataclass(slots=True)
class OptionContract:
    symbol: str
    underlying: str
    strike: float
    expiry: datetime
    option_type: str
    mark_price: float
    implied_volatility: float


@dataclass(slots=True)
class MarginAccount:
    equity: float
    used_margin: float
    free_margin: float
    margin_ratio: float
    maintenance_margin: float


@dataclass(slots=True)
class Balance:
    asset: str
    free: float
    locked: float
    total: float


@dataclass(slots=True)
class ExchangeConnectionHealth:
    connected: bool = False
    last_heartbeat_at: datetime | None = None
    reconnect_attempts: int = 0
    last_error: str | None = None

    def mark_connected(self) -> None:
        self.connected = True
        self.last_error = None
        self.last_heartbeat_at = datetime.now(UTC)

    def mark_heartbeat(self) -> None:
        self.last_heartbeat_at = datetime.now(UTC)

    def mark_disconnected(self, error: str | None = None) -> None:
        self.connected = False
        self.last_error = error
        self.reconnect_attempts += 1


@dataclass(slots=True)
class TokenBucketRateLimiter:
    rate: float
    capacity: int
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(float(self.capacity), self._tokens + (elapsed * self.rate))

    async def acquire(self, tokens: int = 1) -> None:
        while True:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            needed = tokens - self._tokens
            await asyncio.sleep(max(needed / self.rate, 0.001))


class ExchangeAdapter(ABC):
    """Abstract base class for normalized exchange connectivity."""

    def __init__(self, exchange_name: str, *, rate_limit_per_second: int = 10) -> None:
        self.exchange_name = exchange_name
        self.health = ExchangeConnectionHealth()
        self.rate_limiter = TokenBucketRateLimiter(
            rate=float(rate_limit_per_second),
            capacity=rate_limit_per_second,
        )

    @staticmethod
    def reconnection_delays(max_attempts: int = 5) -> list[int]:
        return [2**attempt for attempt in range(max_attempts)]

    async def connect_with_retries(self, attempts: int = 5) -> None:
        last_error: Exception | None = None
        for delay in self.reconnection_delays(attempts):
            try:
                await self.connect()
                self.health.mark_connected()
                return
            except Exception as exc:
                last_error = exc
                self.health.mark_disconnected(str(exc))
                await asyncio.sleep(delay)
        if last_error is None:
            raise RuntimeError("Failed to connect without an exception")
        raise last_error

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the exchange."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the exchange."""

    @abstractmethod
    async def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        """Subscribe to normalized order book updates."""

    @abstractmethod
    async def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        """Subscribe to normalized trade updates."""

    @abstractmethod
    async def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Place an order on the exchange."""

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Fetch normalized ticker data."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Fetch open positions."""

    @abstractmethod
    async def get_balances(self) -> list[Balance]:
        """Fetch account balances."""

    async def get_funding_rates(self, symbols: list[str]) -> dict[str, float]:
        return {symbol: 0.0 for symbol in symbols}

    async def get_perpetual_positions(self) -> list[PerpetualPosition]:
        positions = await self.get_positions()
        perpetual_positions: list[PerpetualPosition] = []
        for position in positions:
            perpetual_positions.append(
                PerpetualPosition(
                    symbol=position.symbol,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    mark_price=position.mark_price,
                    leverage=position.leverage,
                    unrealized_pnl=position.unrealized_pnl,
                    notional_value=(position.mark_price or position.entry_price) * position.quantity,
                )
            )
        return perpetual_positions

    async def get_margin_account(self) -> MarginAccount:
        balances = await self.get_balances()
        total_equity = float(sum(balance.total for balance in balances))
        locked = float(sum(balance.locked for balance in balances))
        maintenance = max(total_equity * 0.1, 0.0)
        free_margin = max(total_equity - locked, 0.0)
        margin_ratio = (total_equity / maintenance) if maintenance > 0 else float("inf")
        return MarginAccount(
            equity=total_equity,
            used_margin=locked,
            free_margin=free_margin,
            margin_ratio=margin_ratio,
            maintenance_margin=maintenance,
        )

    async def get_option_chain(self, underlying: str) -> list[OptionContract]:
        return []
