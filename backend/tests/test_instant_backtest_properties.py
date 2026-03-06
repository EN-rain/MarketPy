"""Property tests for instant backtest engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.backtest.instant_engine import InstantBacktestEngine


def _write_symbol_dataset(base_dir, symbol: str, rows: int) -> None:
    market_dir = base_dir / "parquet" / f"market_id={symbol}"
    market_dir.mkdir(parents=True, exist_ok=True)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    data = []
    for idx in range(rows):
        ts = start + timedelta(minutes=5 * idx)
        close = 100.0 + (idx * 0.1)
        data.append(
            {
                "timestamp": ts,
                "token_id": symbol,
                "open": close,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "mid": close,
                "bid": close - 0.05,
                "ask": close + 0.05,
                "spread": 0.1,
                "volume": 100.0,
                "trade_count": 10,
            }
        )
    pl.DataFrame(data).write_parquet(market_dir / "bars.parquet")


# Property 20: Backtest Execution Time
@given(
    rows=st.integers(min_value=50, max_value=800),
    symbols=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=100, deadline=10000)
@pytest.mark.property_test
def test_property_instant_backtest_execution_time(rows: int, symbols: int) -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        for idx in range(symbols):
            _write_symbol_dataset(root, f"SYM{idx}", rows)

        engine = InstantBacktestEngine(data_dir=str(root))
        result = engine.run_backtest(
            strategy="momentum",
            symbols=[f"SYM{idx}" for idx in range(symbols)],
            timeframe="5m",
            lookback_bars=12,
            momentum_threshold=0.01,
        )
    assert result.execution_ms < 5000.0


# Property 21: Backtest Result Completeness
@given(
    rows=st.integers(min_value=50, max_value=300),
    timeframe=st.sampled_from(["1m", "5m", "1h", "1d"]),
)
@settings(max_examples=100, deadline=10000)
@pytest.mark.property_test
def test_property_backtest_result_completeness(rows: int, timeframe: str) -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        _write_symbol_dataset(root, "BTCUSDT", rows)
        engine = InstantBacktestEngine(data_dir=str(root))
        result = engine.run_backtest(
            strategy="momentum",
            symbols=["BTCUSDT"],
            timeframe=timeframe,
            lookback_bars=8,
            momentum_threshold=0.005,
        )
    assert isinstance(result.total_return, float)
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.max_drawdown, float)
    assert isinstance(result.win_rate, float)
    assert isinstance(result.trades, list)
    assert isinstance(result.equity_curve, list)
