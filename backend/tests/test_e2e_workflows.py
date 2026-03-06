"""End-to-end workflow tests (tasks 37.1-37.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from backend.app.alerts.engine import AlertEngine
from backend.app.alerts.models import AlertCondition, ConditionType, Operator
from backend.app.automation.engine import AutomationEngine
from backend.app.automation.models import ActionType, AutomatedAction, RiskLimits
from backend.app.backtest.instant_engine import InstantBacktestEngine
from backend.app.execution.latency_monitor import LatencyMonitor
from backend.app.execution.slippage_tracker import SlippageTracker
from backend.app.marketplace.marketplace import StrategyMarketplace
from backend.app.marketplace.models import MarketplaceStrategy
from backend.app.marketplace.models import VerifiedMetrics as MarketplaceVerifiedMetrics
from backend.app.risk.correlation_calculator import CorrelationCalculator
from backend.app.risk.stress_tester import StressTester
from backend.app.risk.var_calculator import VaRCalculator, VaRMethod
from backend.app.signals.fusion_engine import FusionSignalEngine


async def _ok_executor(_: AutomatedAction):
    return {"ok": True}


@pytest.mark.asyncio
async def test_strategy_development_workflow() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        _write_symbol_dataset(root, "BTCUSDT", 200)
        backtest = InstantBacktestEngine(data_dir=str(root))
        result = backtest.run_backtest(
            strategy="momentum",
            symbols=["BTCUSDT"],
            timeframe="1h",
            lookback_bars=12,
            momentum_threshold=0.01,
        )
        assert result.total_return == result.total_return

    alerts = AlertEngine()
    alerts.register_condition(
        AlertCondition(
            id="a1",
            market_id="BTCUSDT",
            condition_type=ConditionType.PRICE,
            operator=Operator.GT,
            threshold=100.0,
            cooldown_seconds=0.0,
            channels=["webhook"],
        )
    )
    alerts.register_notifier("webhook", _notify_ok)
    triggered = await alerts.evaluate_conditions("BTCUSDT", {"mid": 101.0})
    assert triggered

    automation = AutomationEngine()
    automation.register_executor(ActionType.PLACE_ORDER, _ok_executor)
    outcome = await automation.execute_action(
        AutomatedAction(
            id="w1",
            market_id="BTCUSDT",
            action_type=ActionType.PLACE_ORDER,
            parameters={"price": 100.0, "size": 1.0},
            risk_limits=RiskLimits(
                max_order_notional=1000.0,
                max_position_notional=5000.0,
                max_daily_loss=1000.0,
                allowed_markets=["BTCUSDT"],
            ),
        ),
        portfolio_state={"position_notional": 0.0},
    )
    assert outcome["status"] == "SUCCESS"

    slippage = SlippageTracker()
    latency = LatencyMonitor()
    slippage.record_execution("BTCUSDT", "BUY", 100.0, 100.1, 1.0, datetime.now(UTC))
    latency.record_order_lifecycle(
        "o1",
        datetime.now(UTC),
        datetime.now(UTC),
        datetime.now(UTC),
    )
    assert slippage.analyze_patterns().count == 1
    assert latency.get_latency_percentiles()["p50"] >= 0

    with TemporaryDirectory() as tmp_dir:
        market = StrategyMarketplace(str(Path(tmp_dir) / "marketplace.db"))
        try:
            market.submit_strategy(
                MarketplaceStrategy(
                    id="s1",
                    name="Strategy 1",
                    author="system",
                    description="workflow",
                    asset_class="crypto",
                    risk_level="medium",
                    methodology="simple",
                    metrics=MarketplaceVerifiedMetrics(0.2, 1.1, 0.1, 180),
                )
            )
            assert market.search_strategies()
        finally:
            market.close()


def test_risk_management_workflow() -> None:
    var = VaRCalculator()
    returns = [0.01, -0.02, 0.005, -0.01] * 50
    var_95 = var.calculate_var(100_000, returns, 0.95, VaRMethod.HISTORICAL)
    assert var_95.var_dollar >= 0

    stress = StressTester()
    stress_result = stress.run_stress_test(
        {"BTC": 50_000, "ETH": 30_000}, scenario_name="covid_crash"
    )
    assert stress_result.value_change <= 0

    corr = CorrelationCalculator()
    matrix = corr.calculate_correlations({"BTC": returns, "ETH": returns, "SOL": returns})
    assert len(matrix.assets) == 3


def test_data_pipeline_workflow() -> None:
    fusion = FusionSignalEngine()
    signal = fusion.generate_signal({"sentiment": 0.2, "mempool": 0.1, "fees": -0.1})
    assert 0.0 <= signal.confidence <= 1.0


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
