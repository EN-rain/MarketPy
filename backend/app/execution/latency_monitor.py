"""Latency monitoring for order lifecycle execution quality."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil, sqrt
from statistics import mean


@dataclass(frozen=True)
class LatencyRecord:
    order_id: str
    created_at: datetime
    submitted_at: datetime
    filled_at: datetime
    cpu_load: float = 0.0
    memory_load: float = 0.0
    network_load: float = 0.0

    @property
    def submission_latency_ms(self) -> float:
        return (self.submitted_at - self.created_at).total_seconds() * 1000.0

    @property
    def fill_latency_ms(self) -> float:
        return (self.filled_at - self.submitted_at).total_seconds() * 1000.0

    @property
    def total_latency_ms(self) -> float:
        return (self.filled_at - self.created_at).total_seconds() * 1000.0


class LatencyMonitor:
    """Collects latency records and reports spikes and percentiles."""

    def __init__(self) -> None:
        self.records: list[LatencyRecord] = []
        self.spike_log: list[LatencyRecord] = []

    def record_order_lifecycle(
        self,
        order_id: str,
        created_at: datetime,
        submitted_at: datetime,
        filled_at: datetime,
        cpu_load: float = 0.0,
        memory_load: float = 0.0,
        network_load: float = 0.0,
    ) -> LatencyRecord:
        record = LatencyRecord(
            order_id=order_id,
            created_at=created_at,
            submitted_at=submitted_at,
            filled_at=filled_at,
            cpu_load=cpu_load,
            memory_load=memory_load,
            network_load=network_load,
        )
        self.records.append(record)
        if self.detect_latency_spike(record):
            self.spike_log.append(record)
        return record

    def get_latency_percentiles(self) -> dict[str, float]:
        if not self.records:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        values = sorted(record.total_latency_ms for record in self.records)
        return {
            "p50": self._percentile(values, 0.50),
            "p95": self._percentile(values, 0.95),
            "p99": self._percentile(values, 0.99),
        }

    def detect_latency_spike(self, record: LatencyRecord, threshold_ms: float = 500.0) -> bool:
        return record.total_latency_ms > threshold_ms

    def correlate_latency_with_load(self) -> dict[str, float]:
        if not self.records:
            return {"cpu": 0.0, "memory": 0.0, "network": 0.0}
        latencies = [record.total_latency_ms for record in self.records]
        return {
            "cpu": self._pearson(latencies, [record.cpu_load for record in self.records]),
            "memory": self._pearson(latencies, [record.memory_load for record in self.records]),
            "network": self._pearson(latencies, [record.network_load for record in self.records]),
        }

    def _percentile(self, values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        idx = min(len(values) - 1, max(0, int(ceil(quantile * len(values)) - 1)))
        return values[idx]

    def _pearson(self, x_values: list[float], y_values: list[float]) -> float:
        n = min(len(x_values), len(y_values))
        if n < 2:
            return 0.0
        x = x_values[:n]
        y = y_values[:n]
        x_mean = mean(x)
        y_mean = mean(y)
        cov = sum((x_i - x_mean) * (y_i - y_mean) for x_i, y_i in zip(x, y, strict=False))
        var_x = sum((x_i - x_mean) ** 2 for x_i in x)
        var_y = sum((y_i - y_mean) ** 2 for y_i in y)
        denom = sqrt(var_x * var_y)
        if denom == 0:
            return 0.0
        return max(-1.0, min(1.0, cov / denom))
