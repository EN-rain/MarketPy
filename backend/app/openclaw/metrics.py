"""OpenClaw metrics tracking and Prometheus text exposition."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class TimerResult:
    key: str
    duration_seconds: float


class OpenClawMetrics:
    """In-memory metrics with Prometheus-compatible rendering."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._durations_sum: dict[str, float] = defaultdict(float)
        self._durations_count: dict[str, float] = defaultdict(float)

    def increment(self, key: str, amount: float = 1.0) -> None:
        self._counters[key] += amount

    def set_gauge(self, key: str, value: float) -> None:
        self._gauges[key] = value

    def observe(self, key: str, duration_seconds: float) -> None:
        self._durations_sum[key] += duration_seconds
        self._durations_count[key] += 1.0

    @contextmanager
    def timer(self, key: str) -> Iterator[TimerResult]:
        start = time.perf_counter()
        result = TimerResult(key=key, duration_seconds=0.0)
        try:
            yield result
        finally:
            elapsed = time.perf_counter() - start
            result.duration_seconds = elapsed
            self.observe(key, elapsed)

    def to_prometheus(self) -> str:
        lines: list[str] = []
        for key, value in sorted(self._counters.items()):
            lines.append(f"{key} {value}")
        for key, value in sorted(self._gauges.items()):
            lines.append(f"{key} {value}")
        for key, value in sorted(self._durations_sum.items()):
            lines.append(f"{key}_sum {value}")
            lines.append(f"{key}_count {self._durations_count[key]}")
        return "\n".join(lines) + ("\n" if lines else "")

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "duration_sum": dict(self._durations_sum),
            "duration_count": dict(self._durations_count),
        }
