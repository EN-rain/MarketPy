"""Observability helpers: structured logging and lightweight metrics."""

from __future__ import annotations

import json
import logging
import traceback
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any


class JsonLogFormatter(logging.Formatter):
    """JSON formatter with correlation-id support."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id
        if record.exc_info:
            payload["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def configure_json_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(JsonLogFormatter())
        root.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    root.setLevel(level)


class MetricsRegistry:
    """Small in-memory metrics registry with Prometheus text rendering."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)

    def inc(self, key: str, amount: float = 1.0) -> None:
        self._counters[key] += amount

    def set_gauge(self, key: str, value: float) -> None:
        self._gauges[key] = value

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {"counters": dict(self._counters), "gauges": dict(self._gauges)}

    def to_prometheus(self) -> str:
        lines: list[str] = []
        for key, value in self._counters.items():
            lines.append(f"{key} {value}")
        for key, value in self._gauges.items():
            lines.append(f"{key} {value}")
        return "\n".join(lines) + ("\n" if lines else "")
