"""Market replay engine for historical simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    size: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    timestamp: datetime
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


@dataclass(frozen=True)
class TradeTick:
    timestamp: datetime
    price: float
    size: float
    side: str


class MarketReplayEngine:
    """Replays historical books/trades with controllable playback and fills."""

    def __init__(
        self,
        orderbooks: list[OrderBookSnapshot] | None = None,
        trades: list[TradeTick] | None = None,
    ):
        self.orderbooks = orderbooks or []
        self.trades = trades or []
        self.speed = 1.0
        self._orderbook_cursor = 0
        self._trade_cursor = 0
        # Backward-compatible alias for any code that introspects internal state.
        self._cursor = 0
        self._paused = True

    def start_replay(self, speed: float = 1.0) -> None:
        self.speed = max(0.1, min(100.0, speed))
        self._paused = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def seek(self, index: int) -> None:
        self._orderbook_cursor = self._clamp_cursor(index, len(self.orderbooks))
        self._trade_cursor = self._clamp_cursor(index, len(self.trades))
        self._cursor = self._orderbook_cursor

    def stream_orderbook(self, limit: int | None = None) -> list[OrderBookSnapshot]:
        if self._paused:
            return []
        chunk = self._chunk_size(limit)
        start = self._orderbook_cursor
        end = min(len(self.orderbooks), start + chunk)
        self._orderbook_cursor = end
        self._cursor = self._orderbook_cursor
        return self.orderbooks[start:end]

    def stream_trades(self, limit: int | None = None) -> list[TradeTick]:
        if self._paused:
            return []
        chunk = self._chunk_size(limit)
        start = self._trade_cursor
        end = min(len(self.trades), start + chunk)
        self._trade_cursor = end
        return self.trades[start:end]

    def simulate_fill(self, side: str, size: float, orderbook: OrderBookSnapshot) -> float:
        levels = orderbook.asks if side.upper() == "BUY" else orderbook.bids
        remaining = size
        notional = 0.0
        for level in levels:
            take = min(remaining, level.size)
            notional += take * level.price
            remaining -= take
            if remaining <= 0:
                break
        if remaining > 0:
            worst_price = levels[-1].price if levels else 0.0
            notional += remaining * worst_price
        return 0.0 if size <= 0 else notional / size

    def estimated_replay_duration_seconds(
        self, event_count: int, base_rate_per_second: float = 100.0
    ) -> float:
        rate = max(1e-6, base_rate_per_second * self.speed)
        return event_count / rate

    def _chunk_size(self, limit: int | None) -> int:
        if limit is not None:
            return max(1, limit)
        return max(1, int(round(self.speed)))

    def _clamp_cursor(self, index: int, total: int) -> int:
        return max(0, min(index, total))


def build_sample_replay(count: int = 120) -> MarketReplayEngine:
    now = datetime.now(UTC)
    orderbooks: list[OrderBookSnapshot] = []
    trades: list[TradeTick] = []
    for i in range(count):
        mid = 100 + (i * 0.01)
        orderbooks.append(
            OrderBookSnapshot(
                timestamp=now,
                bids=[
                    OrderBookLevel(price=mid - 0.05, size=10),
                    OrderBookLevel(price=mid - 0.1, size=20),
                ],
                asks=[
                    OrderBookLevel(price=mid + 0.05, size=10),
                    OrderBookLevel(price=mid + 0.1, size=20),
                ],
            )
        )
        trades.append(TradeTick(timestamp=now, price=mid, size=1 + (i % 3), side="BUY"))
    return MarketReplayEngine(orderbooks=orderbooks, trades=trades)
