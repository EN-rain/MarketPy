"""Phase 16 data quality monitoring tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.ingest.data_monitor import DataMonitor
from backend.monitoring.influx import InfluxConfig, InfluxMetricWriter


class FakeInfluxClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, list[dict[str, object]]]] = []

    def write(self, bucket: str, org: str, record: list[dict[str, object]]) -> None:
        self.writes.append((bucket, org, record))


def _valid_ohlcv_frame(rows: int = 10) -> pd.DataFrame:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    data = []
    for index in range(rows):
        open_price = 100.0 + index
        close_price = open_price + 0.5
        low = open_price - 1.0
        high = close_price + 1.0
        data.append(
            {
                "timestamp": start + timedelta(minutes=index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "volume": 1_000.0 + index,
            }
        )
    return pd.DataFrame(data)


@pytest.mark.property_test
@settings(max_examples=40)
@given(
    base=st.floats(min_value=1.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    spread=st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False),
    volume=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_ohlcv_data_integrity(base: float, spread: float, volume: float) -> None:
    frame = pd.DataFrame(
        [
            {
                "timestamp": datetime(2025, 1, 1, tzinfo=UTC),
                "open": base,
                "high": base + spread,
                "low": base - spread,
                "close": base + (spread / 2),
                "volume": volume,
            }
        ]
    )
    mask = DataMonitor().validate_ohlcv_integrity(frame)
    assert bool(mask.iloc[0]) is True


@pytest.mark.property_test
@settings(max_examples=30)
@given(extreme=st.floats(min_value=500.0, max_value=5_000.0, allow_nan=False, allow_infinity=False))
def test_property_outlier_detection_threshold(extreme: float) -> None:
    frame = _valid_ohlcv_frame(30)
    frame.loc[len(frame)] = {
        "timestamp": frame["timestamp"].iloc[-1] + timedelta(minutes=1),
        "open": extreme,
        "high": extreme + 1,
        "low": extreme - 1,
        "close": extreme,
        "volume": 999_999.0,
    }
    outliers = DataMonitor().detect_outliers(frame, z_threshold=3.0)
    assert "open" in outliers or "close" in outliers or "volume" in outliers


@pytest.mark.property_test
@settings(max_examples=20)
@given(gap_index=st.integers(min_value=2, max_value=8))
def test_property_missing_timestamp_detection(gap_index: int) -> None:
    frame = _valid_ohlcv_frame(10).drop(index=gap_index).reset_index(drop=True)
    missing = DataMonitor().detect_missing_timestamps(frame, expected_frequency=pd.Timedelta(minutes=1))
    expected = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=gap_index)
    assert pd.Timestamp(expected) in missing


def test_data_quality_metrics_tracking_and_alerting() -> None:
    client = FakeInfluxClient()
    writer = InfluxMetricWriter(client, InfluxConfig(bucket="metrics", org="marketpy"))
    monitor = DataMonitor(writer=writer)
    frame = _valid_ohlcv_frame(12).drop(index=4).reset_index(drop=True)
    frame.loc[0, "high"] = frame.loc[0, "open"] - 1.0

    metrics, alerts = monitor.evaluate(
        frame,
        expected_frequency=pd.Timedelta(minutes=1),
        now=datetime(2025, 1, 1, 0, 20, tzinfo=UTC),
    )
    flushed = writer.flush()

    assert metrics.completeness < 0.95
    assert metrics.missing_rate > 0.0
    assert metrics.quarantined_rows > 0
    assert flushed == 1
    assert client.writes
    assert {alert.metric for alert in alerts} >= {"completeness", "staleness_seconds", "outlier_rate"}
