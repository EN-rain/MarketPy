"""Automation Hub data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    PLACE_ORDER = "PLACE_ORDER"
    CLOSE_POSITION = "CLOSE_POSITION"
    CANCEL_ORDERS = "CANCEL_ORDERS"


class ActionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float
    max_position_notional: float
    max_daily_loss: float
    allowed_markets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AutomatedAction:
    id: str
    market_id: str
    action_type: ActionType
    parameters: dict[str, Any]
    risk_limits: RiskLimits
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ActionLogEntry:
    action_id: str
    action_type: ActionType
    market_id: str
    status: ActionStatus
    message: str
    timestamp: datetime
