"""On-chain metrics monitor with threshold alerts and historical storage."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models.market import OnChainMetrics
from backend.app.storage.metrics_store import MetricsStore


@dataclass(frozen=True)
class OnChainAlert:
    metric: str
    value: float
    threshold: float
    message: str


class OnChainMonitor:
    """Evaluate on-chain thresholds and persist history for backtesting."""

    def __init__(
        self,
        *,
        mempool_threshold_mb: float = 100.0,
        fee_rate_threshold_sat_vb: float = 100.0,
        hash_rate_drop_threshold_pct: float = 20.0,
        store: MetricsStore | None = None,
    ):
        self.mempool_threshold_mb = mempool_threshold_mb
        self.fee_rate_threshold_sat_vb = fee_rate_threshold_sat_vb
        self.hash_rate_drop_threshold_pct = hash_rate_drop_threshold_pct
        self.store = store
        self.history: list[OnChainMetrics] = []
        self._baseline_hash_rate: float | None = None

    def record(self, metrics: OnChainMetrics) -> list[OnChainAlert]:
        self.history.append(metrics)
        if self.store is not None:
            self.store.insert_onchain_metrics(metrics)
        alerts: list[OnChainAlert] = []

        if metrics.mempool_size_mb > self.mempool_threshold_mb:
            alerts.append(
                OnChainAlert(
                    metric="mempool_size_mb",
                    value=metrics.mempool_size_mb,
                    threshold=self.mempool_threshold_mb,
                    message="Mempool congestion above threshold",
                )
            )

        if metrics.fee_rate_sat_vb > self.fee_rate_threshold_sat_vb:
            alerts.append(
                OnChainAlert(
                    metric="fee_rate_sat_vb",
                    value=metrics.fee_rate_sat_vb,
                    threshold=self.fee_rate_threshold_sat_vb,
                    message="Fee rate above threshold",
                )
            )

        if self._baseline_hash_rate is None:
            self._baseline_hash_rate = metrics.hash_rate_eh_s
        else:
            if self._baseline_hash_rate > 0:
                drop_pct = (
                    (self._baseline_hash_rate - metrics.hash_rate_eh_s)
                    / self._baseline_hash_rate
                ) * 100
                if drop_pct > self.hash_rate_drop_threshold_pct:
                    alerts.append(
                        OnChainAlert(
                            metric="hash_rate_drop_pct",
                            value=drop_pct,
                            threshold=self.hash_rate_drop_threshold_pct,
                            message="Hash rate dropped significantly",
                        )
                    )
            self._baseline_hash_rate = metrics.hash_rate_eh_s

        return alerts
