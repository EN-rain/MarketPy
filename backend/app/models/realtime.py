"""Data models for enhanced realtime updates system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class UpdatePriority(Enum):
    """Priority classification for market updates."""
    CRITICAL = "CRITICAL"
    NON_CRITICAL = "NON_CRITICAL"


@dataclass
class RealtimeMarketUpdate:
    """Enhanced market update with priority classification and metadata.
    
    This is a specialized version of MarketUpdate used by the realtime system
    for priority classification and batching. For the canonical market update
    model, use backend.app.models.market.MarketUpdate.
    """
    market_id: str
    timestamp: datetime
    event_type: str
    data: dict[str, Any]

    # Pricing data
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    spread: float | None = None
    last_trade: float | None = None

    # Priority classification
    priority: UpdatePriority = UpdatePriority.NON_CRITICAL

    # Metadata
    sequence_number: int = 0
    processing_latency_ms: float = 0.0


@dataclass
class BatchMetadata:
    """Metadata about a batched message."""
    update_count: int
    time_range_ms: float
    first_timestamp: datetime
    last_timestamp: datetime


@dataclass
class BatchedMessage:
    """Container for batched market updates."""
    market_id: str
    updates: list[RealtimeMarketUpdate]
    batch_metadata: BatchMetadata
    timestamp: datetime
    type: str = "batched_update"


@dataclass
class ConnectionMetrics:
    """Health metrics for a WebSocket connection."""
    client_id: str
    connected_at: datetime
    connection_duration_seconds: float
    messages_sent: int
    messages_failed: int
    messages_dropped: int
    average_latency_ms: float
    is_slow: bool
    last_activity: datetime


@dataclass
class ProcessingMetrics:
    """Performance metrics for market update processing."""
    market_id: str
    updates_processed: int
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    errors: int
    last_update: datetime


@dataclass
class PreviousMarketState:
    """Previous market state for comparison in UpdatePrioritizer."""
    market_id: str
    last_price: float | None = None
    last_bid: float | None = None
    last_ask: float | None = None
    last_volume: float | None = None
    last_update: datetime | None = None
    price_history: list[float] = field(default_factory=list)
