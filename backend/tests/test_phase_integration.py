"""Cross-phase integration tests (tasks 36.1-36.3)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from backend.app.alerts.engine import AlertEngine
from backend.app.alerts.models import AlertCondition, ConditionType, Operator
from backend.app.ml.model_registry import ModelRegistry
from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig
from backend.app.replay.replay_engine import build_sample_replay
from backend.app.signals.fusion_engine import FusionSignalEngine
from backend.app.strategy_lab.composer import (
    BlockDefinition,
    ComposedStrategy,
    ConnectionDefinition,
)


@pytest.mark.asyncio
async def test_phase1_to_phase2_integration() -> None:
    manager = BoundedTaskManager(TaskManagerConfig(max_concurrent_tasks=20, queue_max_size=20))
    try:
        async def fetch(_: int) -> int:
            return 1

        submissions = [await manager.submit_task(fetch(i), priority=1) for i in range(10)]
        tasks = [task for task in submissions if task is not None]
        results = await asyncio.gather(*tasks)
        assert sum(results) == 10
        metrics = manager.get_metrics()
        assert metrics.rejected_count == 0
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_phase2_to_phase3_integration() -> None:
    strategy = ComposedStrategy(
        strategy_id="s1",
        name="integration",
        blocks=[
            BlockDefinition(id="src", type="signal.price", config={}),
            BlockDefinition(id="th", type="operator.threshold", config={"threshold": 0.0}),
            BlockDefinition(id="act", type="action.buy", config={}),
        ],
        connections=[
            ConnectionDefinition("src", "out", "th", "in"),
            ConnectionDefinition("th", "out", "act", "trigger"),
        ],
    )
    executable = strategy.to_executable()
    assert isinstance(executable, dict)

    engine = AlertEngine()
    cond = AlertCondition(
        id="m1",
        market_id="BTCUSDT",
        condition_type=ConditionType.PRICE,
        operator=Operator.GT,
        threshold=100.0,
        cooldown_seconds=0.0,
        channels=["webhook"],
    )
    engine.register_condition(cond)
    engine.register_notifier("webhook", _noop_notifier)
    triggered = await engine.evaluate_conditions("BTCUSDT", {"mid": 110.0})
    assert triggered


@pytest.mark.asyncio
async def test_phase3_to_phase4_integration() -> None:
    with TemporaryDirectory() as tmp_dir:
        registry = ModelRegistry(str(Path(tmp_dir) / "registry.db"))
        try:
            version = registry.register_model(
                model_id="alpha",
                artifact_path="/tmp/model.bin",
                hyperparameters={"lr": 0.1},
                training_data_ref="dataset",
                performance_metrics={"acc": 0.8},
            )
            loaded = registry.load_model("alpha", version.version)
            assert loaded.version == version.version
        finally:
            registry.close()

    replay = build_sample_replay(50)
    replay.start_replay(2.0)
    books = replay.stream_orderbook(limit=5)
    assert books

    fusion = FusionSignalEngine()
    signal = fusion.generate_signal({"sentiment": 0.2, "mempool": -0.1})
    assert -1.0 <= signal.signal <= 1.0


async def _noop_notifier(_):
    return True
