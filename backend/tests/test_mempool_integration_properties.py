"""Property tests for Mempool on-chain monitoring.

Validates:
- Property 14: Alert Threshold Triggering
- Property 15: Historical Data Persistence
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.onchain_monitor import OnChainMonitor
from backend.app.models.market import OnChainMetrics


# Property 14: Alert Threshold Triggering
@given(
    mempool_size_mb=st.floats(
        min_value=101.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    fee_rate_sat_vb=st.floats(
        min_value=101.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    baseline_hash_rate=st.floats(
        min_value=100.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    drop_factor=st.floats(min_value=0.0, max_value=0.79, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_onchain_alert_threshold_triggering(
    mempool_size_mb: float, fee_rate_sat_vb: float, baseline_hash_rate: float, drop_factor: float
) -> None:
    monitor = OnChainMonitor()

    # Seed baseline.
    monitor.record(
        OnChainMetrics(
            timestamp=datetime.now(UTC),
            mempool_size_mb=10.0,
            fee_rate_sat_vb=10.0,
            hash_rate_eh_s=baseline_hash_rate,
            difficulty=1.0,
        )
    )

    # Trigger all threshold conditions.
    alerts = monitor.record(
        OnChainMetrics(
            timestamp=datetime.now(UTC),
            mempool_size_mb=mempool_size_mb,
            fee_rate_sat_vb=fee_rate_sat_vb,
            hash_rate_eh_s=baseline_hash_rate * drop_factor,
            difficulty=1.0,
        )
    )
    metrics = {alert.metric for alert in alerts}
    assert "mempool_size_mb" in metrics
    assert "fee_rate_sat_vb" in metrics
    assert "hash_rate_drop_pct" in metrics


# Property 15: Historical Data Persistence
@given(
    sample_count=st.integers(min_value=1, max_value=200),
    mempool_size_mb=st.floats(
        min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    fee_rate_sat_vb=st.floats(
        min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    hash_rate_eh_s=st.floats(
        min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_onchain_historical_data_persistence(
    sample_count: int, mempool_size_mb: float, fee_rate_sat_vb: float, hash_rate_eh_s: float
) -> None:
    monitor = OnChainMonitor()
    for _ in range(sample_count):
        monitor.record(
            OnChainMetrics(
                timestamp=datetime.now(UTC),
                mempool_size_mb=mempool_size_mb,
                fee_rate_sat_vb=fee_rate_sat_vb,
                hash_rate_eh_s=hash_rate_eh_s,
                difficulty=1.0,
            )
        )

    assert len(monitor.history) == sample_count
    assert all(isinstance(item, OnChainMetrics) for item in monitor.history)
