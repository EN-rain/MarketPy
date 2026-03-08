"""Core domain and conversation models for OpenClaw."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class CommandType(StrEnum):
    PRICE_CHECK = "price_check"
    PLACE_ORDER = "place_order"
    POSITION_QUERY = "position_query"
    RUN_BACKTEST = "run_backtest"
    STRATEGY_EXECUTION = "strategy_execution"
    MARKET_ANALYSIS = "market_analysis"
    CONDITION_ADD = "condition_add"
    CONDITION_LIST = "condition_list"
    CONDITION_REMOVE = "condition_remove"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class MarketCondition:
    condition_id: str = field(default_factory=lambda: f"cond-{uuid4().hex[:12]}")
    user_id: str = ""
    condition_type: str = ""
    symbol: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    action: str = "notify"
    action_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_triggered: datetime | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.user_id:
            errors.append("user_id is required")
        if not self.condition_type:
            errors.append("condition_type is required")
        if not self.symbol:
            errors.append("symbol is required")
        if self.action not in {"notify", "execute_order", "run_analysis"}:
            errors.append("action must be notify, execute_order, or run_analysis")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "user_id": self.user_id,
            "condition_type": self.condition_type,
            "symbol": self.symbol,
            "parameters": self.parameters,
            "action": self.action,
            "action_params": self.action_params,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MarketCondition:
        return cls(
            condition_id=str(payload.get("condition_id") or f"cond-{uuid4().hex[:12]}"),
            user_id=str(payload.get("user_id", "")),
            condition_type=str(payload.get("condition_type", "")),
            symbol=str(payload.get("symbol", "")).upper(),
            parameters=dict(payload.get("parameters", {})),
            action=str(payload.get("action", "notify")),
            action_params=dict(payload.get("action_params", {})),
            enabled=bool(payload.get("enabled", True)),
            last_triggered=_parse_dt(payload.get("last_triggered")),
        )

    def evaluate(self, market_data: dict[str, Any]) -> bool:
        """Evaluate this condition against a normalized market data payload."""
        if not self.enabled:
            return False
        condition_type = self.condition_type.lower()
        price = float(market_data.get("price", 0.0))
        previous_price = float(market_data.get("previous_price", price))
        rsi = float(market_data.get("rsi", 50.0))
        volume = float(market_data.get("volume", 0.0))
        average_volume = float(market_data.get("average_volume", max(volume, 1.0)))

        if condition_type == "price_threshold":
            threshold = float(self.parameters.get("threshold", 0.0))
            direction = str(self.parameters.get("direction", "above")).lower()
            return price >= threshold if direction == "above" else price <= threshold

        if condition_type == "rsi_level":
            level = float(self.parameters.get("level", 50.0))
            direction = str(self.parameters.get("direction", "below")).lower()
            return rsi <= level if direction == "below" else rsi >= level

        if condition_type == "volume_spike":
            multiplier = float(self.parameters.get("multiplier", 2.0))
            return volume >= (average_volume * multiplier)

        if condition_type == "price_change":
            pct_threshold = float(self.parameters.get("pct", 0.0))
            if previous_price <= 0:
                return False
            pct_change = abs((price - previous_price) / previous_price) * 100.0
            return pct_change >= pct_threshold

        return False


@dataclass(slots=True)
class TradingCommand:
    command_type: str
    user_id: str
    symbol: str | None = None
    action: str | None = None
    quantity: float | None = None
    conditions: list[MarketCondition] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_now_utc)
    correlation_id: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.user_id:
            errors.append("user_id is required")
        if not self.command_type:
            errors.append("command_type is required")

        if self.command_type == CommandType.PLACE_ORDER:
            if not self.symbol:
                errors.append("symbol is required for place_order")
            if self.action not in {"buy", "sell"}:
                errors.append("action must be buy or sell for place_order")
            if self.quantity is None or self.quantity <= 0:
                errors.append("quantity must be positive for place_order")

        if self.symbol:
            self.symbol = self.symbol.upper()
        return errors

    def required_params(self) -> list[str]:
        if self.command_type == CommandType.PLACE_ORDER:
            return ["symbol", "action", "quantity"]
        if self.command_type == CommandType.PRICE_CHECK:
            return ["symbol"]
        if self.command_type == CommandType.RUN_BACKTEST:
            return ["strategy_name", "start_date", "end_date"]
        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_type": self.command_type,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "conditions": [condition.to_dict() for condition in self.conditions],
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TradingCommand:
        return cls(
            command_type=str(payload.get("command_type", CommandType.UNKNOWN)),
            user_id=str(payload.get("user_id", "")),
            symbol=(str(payload["symbol"]).upper() if payload.get("symbol") else None),
            action=(str(payload["action"]).lower() if payload.get("action") else None),
            quantity=(float(payload["quantity"]) if payload.get("quantity") is not None else None),
            conditions=[MarketCondition.from_dict(item) for item in payload.get("conditions", [])],
            parameters=dict(payload.get("parameters", {})),
            timestamp=_parse_dt(payload.get("timestamp")) or _now_utc(),
            correlation_id=payload.get("correlation_id"),
        )


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExecutionResult:
        return cls(
            success=bool(payload.get("success")),
            data=payload.get("data"),
            error=payload.get("error"),
            execution_time_ms=float(payload.get("execution_time_ms", 0.0)),
            correlation_id=payload.get("correlation_id"),
            timestamp=_parse_dt(payload.get("timestamp")) or _now_utc(),
        )


@dataclass(slots=True)
class ConversationMessage:
    role: str
    content: str
    user_id: str
    timestamp: datetime = field(default_factory=_now_utc)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConversationMessage:
        return cls(
            role=str(payload.get("role", "user")),
            content=str(payload.get("content", "")),
            user_id=str(payload.get("user_id", "")),
            timestamp=_parse_dt(payload.get("timestamp")) or _now_utc(),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(slots=True)
class UserContext:
    user_id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    last_trade: dict[str, Any] | None = None
    active_strategies: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=_now_utc)

    def add_message(self, message: ConversationMessage, max_messages: int = 50) -> None:
        self.messages.append(message)
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]
        self.updated_at = _now_utc()

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "messages": [message.to_dict() for message in self.messages],
            "preferences": self.preferences,
            "last_trade": self.last_trade,
            "active_strategies": self.active_strategies,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UserContext:
        return cls(
            user_id=str(payload.get("user_id", "")),
            messages=[ConversationMessage.from_dict(item) for item in payload.get("messages", [])],
            preferences=dict(payload.get("preferences", {})),
            last_trade=payload.get("last_trade"),
            active_strategies=list(payload.get("active_strategies", [])),
            updated_at=_parse_dt(payload.get("updated_at")) or _now_utc(),
        )
