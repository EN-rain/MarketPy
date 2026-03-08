"""Monitoring metrics collection for system, API, business, and ML domains."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
import os
import shutil
import statistics

from backend.monitoring.influx import InfluxMetricWriter


@dataclass(slots=True)
class _LatencyWindow:
    values_ms: deque[float] = field(default_factory=lambda: deque(maxlen=10_000))

    def add(self, value_ms: float) -> None:
        self.values_ms.append(float(value_ms))

    def quantiles(self) -> dict[str, float]:
        if not self.values_ms:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        ordered = sorted(self.values_ms)
        def _pct(p: float) -> float:
            idx = min(max(int(round((len(ordered) - 1) * p)), 0), len(ordered) - 1)
            return float(ordered[idx])
        return {"p50": _pct(0.50), "p95": _pct(0.95), "p99": _pct(0.99)}


class MetricsCollector:
    def __init__(self, writer: InfluxMetricWriter | None = None) -> None:
        self.writer = writer
        self._api_latency = _LatencyWindow()
        self._api_requests = 0
        self._api_errors = 0
        self._business: dict[str, float] = defaultdict(float)
        self._ml: dict[str, float] = defaultdict(float)

    def collect_system_metrics(self) -> dict[str, float]:
        disk = shutil.disk_usage(".")
        memory = 0.0
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            memory = float(page_size * phys_pages)
        except (AttributeError, ValueError, OSError):
            memory = 0.0
        cpu_load = 0.0
        try:
            cpu_load = float(os.getloadavg()[0])
        except (AttributeError, OSError):
            cpu_load = 0.0
        metrics = {
            "cpu_load_1m": cpu_load,
            "memory_bytes": memory,
            "disk_total_bytes": float(disk.total),
            "disk_used_bytes": float(disk.used),
            "disk_free_bytes": float(disk.free),
        }
        return metrics

    def record_api_call(self, latency_ms: float, *, error: bool = False) -> None:
        self._api_requests += 1
        if error:
            self._api_errors += 1
        self._api_latency.add(latency_ms)

    def collect_api_metrics(self) -> dict[str, float]:
        quantiles = self._api_latency.quantiles()
        error_rate = float(self._api_errors / self._api_requests) if self._api_requests else 0.0
        return {
            "request_rate": float(self._api_requests),
            "error_rate": error_rate,
            "response_p50_ms": quantiles["p50"],
            "response_p95_ms": quantiles["p95"],
            "response_p99_ms": quantiles["p99"],
        }

    def update_business_metrics(self, *, prediction_accuracy: float, sharpe_ratio: float, win_rate: float, drawdown: float) -> None:
        self._business.update(
            {
                "prediction_accuracy": float(prediction_accuracy),
                "sharpe_ratio": float(sharpe_ratio),
                "win_rate": float(win_rate),
                "drawdown": float(drawdown),
            }
        )

    def update_ml_metrics(self, *, inference_latency_ms: float, feature_latency_ms: float, drift_alerts: int) -> None:
        self._ml.update(
            {
                "inference_latency_ms": float(inference_latency_ms),
                "feature_latency_ms": float(feature_latency_ms),
                "drift_alerts": float(drift_alerts),
            }
        )

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            "system": self.collect_system_metrics(),
            "api": self.collect_api_metrics(),
            "business": dict(self._business),
            "ml": dict(self._ml),
        }

    def persist(self, *, timestamp: datetime | None = None) -> int:
        if self.writer is None:
            return 0
        ts = timestamp or datetime.now(UTC)
        snapshot = self.snapshot()
        self.writer.append("model_performance", fields=snapshot["business"], timestamp=ts)
        self.writer.append("execution_quality", fields=snapshot["api"], timestamp=ts)
        self.writer.append("portfolio_risk", fields=snapshot["system"], timestamp=ts)
        self.writer.append("data_quality", fields=snapshot["ml"], timestamp=ts)
        return self.writer.flush()
