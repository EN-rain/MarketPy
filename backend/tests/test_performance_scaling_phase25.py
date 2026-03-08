"""Phase 25 performance optimization and scaling tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from backend.app.realtime.distributed_state import InMemorySubscriptionStore
from backend.execution.analyzer import ExecutionAnalyzer
from backend.features.cache import RedisFeatureCache
from backend.features.computer import FeatureComputer
from backend.features.registry import FeatureDefinition, FeatureRegistry


class _DummyRedis:
    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: object, ex: int | None = None) -> None:
        self.store[key] = value

    def mget(self, keys: list[str]) -> list[object]:
        return [self.store.get(key) for key in keys]

    def mset(self, mapping: dict[str, object]) -> None:
        self.store.update(mapping)


def test_feature_computer_uses_batch_cache_and_parallel_compute() -> None:
    registry = FeatureRegistry()
    registry.register_feature(
        FeatureDefinition(
            name="f_mean",
            version="1.0.0",
            definition={"source": "test"},
            dependencies=[],
            data_sources=["market"],
            computation_logic="mean close",
            compute_fn=lambda frame: float(frame["close"].mean()),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="f_last",
            version="1.0.0",
            definition={"source": "test"},
            dependencies=[],
            data_sources=["market"],
            computation_logic="last close",
            compute_fn=lambda frame: float(frame["close"].iloc[-1]),
        )
    )
    cache = RedisFeatureCache(client=_DummyRedis())
    computer = FeatureComputer(registry=registry, cache=cache)
    now = datetime.now(UTC)
    market_data = pd.DataFrame(
        {
            "timestamp": [now - timedelta(minutes=2), now - timedelta(minutes=1), now],
            "close": [100.0, 101.0, 103.0],
        }
    )

    first = computer.compute_features(now, market_data, ["f_mean", "f_last"])
    second = computer.compute_features(now, market_data, ["f_mean", "f_last"])
    assert first["f_last"] == 103.0
    assert second == first
    assert cache.metrics.hit_rate > 0.0


def test_execution_analyzer_recent_by_symbol_query_path(tmp_path) -> None:
    analyzer = ExecutionAnalyzer(db_path=tmp_path / "exec.sqlite")
    analyzer.analyze_execution(
        order_id="a",
        symbol="BTCUSDT",
        predicted_price=100.0,
        order_price=100.1,
        execution_price=100.2,
        execution_time_ms=20.0,
    )
    analyzer.analyze_execution(
        order_id="b",
        symbol="ETHUSDT",
        predicted_price=200.0,
        order_price=200.2,
        execution_price=200.3,
        execution_time_ms=30.0,
    )
    btc_only = analyzer.recent_by_symbol("BTCUSDT", limit=10)
    assert len(btc_only) == 1
    assert btc_only[0].symbol == "BTCUSDT"


def test_in_memory_subscription_store_for_horizontal_scaling_state() -> None:
    store = InMemorySubscriptionStore()
    store.set_channels("c1", {"predictions", "alerts"})
    assert store.get_channels("c1") == {"predictions", "alerts"}
    remaining = store.remove_channels("c1", {"alerts"})
    assert remaining == {"predictions"}
    store.clear_client("c1")
    assert store.get_channels("c1") == set()
