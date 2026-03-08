"""Phase 15 regime-aware walk-forward tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.sim.vectorized_engine import VectorizedStrategy
from backend.sim.walk_forward import WalkForwardOptimizer


class _RegimeStrategy(VectorizedStrategy):
    def __init__(self) -> None:
        self.lookback = 3
        self.threshold = 0.0

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = data.copy()
        rolling = frame["close"].rolling(self.lookback, min_periods=1).mean()
        frame["entries"] = frame["close"] > (rolling * (1 + self.threshold))
        frame["exits"] = frame["close"] < rolling
        return frame


def _make_regime_frame(days: int = 240) -> pd.DataFrame:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(days=index) for index in range(days)]
    regimes = ["trend" if (index // 60) % 2 == 0 else "mean_reversion" for index in range(days)]
    close = [100.0 + (index * 0.2 if regime == "trend" else (index % 10) * 0.05) for index, regime in enumerate(regimes)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": close,
            "regime": regimes,
            "volatility": [0.01 + (index % 7) * 0.002 for index in range(days)],
            "liquidity": [1_000_000.0 - (index % 20) * 10_000.0 for index in range(days)],
            "order_size": [1.0 + (index % 5) for index in range(days)],
        }
    )


@pytest.mark.property_test
@settings(max_examples=50)
@given(
    small_size=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    large_size=st.floats(min_value=20.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    low_vol=st.floats(min_value=0.001, max_value=0.02, allow_nan=False, allow_infinity=False),
    high_vol=st.floats(min_value=0.03, max_value=0.2, allow_nan=False, allow_infinity=False),
    low_liq=st.floats(min_value=100.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    high_liq=st.floats(min_value=100_000.0, max_value=10_000_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_backtest_slippage_modeling(
    small_size: float,
    large_size: float,
    low_vol: float,
    high_vol: float,
    low_liq: float,
    high_liq: float,
) -> None:
    optimizer = WalkForwardOptimizer()
    low = optimizer.model_slippage(small_size, low_vol, high_liq)
    high = optimizer.model_slippage(large_size, high_vol, low_liq)
    assert high > low > 0.0


def test_regime_specific_walk_forward_optimization_tracks_regime_performance() -> None:
    optimizer = WalkForwardOptimizer()
    result = optimizer.run_regime_walk_forward(
        _RegimeStrategy(),
        _make_regime_frame(),
        param_grid={"lookback": [2, 3, 5], "threshold": [0.0, 0.01]},
        train_days=90,
        validation_days=30,
        step_days=30,
    )

    assert result.windows
    assert result.metrics
    assert all("regime_performance" in metric for metric in result.metrics)
    assert any(metric["regime_change_count"] >= 0 for metric in result.metrics)
    assert any(metric["modeled_slippage"] > 0 for metric in result.metrics)


def test_walk_forward_reporting_aggregates_window_results() -> None:
    optimizer = WalkForwardOptimizer()
    result = optimizer.run_regime_walk_forward(
        _RegimeStrategy(),
        _make_regime_frame(),
        param_grid={"lookback": [2, 4], "threshold": [0.0, 0.005]},
        train_days=90,
        validation_days=30,
        step_days=30,
    )

    report = optimizer.generate_report(result)

    assert report.window_count == len(result.windows)
    assert 0.0 <= report.win_rate <= 1.0
    assert report.max_drawdown >= 0.0
    assert report.regime_performance
