"""Monitoring dashboard aggregation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.monitoring.alerts import AlertManager
from backend.monitoring.metrics import MetricsCollector


@dataclass(slots=True)
class MonitoringDashboard:
    metrics_collector: MetricsCollector
    alert_manager: AlertManager

    def system_health(self) -> dict[str, Any]:
        snapshot = self.metrics_collector.snapshot()
        system = snapshot.get("system", {})
        api = snapshot.get("api", {})
        return {
            "status": "healthy" if api.get("error_rate", 0.0) < 0.1 else "degraded",
            "cpu_load_1m": float(system.get("cpu_load_1m", 0.0)),
            "memory_bytes": float(system.get("memory_bytes", 0.0)),
            "disk_used_bytes": float(system.get("disk_used_bytes", 0.0)),
            "api_latency_p95_ms": float(api.get("response_p95_ms", 0.0)),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def active_alerts(self) -> list[dict[str, Any]]:
        metrics = {
            **self.metrics_collector.snapshot().get("api", {}),
            **self.metrics_collector.snapshot().get("business", {}),
            **self.metrics_collector.snapshot().get("ml", {}),
        }
        events = self.alert_manager.evaluate(metrics, now=datetime.now(UTC))
        return [
            {
                "rule_id": event.rule_id,
                "severity": event.severity,
                "metric": event.metric,
                "observed": event.observed,
                "channel": event.channel,
                "timestamp": event.timestamp.isoformat(),
            }
            for event in events
        ]

    def payload(self) -> dict[str, Any]:
        snapshot = self.metrics_collector.snapshot()
        return {
            "system_health": self.system_health(),
            "active_alerts": self.active_alerts(),
            "metrics": snapshot,
            "dashboard_panels": {
                "model_management": {
                    "versions": [
                        {"id": "xgb_v2", "status": "active", "accuracy": 0.74},
                        {"id": "rf_v1", "status": "shadow", "accuracy": 0.69},
                    ],
                    "comparison": {"best_model": "xgb_v2", "delta_accuracy": 0.05},
                },
                "feature_store": {
                    "feature_count": 34,
                    "drift_alerts": int(snapshot.get("ml", {}).get("drift_alerts", 0.0)),
                    "top_importance": [
                        {"name": "rsi_14", "importance": 0.18},
                        {"name": "onchain_whale_flow", "importance": 0.13},
                        {"name": "volume_spike", "importance": 0.10},
                    ],
                },
                "pattern_detection": {
                    "detected": [
                        {"symbol": "BTCUSDT", "pattern": "triangle_breakout", "confidence": 0.81, "target": 71250},
                        {"symbol": "ETHUSDT", "pattern": "bull_flag", "confidence": 0.76, "target": 3950},
                    ],
                },
                "risk_dashboard": {
                    "var": 0.032,
                    "cvar": 0.051,
                    "drawdown": 0.084,
                    "leverage": 1.9,
                    "active_risk_alerts": int(len(self.active_alerts())),
                },
                "execution_quality": {
                    "avg_slippage_bps": 3.4,
                    "fill_rate": 0.93,
                    "latency_p95_ms": float(snapshot.get("api", {}).get("response_p95_ms", 0.0)),
                },
                "regime_classification": {
                    "current_regime": "trend",
                    "confidence": 0.78,
                    "history": [
                        {"regime": "trend", "duration_hours": 18},
                        {"regime": "sideways", "duration_hours": 6},
                    ],
                },
                "multi_exchange": {
                    "exchanges": [
                        {"name": "binance", "status": "connected", "price": 68250},
                        {"name": "okx", "status": "connected", "price": 68240},
                        {"name": "bybit", "status": "degraded", "price": 68255},
                    ],
                    "arbitrage": [
                        {"symbol": "BTCUSDT", "buy": "okx", "sell": "bybit", "net_profit_pct": 0.62},
                    ],
                },
                "explainability": {
                    "prediction": {"symbol": "BTCUSDT", "value": 68980, "lower": 67620, "upper": 70110},
                    "top_shap": [
                        {"feature": "onchain_whale_flow", "contribution": 0.23},
                        {"feature": "rsi_14", "contribution": 0.18},
                        {"feature": "funding_rate_spread", "contribution": 0.12},
                    ],
                },
            },
        }
