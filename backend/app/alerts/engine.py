"""Alert evaluation and notification dispatch engine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime

from .models import AlertCondition, ConditionType, Operator, TriggeredAlert

Notifier = Callable[[TriggeredAlert], Awaitable[bool]]


class AlertEngine:
    """Evaluates alert conditions in real-time with cooldown protection."""

    def __init__(self):
        self.conditions: dict[str, AlertCondition] = {}
        self.last_trigger_at: dict[str, datetime] = {}
        self.previous_values: dict[str, float] = {}
        self.notifiers: dict[str, Notifier] = {}

    def register_condition(self, condition: AlertCondition) -> None:
        self.conditions[condition.id] = condition

    def remove_condition(self, condition_id: str) -> None:
        self.conditions.pop(condition_id, None)
        self.last_trigger_at.pop(condition_id, None)
        self.previous_values.pop(condition_id, None)

    def register_notifier(self, channel: str, notifier: Notifier) -> None:
        self.notifiers[channel] = notifier

    @staticmethod
    def _extract_value(
        condition: AlertCondition, update: Mapping[str, float | int | None]
    ) -> float | None:
        if condition.condition_type == ConditionType.PRICE:
            for key in ("mid", "last_trade", "price"):
                value = update.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
            return None
        if condition.condition_type == ConditionType.VOLUME:
            value = update.get("volume_24h")
            return float(value) if isinstance(value, (int, float)) else None
        if condition.condition_type == ConditionType.VOLATILITY:
            for key in ("volatility", "change_24h_pct"):
                value = update.get(key)
                if isinstance(value, (int, float)):
                    return abs(float(value))
            return None
        return None

    def _passes_condition(self, condition: AlertCondition, value: float) -> bool:
        if condition.operator == Operator.GT:
            return value > condition.threshold
        if condition.operator == Operator.LT:
            return value < condition.threshold
        if condition.operator == Operator.EQ:
            return value == condition.threshold

        prev = self.previous_values.get(condition.id)
        if prev is None:
            return False
        if condition.operator == Operator.CROSSES_ABOVE:
            return prev <= condition.threshold < value
        if condition.operator == Operator.CROSSES_BELOW:
            return prev >= condition.threshold > value
        return False

    def _cooldown_active(self, condition: AlertCondition, now: datetime) -> bool:
        last = self.last_trigger_at.get(condition.id)
        if last is None:
            return False
        elapsed = (now - last).total_seconds()
        return elapsed < condition.cooldown_seconds

    async def evaluate_conditions(
        self, market_id: str, update: Mapping[str, float | int | None], now: datetime | None = None
    ) -> list[TriggeredAlert]:
        current_time = now or datetime.now(UTC)
        triggered: list[TriggeredAlert] = []

        for condition in self.conditions.values():
            if not condition.enabled or condition.market_id != market_id:
                continue
            observed = self._extract_value(condition, update)
            if observed is None:
                continue

            passed = self._passes_condition(condition, observed)
            self.previous_values[condition.id] = observed
            if not passed:
                continue
            if self._cooldown_active(condition, current_time):
                continue

            alert = TriggeredAlert(
                condition_id=condition.id,
                market_id=condition.market_id,
                condition_type=condition.condition_type,
                operator=condition.operator,
                threshold=condition.threshold,
                observed_value=observed,
                triggered_at=current_time,
                channels=condition.channels,
            )
            triggered.append(alert)
            self.last_trigger_at[condition.id] = current_time

        if triggered:
            await self.send_notifications(triggered)
        return triggered

    async def send_notifications(self, alerts: list[TriggeredAlert]) -> dict[str, int]:
        delivered = 0
        failed = 0
        for alert in alerts:
            for channel in alert.channels:
                notifier = self.notifiers.get(channel)
                if notifier is None:
                    failed += 1
                    continue
                ok = await notifier(alert)
                if ok:
                    delivered += 1
                else:
                    failed += 1
        return {"delivered": delivered, "failed": failed}
