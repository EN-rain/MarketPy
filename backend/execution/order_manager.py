"""Order lifecycle management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class OrderStatus(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(slots=True)
class OrderRecord:
    order_id: str
    market_id: str
    side: str
    size: float
    order_type: str
    status: OrderStatus
    limit_price: float | None = None
    trail_percent: float | None = None
    trail_amount: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class OrderManager:
    """Tracks and validates order lifecycle state."""

    SUPPORTED_TYPES = {
        "limit",
        "market",
        "stop_loss",
        "take_profit",
        "trailing_stop",
        "bracket",
        "iceberg",
        "twap",
        "vwap",
    }

    def __init__(self) -> None:
        self.orders: dict[str, OrderRecord] = {}

    def place_order(
        self,
        *,
        market_id: str,
        side: str,
        size: float,
        order_type: str,
        limit_price: float | None = None,
        trail_percent: float | None = None,
        trail_amount: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OrderRecord:
        if size <= 0:
            raise ValueError("order size must be positive")
        if order_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"unsupported order type: {order_type}")
        if order_type == "limit" and limit_price is None:
            raise ValueError("limit orders require limit_price")
        if order_type == "trailing_stop" and trail_percent is None and trail_amount is None:
            raise ValueError("trailing_stop orders require trail_percent or trail_amount")

        record = OrderRecord(
            order_id=str(uuid4()),
            market_id=market_id,
            side=side.upper(),
            size=float(size),
            order_type=order_type,
            status=OrderStatus.PENDING,
            limit_price=limit_price,
            trail_percent=trail_percent,
            trail_amount=trail_amount,
            metadata=dict(metadata or {}),
        )
        self.orders[record.order_id] = record
        return record

    def cancel_order(self, order_id: str) -> OrderRecord:
        record = self.orders[order_id]
        record.status = OrderStatus.CANCELLED
        record.updated_at = datetime.now(UTC)
        return record

    def modify_order(self, order_id: str, **updates: Any) -> OrderRecord:
        record = self.orders[order_id]
        for key in ("size", "limit_price", "trail_percent", "trail_amount"):
            if key in updates and updates[key] is not None:
                setattr(record, key, updates[key])
        record.updated_at = datetime.now(UTC)
        return record

    def update_status(self, order_id: str, status: OrderStatus) -> OrderRecord:
        record = self.orders[order_id]
        record.status = status
        record.updated_at = datetime.now(UTC)
        return record
