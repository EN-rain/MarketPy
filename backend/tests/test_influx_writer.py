from __future__ import annotations

from datetime import datetime

from backend.monitoring.influx import InfluxConfig, InfluxMetricWriter


class FakeInfluxClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, list[dict[str, object]]]] = []

    def write(self, bucket: str, org: str, record: list[dict[str, object]]) -> None:
        self.writes.append((bucket, org, record))


def test_influx_writer_batches_metric_records() -> None:
    client = FakeInfluxClient()
    writer = InfluxMetricWriter(client, InfluxConfig(bucket="metrics", org="marketpy"))

    writer.append(
        "model_performance",
        fields={"accuracy": 0.61},
        tags={"model": "xgb"},
        timestamp=datetime(2026, 3, 7, 12, 0, 0),
    )
    writer.append("execution_quality", fields={"slippage_bps": 3.2})

    assert writer.buffered_points == 2
    flushed = writer.flush()

    assert flushed == 2
    assert writer.buffered_points == 0
    assert client.writes[0][0] == "metrics"
    assert client.writes[0][1] == "marketpy"
    assert len(client.writes[0][2]) == 2


def test_influx_writer_exposes_retention_policies() -> None:
    writer = InfluxMetricWriter(FakeInfluxClient(), InfluxConfig(high_resolution_retention_days=30, downsampled_retention_days=365))

    assert writer.retention_policies() == {
        "high_resolution": "30d",
        "downsampled": "365d",
    }


def test_influx_writer_rejects_unknown_measurements() -> None:
    writer = InfluxMetricWriter(FakeInfluxClient())

    try:
        writer.append("unknown_metric", fields={"value": 1})
    except ValueError as exc:
        assert "Unsupported measurement" in str(exc)
    else:
        raise AssertionError("Expected unsupported measurement to raise ValueError")
