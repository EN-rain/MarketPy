from __future__ import annotations

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


def _market_data() -> pd.DataFrame:
    start = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    rows = []
    for idx in range(30):
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


def _build_store() -> FeatureStore:
    registry = FeatureRegistry()
    register_price_features(registry)
    register_volume_features(registry)
    register_technical_indicator_features(registry)
    cache = RedisFeatureCache(FakeRedis())
    computer = FeatureComputer(registry, cache)
    validator = FeatureValidator()
    return FeatureStore(registry, computer, validator, cache)


def test_feature_store_registers_and_returns_metadata() -> None:
    store = _build_store()

    metadata = store.get_feature_metadata("rsi_14")

    assert metadata["name"] == "rsi_14"
    assert metadata["version"] == "1.0.0"
    assert metadata["lineage"] == ["ohlcv"]


def test_feature_store_computes_features_with_caching() -> None:
    store = _build_store()
    market_data = _market_data()
    timestamp = market_data["timestamp"].iloc[-1]

    features = store.compute_features(timestamp, market_data, ["return_1", "rsi_14", "volume_ratio_5"])
    cached = store.compute_features(timestamp, market_data, ["return_1", "rsi_14", "volume_ratio_5"])

    assert set(features) == {"return_1", "rsi_14", "volume_ratio_5"}
    assert cached == features
    assert store.cache.metrics.hits >= 3


def test_feature_store_historical_and_validation_paths() -> None:
    store = _build_store()
    market_data = _market_data().tail(5).reset_index(drop=True)
    historical = store.get_historical_features(market_data, ["return_1"])
    result = store.validate({"return_1": historical["return_1"].iloc[-1]}, computed_at=market_data["timestamp"].iloc[-1], now=market_data["timestamp"].iloc[-1])

    assert not historical.empty
    assert result.valid is True


def test_feature_store_point_in_time_computation_excludes_future_rows() -> None:
    store = _build_store()
    market_data = _market_data()
    earlier = market_data["timestamp"].iloc[10]
    truncated = market_data[market_data["timestamp"] <= earlier].copy()

    full_features = store.compute_features(earlier, market_data, ["momentum_5", "rsi_14"])
    truncated_features = store.compute_features(earlier, truncated, ["momentum_5", "rsi_14"])

    assert full_features == truncated_features
