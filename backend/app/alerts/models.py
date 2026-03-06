"""Alerting Hub data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ConditionType(StrEnum):
    PRICE = "PRICE"
    VOLUME = "VOLUME"
    VOLATILITY = "VOLATILITY"


class Operator(StrEnum):
    GT = "GT"
    LT = "LT"
    EQ = "EQ"
    CROSSES_ABOVE = "CROSSES_ABOVE"
    CROSSES_BELOW = "CROSSES_BELOW"


@dataclass(frozen=True)
class AlertCondition:
    id: str
    market_id: str
    condition_type: ConditionType
    operator: Operator
    threshold: float
    cooldown_seconds: float
    channels: list[str] = field(default_factory=lambda: ["webhook"])
    enabled: bool = True


@dataclass(frozen=True)
class TriggeredAlert:
    condition_id: str
    market_id: str
    condition_type: ConditionType
    operator: Operator
    threshold: float
    observed_value: float
    triggered_at: datetime
    channels: list[str]
