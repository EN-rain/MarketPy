"""Pydantic domain models for portfolio, positions, and trades."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TradeAction(str, Enum):
    BUY_YES = "BUY_YES"
    SELL_YES = "SELL_YES"
    BUY_NO = "BUY_NO"
    SELL_NO = "SELL_NO"


class Trade(BaseModel):
    """A single executed trade."""

    id: str
    timestamp: datetime
    market_id: str
    action: TradeAction
    price: float  # fill price
    size: float  # number of shares
    fee: float = 0.0
    strategy: str = "manual"
    edge: float | None = None  # predicted edge at time of trade
    pnl: float | None = None  # realized PnL if closing


class Position(BaseModel):
    """Current position in a market."""

    market_id: str
    side: str = "YES"  # YES or NO
    size: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return self.size * self.current_price

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl


class EquityPoint(BaseModel):
    """Single point on the equity curve."""

    timestamp: datetime
    cash: float
    positions_value: float
    total_equity: float
    drawdown: float = 0.0


class Portfolio(BaseModel):
    """Full portfolio state."""

    cash: float = 10000.0
    initial_cash: float = 10000.0
    positions: dict[str, Position] = Field(default_factory=dict)
    trades: list[Trade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    total_fees_paid: float = 0.0

    @property
    def positions_value(self) -> float:
        return sum(pos.market_value for pos in self.positions.values())

    @property
    def total_equity(self) -> float:
        return self.cash + self.positions_value

    @property
    def total_pnl(self) -> float:
        return self.total_equity - self.initial_cash

    @property
    def realized_pnl(self) -> float:
        return sum(t.pnl for t in self.trades if t.pnl is not None)

    @property
    def total_pnl_pct(self) -> float:
        if self.initial_cash == 0:
            return 0.0
        return (self.total_pnl / self.initial_cash) * 100

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        return max(pt.drawdown for pt in self.equity_curve)

    @property
    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return 0.0
        wins = sum(1 for t in closed if t.pnl > 0)
        return wins / len(closed)
