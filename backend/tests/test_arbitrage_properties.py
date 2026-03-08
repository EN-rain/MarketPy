"""Property tests for arbitrage scanning."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.arbitrage.scanner import ArbitrageScanner


# Property 50: Arbitrage Price Comparison
@given(
    p1=st.floats(min_value=1.0, max_value=200_000.0, allow_nan=False, allow_infinity=False),
    p2=st.floats(min_value=1.0, max_value=200_000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_arbitrage_price_comparison(p1: float, p2: float) -> None:
    with TemporaryDirectory() as tmp_dir:
        scanner = ArbitrageScanner(str(Path(tmp_dir) / "arb.db"), min_profit_threshold_pct=0.0)
        try:
            opps = scanner.scan_opportunities("BTCUSDT", {"ex1": p1, "ex2": p2})
            assert isinstance(opps, list)
            assert all(item.buy_exchange != item.sell_exchange for item in opps)
        finally:
            scanner.close()


# Property 51: Arbitrage Profit Calculation
@given(
    gross=st.floats(min_value=-2.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    fee=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    slip=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_arbitrage_profit_calculation(gross: float, fee: float, slip: float) -> None:
    with TemporaryDirectory() as tmp_dir:
        scanner = ArbitrageScanner(str(Path(tmp_dir) / "arb.db"))
        try:
            net = scanner.calculate_net_profit(
                gross_profit_pct=gross, fee_pct=fee, slippage_pct=slip
            )
            assert net == pytest.approx(gross - fee - slip)
        finally:
            scanner.close()


# Property 52: Arbitrage Alert Generation
@given(diff=st.floats(min_value=0.71, max_value=5.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_arbitrage_alert_generation(diff: float) -> None:
    with TemporaryDirectory() as tmp_dir:
        scanner = ArbitrageScanner(str(Path(tmp_dir) / "arb.db"), min_profit_threshold_pct=0.5)
        try:
            buy = 100.0
            sell = buy * (1 + diff / 100)
            opps = scanner.scan_opportunities("BTCUSDT", {"a": buy, "b": sell})
            alerts = scanner.generate_alerts(opps)
            assert alerts
        finally:
            scanner.close()


# Property 53: Arbitrage Opportunity Tracking
@settings(max_examples=50, deadline=7000)
@given(seed=st.integers(min_value=1, max_value=1000))
@pytest.mark.property_test
def test_property_arbitrage_opportunity_tracking(seed: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        scanner = ArbitrageScanner(
            str(Path(tmp_dir) / f"arb_{seed}.db"), min_profit_threshold_pct=0.1
        )
        try:
            for i in range(5):
                base = 100 + i
                scanner.scan_opportunities("BTCUSDT", {"a": base, "b": base * 1.02})
            metrics = scanner.track_opportunity_metrics("BTCUSDT")
            assert metrics["count"] >= 1
            assert metrics["avg_detection_interval_seconds"] >= 0
            assert metrics["avg_duration_seconds"] >= 0
        finally:
            scanner.close()


# Property 54: Arbitrage Opportunity Filtering
@given(diff=st.floats(min_value=0.0, max_value=0.3, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_arbitrage_opportunity_filtering(diff: float) -> None:
    with TemporaryDirectory() as tmp_dir:
        scanner = ArbitrageScanner(str(Path(tmp_dir) / "arb.db"), min_profit_threshold_pct=0.5)
        try:
            buy = 100.0
            sell = buy * (1 + diff / 100)
            opps = scanner.scan_opportunities("BTCUSDT", {"a": buy, "b": sell})
            assert not opps
        finally:
            scanner.close()
