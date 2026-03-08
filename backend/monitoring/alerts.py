"""Monitoring alert rules and throttled escalation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class AlertRule:
    rule_id: str
    metric: str
    operator: str
    threshold: float
    severity: str


@dataclass(frozen=True, slots=True)
class AlertEvent:
    rule_id: str
    severity: str
    metric: str
    observed: float
    channel: str
    timestamp: datetime


class AlertManager:
    def __init__(self, throttle_seconds: int = 300) -> None:
        self.throttle = timedelta(seconds=throttle_seconds)
        self.rules: dict[str, AlertRule] = {}
        self.last_sent: dict[str, datetime] = {}

    def add_rule(self, rule: AlertRule) -> None:
        self.rules[rule.rule_id] = rule

    def _passes(self, rule: AlertRule, observed: float) -> bool:
        if rule.operator == ">":
            return observed > rule.threshold
        if rule.operator == "<":
            return observed < rule.threshold
        if rule.operator == ">=":
            return observed >= rule.threshold
        if rule.operator == "<=":
            return observed <= rule.threshold
        raise ValueError(f"Unsupported operator: {rule.operator}")

    def evaluate(self, metrics: dict[str, float], now: datetime | None = None) -> list[AlertEvent]:
        current_time = now or datetime.now(UTC)
        events: list[AlertEvent] = []
        for rule in self.rules.values():
            observed = float(metrics.get(rule.metric, 0.0))
            if not self._passes(rule, observed):
                continue
            last = self.last_sent.get(rule.rule_id)
            if last is not None and (current_time - last) < self.throttle:
                continue
            channel = "pagerduty" if rule.severity == "critical" else "slack"
            events.append(
                AlertEvent(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    metric=rule.metric,
                    observed=observed,
                    channel=channel,
                    timestamp=current_time,
                )
            )
            self.last_sent[rule.rule_id] = current_time
        return events
