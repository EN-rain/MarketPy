"""Phase 14 execution quality tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.execution.analyzer import ExecutionAnalyzer
from backend.execution.quality_monitor import ExecutionQualityMonitor
from backend.execution.tca import TCAAnalyzer


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    predicted=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    execution=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_slippage_calculation(predicted: float, execution: float) -> None:
    bps = ExecutionAnalyzer.compute_slippage_bps(predicted, execution)
    expected = ((execution - predicted) / predicted) * 10_000.0
    assert bps == pytest.approx(expected, rel=1e-9)


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    size_small=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False),
    size_large=st.floats(min_value=101.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    avg_volume=st.floats(min_value=10_000.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_market_impact_square_root_model(size_small: float, size_large: float, avg_volume: float) -> None:
    analyzer = TCAAnalyzer()
    small = analyzer.market_impact(size_small, avg_volume)
    large = analyzer.market_impact(size_large, avg_volume)
    assert large >= small


def test_execution_analyzer_tca_monitoring_and_checkpoint(tmp_path: Path) -> None:
    analyzer = ExecutionAnalyzer(db_path=tmp_path / "exec.sqlite")
    record = analyzer.analyze_execution(
        order_id="o1",
        symbol="BTCUSDT",
        predicted_price=100.0,
        order_price=100.1,
        execution_price=100.2,
        execution_time_ms=35.0,
    )
    assert record.slippage_bps == pytest.approx(20.0, abs=1e-9)
    assert analyzer.recent(5)

    tca = TCAAnalyzer().compute_tca(
        arrival_price=100.0,
        execution_price=100.2,
        expected_price=100.1,
        order_size=5.0,
        spread=0.1,
        fee_rate=0.001,
        average_volume=10_000.0,
        vwap_price=100.05,
        twap_price=100.08,
        filled_size=5.0,
    )
    assert tca.fill_rate == 1.0
    assert tca.market_impact >= 0.0

    monitor = ExecutionQualityMonitor()
    now = datetime.now(UTC)
    for index in range(5):
        monitor.record(
            timestamp=now + timedelta(minutes=index),
            regime="high_volatility" if index % 2 else "ranging",
            order_size=5.0 + index,
            slippage_bps=11.0 + index,
            tca=tca,
        )
    summary = monitor.summarize()
    assert summary.alert_triggered is True
    assert summary.by_regime
