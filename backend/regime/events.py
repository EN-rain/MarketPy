"""Regime transition event system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable


@dataclass(frozen=True, slots=True)
class RegimeTransitionEvent:
    previous_regime: str
    current_regime: str
    confidence: float
    timestamp: datetime


class RegimeEventSystem:
    """Emits regime transitions and tracks regime-specific attribution."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[RegimeTransitionEvent], None]] = []
        self.performance_by_regime: dict[str, list[float]] = {}
        self.alert_log: list[str] = []

    def subscribe(self, callback: Callable[[RegimeTransitionEvent], None]) -> None:
        self._subscribers.append(callback)

    def emit_transition(self, previous_regime: str, current_regime: str, confidence: float) -> RegimeTransitionEvent:
        event = RegimeTransitionEvent(
            previous_regime=previous_regime,
            current_regime=current_regime,
            confidence=confidence,
            timestamp=datetime.now(UTC),
        )
        self.alert_log.append(
            f"Regime change {previous_regime}->{current_regime} confidence={confidence:.3f}"
        )
        for subscriber in list(self._subscribers):
            subscriber(event)
        return event

    def record_performance(self, regime: str, value: float) -> None:
        self.performance_by_regime.setdefault(regime, []).append(float(value))
