"""Property tests for latency monitoring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.execution.latency_monitor import LatencyMonitor


# Property 34: Latency Timestamp Completeness
@given(
    submit_ms=st.integers(min_value=1, max_value=5_000),
    fill_ms=st.integers(min_value=1, max_value=5_000),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_latency_timestamp_completeness(submit_ms: int, fill_ms: int) -> None:
    monitor = LatencyMonitor()
    created = datetime.now(UTC)
    submitted = created + timedelta(milliseconds=submit_ms)
    filled = submitted + timedelta(milliseconds=fill_ms)
    record = monitor.record_order_lifecycle("o1", created, submitted, filled)
    assert record.created_at is not None
    assert record.submitted_at is not None
    assert record.filled_at is not None
    assert record.submission_latency_ms > 0
    assert record.fill_latency_ms > 0
    assert record.total_latency_ms > 0


# Property 35: Latency Calculation Correctness
@given(
    submit_ms=st.integers(min_value=1, max_value=1000),
    fill_ms=st.integers(min_value=1, max_value=1000),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_latency_calculation_correctness(submit_ms: int, fill_ms: int) -> None:
    monitor = LatencyMonitor()
    created = datetime.now(UTC)
    submitted = created + timedelta(milliseconds=submit_ms)
    filled = submitted + timedelta(milliseconds=fill_ms)
    record = monitor.record_order_lifecycle("o2", created, submitted, filled)
    assert record.submission_latency_ms == pytest.approx(float(submit_ms), abs=1.0)
    assert record.fill_latency_ms == pytest.approx(float(fill_ms), abs=1.0)
    assert record.total_latency_ms == pytest.approx(float(submit_ms + fill_ms), abs=1.0)


# Property 36: Latency Spike Logging
@given(total_ms=st.integers(min_value=501, max_value=10_000))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_latency_spike_logging(total_ms: int) -> None:
    monitor = LatencyMonitor()
    created = datetime.now(UTC)
    submitted = created + timedelta(milliseconds=1)
    filled = created + timedelta(milliseconds=total_ms)
    record = monitor.record_order_lifecycle("o3", created, submitted, filled)
    assert monitor.detect_latency_spike(record) is True
    assert monitor.spike_log
    assert monitor.spike_log[0].order_id == "o3"


# Property 37: Latency-Load Correlation
@given(scale=st.floats(min_value=2.0, max_value=10.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_latency_load_correlation(scale: float) -> None:
    monitor = LatencyMonitor()
    base = datetime.now(UTC)
    for i in range(1, 30):
        created = base + timedelta(seconds=i)
        total = int(100 + (i * scale * 10))
        submitted = created + timedelta(milliseconds=5)
        filled = created + timedelta(milliseconds=total)
        cpu = i / 30
        memory = i / 30
        network = i / 30
        monitor.record_order_lifecycle(
            f"o{i}",
            created,
            submitted,
            filled,
            cpu_load=cpu,
            memory_load=memory,
            network_load=network,
        )
    corr = monitor.correlate_latency_with_load()
    assert corr["cpu"] > 0.5
    assert corr["memory"] > 0.5
    assert corr["network"] > 0.5
