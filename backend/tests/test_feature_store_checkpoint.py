from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pandas as pd

from backend.features.cache import RedisFeatureCache
from backend.features.computer import FeatureComputer
from backend.features.definitions.price_features import register_price_features
from backend.features.definitions.technical_indicators import register_technical_indicator_features
from backend.features.definitions.volume_features import register_volume_features
from backend.features.registry import FeatureRegistry
from backend.features.store import FeatureStore
from backend.features.validator import FeatureValidator


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def set(self, key: str, value: object, ex: int | None = None) -> None:
        self.values[key] = value


def _build_store() -> FeatureStore:
    registry = FeatureRegistry()
    register_price_features(registry)
    register_volume_features(registry)
    register_technical_indicator_features(registry)
    cache = RedisFeatureCache(FakeRedis())
    return FeatureStore(registry, FeatureComputer(registry, cache), FeatureValidator(), cache)


def _market_data() -> pd.DataFrame:
    start = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    rows = []
    for idx in range(60):
        rows.append(
            {
                "timestamp": start + timedelta(minutes=idx),
                "open": 100 + idx,
                "high": 101 + idx,
                "low": 99 + idx,
                "close": 100.5 + idx,
                "volume": 10 + idx,
            }
        )
    return pd.DataFrame(rows)


def test_feature_store_checkpoint_verifies_behavior_and_latency() -> None:
    store = _build_store()
    market_data = _market_data()
    timestamp = market_data["timestamp"].iloc[-1]

    start = time.perf_counter()
    result = store.compute_features(timestamp, market_data, ["return_1", "rsi_14", "volume_ratio_5"])
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result
    assert store.get_feature_metadata("rsi_14")["lineage"] == ["ohlcv"]
    assert store.get_historical_features(market_data.tail(10), ["return_1"]).shape[0] == 10
    assert elapsed_ms < 50.0
