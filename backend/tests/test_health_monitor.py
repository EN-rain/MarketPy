"""Unit tests for HealthMonitor."""

from backend.app.realtime.health_monitor import HealthMonitor


def test_connection_metrics_accumulation():
    hm = HealthMonitor()
    hm.on_client_connected("c1")
    hm.record_message_sent("c1", True, 10.0)
    hm.record_message_sent("c1", False, 20.0)
    hm.record_message_dropped("c1")
    metrics = hm.get_connection_health("c1")
    assert metrics.messages_sent == 1
    assert metrics.messages_failed == 1
    assert metrics.messages_dropped == 1
    assert metrics.average_latency_ms == 15.0


def test_processing_percentiles():
    hm = HealthMonitor()
    for value in [1.0, 2.0, 3.0, 4.0, 50.0]:
        hm.record_processing_latency("BTCUSDT", value)
    pm = hm.get_processing_metrics("BTCUSDT")
    assert pm.updates_processed == 5
    assert pm.p95_latency_ms >= 4.0
    assert pm.p99_latency_ms >= pm.p95_latency_ms


def test_unhealthy_slow_flag():
    hm = HealthMonitor()
    hm.on_client_connected("c2")
    hm.mark_client_slow("c2", True)
    metrics = hm.get_connection_health("c2")
    assert metrics.is_slow is True

