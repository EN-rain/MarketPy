"""Phase 22 monitoring and observability tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.monitoring.alerts import AlertManager, AlertRule
from backend.monitoring.audit import AuditLogger
from backend.monitoring.influx import InfluxConfig, InfluxMetricWriter
from backend.monitoring.metrics import MetricsCollector


class FakeInfluxClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, list[dict[str, object]]]] = []

    def write(self, bucket: str, org: str, record: list[dict[str, object]]) -> None:
        self.writes.append((bucket, org, record))


def test_metrics_collection_and_persistence() -> None:
    writer = InfluxMetricWriter(FakeInfluxClient(), InfluxConfig(bucket="metrics", org="marketpy"))
    collector = MetricsCollector(writer=writer)

    collector.record_api_call(100.0)
    collector.record_api_call(250.0, error=True)
    collector.update_business_metrics(prediction_accuracy=0.62, sharpe_ratio=1.3, win_rate=0.54, drawdown=0.08)
    collector.update_ml_metrics(inference_latency_ms=42.0, feature_latency_ms=31.0, drift_alerts=1)

    flushed = collector.persist(timestamp=datetime(2026, 3, 7, tzinfo=UTC))
    snapshot = collector.snapshot()

    assert flushed == 4
    assert snapshot["api"]["request_rate"] == 2.0
    assert snapshot["api"]["error_rate"] == 0.5
    assert snapshot["business"]["sharpe_ratio"] == 1.3


def test_alert_manager_throttle_and_escalation() -> None:
    manager = AlertManager(throttle_seconds=300)
    manager.add_rule(AlertRule("drawdown_critical", "drawdown", ">", 0.15, "critical"))
    manager.add_rule(AlertRule("drift_warning", "drift_alerts", ">", 0, "warning"))
    now = datetime(2026, 3, 7, tzinfo=UTC)

    events1 = manager.evaluate({"drawdown": 0.2, "drift_alerts": 1}, now=now)
    events2 = manager.evaluate({"drawdown": 0.21, "drift_alerts": 1}, now=now + timedelta(seconds=60))
    events3 = manager.evaluate({"drawdown": 0.21, "drift_alerts": 1}, now=now + timedelta(seconds=600))

    assert {item.channel for item in events1} == {"pagerduty", "slack"}
    assert events2 == []
    assert len(events3) == 2


def test_audit_logger_records_and_retention_cleanup(tmp_path) -> None:
    logger = AuditLogger(str(tmp_path / "audit.db"), retention_days=1)
    logger.log_trading_decision({"symbol": "BTCUSDT", "action": "buy"}, reason="ml_signal")
    logger.log_model_deployment({"model": "xgb_v2"}, reason="shadow_promotion")
    logger.log_config_change({"field": "max_risk", "value": 0.1}, reason="ops_update")
    logger.log_risk_breach({"metric": "drawdown", "value": 0.2}, reason="threshold_exceeded")

    assert logger.count_rows() == 4
    removed = logger.cleanup_retention(now=datetime.now(UTC) + timedelta(days=2))
    assert removed == 4
    assert logger.count_rows() == 0
    logger.close()
