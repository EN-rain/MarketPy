"""Tests for vectorized backtest engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.sim.vectorized_engine import VectorizedBacktestEngine, VectorizedStrategy


class _SimpleStrategy(VectorizedStrategy):
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = data.copy()
        frame["entries"] = frame["close"] > frame["close"].rolling(3).mean()
        frame["exits"] = frame["close"] < frame["close"].rolling(3).mean()
        return frame


def test_vectorized_engine_run_returns_metrics() -> None:
    close = np.linspace(100, 120, 200) + np.sin(np.linspace(0, 20, 200))
    df = pd.DataFrame({"close": close})
    engine = VectorizedBacktestEngine(initial_cash=10_000.0, fee_rate=0.001)
    result = engine.run(_SimpleStrategy(), df)
    assert isinstance(result.total_return, float)
    assert result.execution_mode.value == "vectorized"
    assert result.equity_curve.shape[0] == df.shape[0]
