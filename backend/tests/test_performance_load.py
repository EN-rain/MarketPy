"""Performance and load tests (tasks 38.1-38.3)."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from backend.app.alerts.engine import AlertEngine
from backend.app.alerts.models import AlertCondition, ConditionType, Operator
from backend.app.backtest.instant_engine import InstantBacktestEngine
from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig
from backend.app.risk.correlation_calculator import CorrelationCalculator
from backend.app.risk.stress_tester import StressTester
from backend.app.risk.var_calculator import VaRCalculator, VaRMethod


@pytest.mark.asyncio
async def test_system_under_high_load() -> None:
    manager = BoundedTaskManager(TaskManagerConfig(max_concurrent_tasks=1000, queue_max_size=2000))
    alerts = AlertEngine()
    alerts.register_condition(
        AlertCondition(
            id="hl",
            market_id="BTCUSDT",
            condition_type=ConditionType.PRICE,
            operator=Operator.GT,
            threshold=100.0,
            cooldown_seconds=0.0,
            channels=["noop"],
        )
    )
    alerts.register_notifier("noop", _notify_ok)
    try:
        async def unit(_: int) -> int:
            await alerts.evaluate_conditions("BTCUSDT", {"mid": 101.0})
            return 1

        t0 = time.perf_counter()
        submissions = [await manager.submit_task(unit(i), priority=1) for i in range(1000)]
        tasks = [task for task in submissions if task is not None]
        out = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0
        assert sum(out) == 1000
        assert elapsed < 10
        assert manager.get_metrics().rejected_count == 0
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_backtest_performance() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        _write_symbol_dataset(root, "BTCUSDT", 500)
        engine = InstantBacktestEngine(data_dir=str(root))
        t0 = time.perf_counter()
        result = engine.run_backtest(
            strategy="momentum",
            symbols=["BTCUSDT"],
            timeframe="1h",
            lookback_bars=12,
            momentum_threshold=0.01,
        )
        elapsed = time.perf_counter() - t0
        assert elapsed < 5
        assert result.total_return == result.total_return


def test_risk_calculation_performance() -> None:
    returns = [0.01, -0.02, 0.005, -0.01] * 1000
    t0 = time.perf_counter()
    var = VaRCalculator().calculate_var(100_000, returns, 0.95, VaRMethod.MONTE_CARLO)
    stress = StressTester().run_stress_test(
        {"BTC": 80_000, "ETH": 30_000}, scenario_name="2008_crisis"
    )
    corr = CorrelationCalculator().calculate_correlations(
        {"BTC": returns, "ETH": returns, "SOL": returns}
    )
    elapsed = time.perf_counter() - t0
    assert var.var_dollar >= 0
    assert stress.value_change <= 0
    assert len(corr.assets) == 3
    assert elapsed < 300


async def _notify_ok(_):
    return True


def _write_symbol_dataset(base_dir: Path, symbol: str, rows: int) -> None:
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
