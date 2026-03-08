"""Redis-oriented cache primitives for feature serving."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class CacheClient(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any, ex: int | None = None) -> Any: ...
    def mget(self, keys: list[str]) -> list[Any] | None: ...
    def mset(self, mapping: dict[str, Any]) -> Any: ...


@dataclass(slots=True)
class FeatureCacheMetrics:
    hits: int = 0
    misses: int = 0
    writes: int = 0

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.hits / self.requests


@dataclass(slots=True)
class RedisCacheConfig:
    redis_url: str = "redis://localhost:6379/0"
    max_connections: int = 20
    feature_ttl_seconds: int = 60
    market_data_ttl_seconds: int = 1
    prediction_ttl_seconds: int = 300

    def ttl_for_namespace(self, namespace: str) -> int:
        ttl_map = {
            "feature": self.feature_ttl_seconds,
            "market_data": self.market_data_ttl_seconds,
            "prediction": self.prediction_ttl_seconds,
        }
        if namespace not in ttl_map:
            raise ValueError(f"Unsupported cache namespace: {namespace}")
        return ttl_map[namespace]


@dataclass(slots=True)
class RedisFeatureCache:
    client: CacheClient
    config: RedisCacheConfig = field(default_factory=RedisCacheConfig)
    metrics: FeatureCacheMetrics = field(default_factory=FeatureCacheMetrics)

    @staticmethod
    def build_key(symbol: str, feature_name: str, timestamp: str) -> str:
        return f"feature:{symbol}:{feature_name}:{timestamp}"

    def get_features_batch(self, symbol: str, feature_names: list[str], timestamp: str) -> dict[str, Any]:
        if not feature_names:
            return {}
        keys = [self.build_key(symbol, feature_name, timestamp) for feature_name in feature_names]
        if hasattr(self.client, "mget"):
            values = self.client.mget(keys)
            if values is not None:
                output: dict[str, Any] = {}
                for index, feature_name in enumerate(feature_names):
                    value = values[index] if index < len(values) else None
                    if value is None:
                        self.metrics.misses += 1
                        continue
                    self.metrics.hits += 1
                    output[feature_name] = value
                return output
        output: dict[str, Any] = {}
        for feature_name in feature_names:
            value = self.get_feature(symbol, feature_name, timestamp)
            if value is not None:
                output[feature_name] = value
        return output

    def get_feature(self, symbol: str, feature_name: str, timestamp: str) -> Any | None:
        key = self.build_key(symbol, feature_name, timestamp)
        value = self.client.get(key)
        if value is None:
            self.metrics.misses += 1
            return None
        self.metrics.hits += 1
        return value

    def set_feature(self, symbol: str, feature_name: str, timestamp: str, value: Any) -> None:
        key = self.build_key(symbol, feature_name, timestamp)
        self.client.set(key, value, ex=self.config.ttl_for_namespace("feature"))
        self.metrics.writes += 1

    def set_features_batch(self, symbol: str, timestamp: str, values: dict[str, Any]) -> None:
        if not values:
            return
        ttl = self.config.ttl_for_namespace("feature")
        if hasattr(self.client, "mset"):
            mapping = {
                self.build_key(symbol, feature_name, timestamp): value
                for feature_name, value in values.items()
            }
            self.client.mset(mapping)
            for key in mapping:
                self.client.expire(key, ttl) if hasattr(self.client, "expire") else self.client.set(key, mapping[key], ex=ttl)
            self.metrics.writes += len(mapping)
            return
        for feature_name, value in values.items():
            self.set_feature(symbol, feature_name, timestamp, value)
