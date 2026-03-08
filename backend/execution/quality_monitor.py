"""Execution quality aggregation and alerting."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from backend.execution.tca import TCAResult


@dataclass(frozen=True, slots=True)
class ExecutionQualitySummary:
    by_hour: dict[int, float]
    by_regime: dict[str, float]
    by_order_bucket: dict[str, float]
    alert_triggered: bool


class ExecutionQualityMonitor:
    """Aggregates TCA metrics and raises slippage alerts."""

    def __init__(self) -> None:
        self.records: list[tuple[datetime, str, float, TCAResult]] = []
        self._recent_slippage_bps: deque[float] = deque(maxlen=5)

    def record(self, *, timestamp: datetime, regime: str, order_size: float, slippage_bps: float, tca: TCAResult) -> None:
        self.records.append((timestamp, regime, float(order_size), tca))
        self._recent_slippage_bps.append(float(slippage_bps))

    def alert_on_consecutive_slippage(self, threshold_bps: float = 10.0) -> bool:
        if len(self._recent_slippage_bps) < 5:
            return False
        return all(abs(value) > threshold_bps for value in self._recent_slippage_bps)

    def summarize(self) -> ExecutionQualitySummary:
        def bucket(size: float) -> str:
            if size < 1:
                return "small"
            if size < 10:
                return "medium"
            return "large"

        by_hour: dict[int, list[float]] = {}
        by_regime: dict[str, list[float]] = {}
        by_order_bucket: dict[str, list[float]] = {}
        for ts, regime, order_size, tca in self.records:
            by_hour.setdefault(ts.hour, []).append(tca.implementation_shortfall)
            by_regime.setdefault(regime, []).append(tca.implementation_shortfall)
            by_order_bucket.setdefault(bucket(order_size), []).append(tca.implementation_shortfall)

        def average(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        return ExecutionQualitySummary(
            by_hour={key: average(values) for key, values in by_hour.items()},
            by_regime={key: average(values) for key, values in by_regime.items()},
            by_order_bucket={key: average(values) for key, values in by_order_bucket.items()},
            alert_triggered=self.alert_on_consecutive_slippage(),
        )
