"""Canonical domain models for market data.

This module provides the single source of truth for market update data structures.
All other modules should import from this location to prevent type drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class OrderBookSnapshot:
    """Snapshot of orderbook state at a point in time.
    
    This is the canonical orderbook representation. Use this dataclass
    for all orderbook data to ensure consistency across modules.
    """
    token_id: str
    timestamp: datetime
    best_bid: float | None
    best_ask: float | None
    mid: float | None
    spread: float | None
    bids: list[tuple[float, float]] = field(default_factory=list)  # (price, size)
    asks: list[tuple[float, float]] = field(default_factory=list)  # (price, size)


@dataclass
class MarketUpdate:
    """Canonical market update data structure.
    
    This is the single source of truth for market update data.
    All modules should import this class from backend.app.models.market
    to prevent type drift between modules.
    
    Attributes:
        market_id: Unique identifier for the market
        timestamp: Time of the update
        mid: Mid price (average of bid and ask)
        bid: Best bid price
        ask: Best ask price
        last_trade: Last trade price
        orderbook: Full orderbook snapshot (optional)
        volume_24h: 24-hour trading volume (optional)
        change_24h_pct: 24-hour price change percentage (optional)
    """
    market_id: str
    timestamp: datetime
    mid: float | None
    bid: float | None
    ask: float | None
    last_trade: float | None
    orderbook: OrderBookSnapshot | None
    volume_24h: float | None = None
    change_24h_pct: float | None = None


@dataclass
class MarketMetrics:
    """Market-cap and supply metrics from external providers."""

    coin_id: str
    volume_24h: float
    market_cap: float
    circulating_supply: float
    total_supply: float | None
    max_supply: float | None
    timestamp: datetime


@dataclass
class OnChainMetrics:
    """Bitcoin on-chain metrics snapshot."""

    timestamp: datetime
    mempool_size_mb: float
    fee_rate_sat_vb: float
    hash_rate_eh_s: float
    difficulty: float | None = None


@dataclass
class RepoActivity:
    """GitHub repository activity metrics snapshot."""

    repo: str
    commit_count_24h: int
    contributor_count: int
    open_issues_count: int
    timestamp: datetime


@dataclass
class SentimentScore:
    """Sentiment score snapshot for crypto discussions."""

    source: str
    score: float  # range [-1.0, 1.0]
    positive_count: int
    negative_count: int
    neutral_count: int
    timestamp: datetime


# Legacy Pydantic models for backward compatibility
class OrderBookLevel(BaseModel):
    """Legacy Pydantic model for orderbook levels.
    
    Deprecated: Use OrderBookSnapshot dataclass instead.
    """
    price: float
    size: float


class OrderBookSnapshotPydantic(BaseModel):
    """Legacy Pydantic model for orderbook snapshots.
    
    Deprecated: Use OrderBookSnapshot dataclass instead.
    """
    token_id: str
    timestamp: datetime
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    best_bid: float | None = None
    best_ask: float | None = None
    mid: float | None = None
    spread: float | None = None

    def model_post_init(self, __context: object) -> None:
        if self.bids and self.best_bid is None:
            self.best_bid = max(lvl.price for lvl in self.bids)
        if self.asks and self.best_ask is None:
            self.best_ask = min(lvl.price for lvl in self.asks)
        if self.best_bid is not None and self.best_ask is not None:
            if self.mid is None:
                self.mid = (self.best_bid + self.best_ask) / 2
            if self.spread is None:
                self.spread = self.best_ask - self.best_bid


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    mid: float
    bid: float
    ask: float
    spread: float
    volume: float = 0.0
    trade_count: int = 0


class MarketInfo(BaseModel):
    """Static market metadata."""

    condition_id: str  # canonical market identifier (e.g., BTCUSDT)
    question: str
    token_id_yes: str  # primary tradable symbol id
    token_id_no: str | None = None
    end_date: datetime | None = None
    active: bool = True
    description: str = ""


class MarketState(BaseModel):
    """Live market state combining metadata + latest prices."""

    info: MarketInfo
    orderbook: OrderBookSnapshotPydantic | None = None
    candles: list[Candle] = Field(default_factory=list)
    last_trade_price: float | None = None
    time_to_close: float | None = None  # seconds until market close
    updated_at: datetime | None = None
