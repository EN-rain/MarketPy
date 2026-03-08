"""Tests for alert storage tables in MetricsStore."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.alerts.models import AlertCondition, ConditionType, Operator, TriggeredAlert
from backend.app.storage.metrics_store import MetricsStore


def test_alert_tables_exist_and_persist_rows(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))
    try:
        condition = AlertCondition(
            id="cond-1",
            market_id="BTCUSDT",
            condition_type=ConditionType.PRICE,
            operator=Operator.GT,
            threshold=50000.0,
            cooldown_seconds=30.0,
            channels=["webhook", "discord"],
            enabled=True,
        )
        store.insert_alert_condition(condition)
        assert store.count_rows("alert_conditions") == 1

        triggered = TriggeredAlert(
            condition_id=condition.id,
            market_id=condition.market_id,
            condition_type=condition.condition_type,
            operator=condition.operator,
            threshold=condition.threshold,
            observed_value=51000.0,
            triggered_at=datetime.now(UTC),
            channels=condition.channels,
        )
        store.insert_triggered_alert(triggered)
        assert store.count_rows("triggered_alerts") == 1
    finally:
        store.close()

