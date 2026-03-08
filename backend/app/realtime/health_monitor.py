"""Health metrics monitor for realtime update components."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import ceil
from typing import Any

from backend.app.models.realtime import ConnectionMetrics, ProcessingMetrics


@dataclass
class _ConnectionAccumulator:
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages_sent: int = 0
    messages_failed: int = 0
    messages_dropped: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    is_slow: bool = False
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class _ProcessingAccumulator:
    updates_processed: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))


class HealthMonitor:
    """Track connection health and processing performance metrics."""

    def __init__(self):
        self._connections: dict[str, _ConnectionAccumulator] = {}
        self._processing: dict[str, _ProcessingAccumulator] = defaultdict(_ProcessingAccumulator)

    def on_client_connected(self, client_id: str) -> None:
        self._connections.setdefault(client_id, _ConnectionAccumulator())

    def on_client_disconnected(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    def mark_client_slow(self, client_id: str, is_slow: bool = True) -> None:
        conn = self._connections.setdefault(client_id, _ConnectionAccumulator())
        conn.is_slow = is_slow
        conn.last_activity = datetime.now(UTC)

    def record_message_sent(self, client_id: str, success: bool, latency_ms: float) -> None:
        conn = self._connections.setdefault(client_id, _ConnectionAccumulator())
        if success:
            conn.messages_sent += 1
        else:
            conn.messages_failed += 1
        conn.latencies_ms.append(latency_ms)
        conn.last_activity = datetime.now(UTC)

    def record_message_dropped(self, client_id: str) -> None:
        conn = self._connections.setdefault(client_id, _ConnectionAccumulator())
        conn.messages_dropped += 1
        conn.last_activity = datetime.now(UTC)

    def record_processing_latency(self, market_id: str, latency_ms: float) -> None:
        proc = self._processing[market_id]
        proc.updates_processed += 1
        proc.latencies_ms.append(latency_ms)
        proc.last_update = datetime.now(UTC)

    def record_processing_error(self, market_id: str) -> None:
        proc = self._processing[market_id]
        proc.errors += 1
        proc.last_update = datetime.now(UTC)

    def get_connection_health(self, client_id: str) -> ConnectionMetrics:
        conn = self._connections.setdefault(client_id, _ConnectionAccumulator())
        now = datetime.now(UTC)
        avg_latency = (
            sum(conn.latencies_ms) / len(conn.latencies_ms) if conn.latencies_ms else 0.0
        )
        return ConnectionMetrics(
            client_id=client_id,
            connected_at=conn.connected_at,
            connection_duration_seconds=(now - conn.connected_at).total_seconds(),
            messages_sent=conn.messages_sent,
            messages_failed=conn.messages_failed,
            messages_dropped=conn.messages_dropped,
            average_latency_ms=avg_latency,
            is_slow=conn.is_slow,
            last_activity=conn.last_activity,
        )

    def get_processing_metrics(self, market_id: str) -> ProcessingMetrics:
        proc = self._processing[market_id]
        avg = sum(proc.latencies_ms) / len(proc.latencies_ms) if proc.latencies_ms else 0.0
        return ProcessingMetrics(
            market_id=market_id,
            updates_processed=proc.updates_processed,
            average_latency_ms=avg,
            p95_latency_ms=self._percentile(proc.latencies_ms, 95),
            p99_latency_ms=self._percentile(proc.latencies_ms, 99),
            errors=proc.errors,
            last_update=proc.last_update,
        )

    def get_all_metrics(self) -> dict[str, Any]:
        return {
            "connections": {
                client_id: self.get_connection_health(client_id).__dict__
                for client_id in self._connections
            },
            "processing": {
                market_id: self.get_processing_metrics(market_id).__dict__
                for market_id in self._processing
            },
            "summary": {
                "active_connections": len(self._connections),
                "slow_connections": sum(1 for c in self._connections.values() if c.is_slow),
                "markets_tracked": len(self._processing),
            },
        }

    @staticmethod
    def _percentile(samples: list[float], p: int) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        idx = max(0, min(len(ordered) - 1, ceil((p / 100) * len(ordered)) - 1))
        return ordered[idx]

