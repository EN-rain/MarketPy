from __future__ import annotations

from backend.features.cache import RedisCacheConfig, RedisFeatureCache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.expirations: dict[str, int | None] = {}

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def set(self, key: str, value: object, ex: int | None = None) -> None:
        self.values[key] = value
        self.expirations[key] = ex


def test_feature_cache_uses_expected_key_format_and_ttl() -> None:
    redis = FakeRedis()
    cache = RedisFeatureCache(redis, RedisCacheConfig(feature_ttl_seconds=60))

    cache.set_feature("BTCUSDT", "rsi_14", "2026-03-07T12:00:00Z", 52.4)

    key = "feature:BTCUSDT:rsi_14:2026-03-07T12:00:00Z"
    assert redis.values[key] == 52.4
    assert redis.expirations[key] == 60
    assert cache.metrics.writes == 1


def test_feature_cache_tracks_hits_and_misses() -> None:
    redis = FakeRedis()
    cache = RedisFeatureCache(redis)
    cache.set_feature("BTCUSDT", "volatility_20", "2026-03-07T12:00:00Z", 0.12)

    assert cache.get_feature("BTCUSDT", "volatility_20", "2026-03-07T12:00:00Z") == 0.12
    assert cache.get_feature("BTCUSDT", "missing", "2026-03-07T12:00:00Z") is None
    assert cache.metrics.hits == 1
    assert cache.metrics.misses == 1
    assert cache.metrics.hit_rate == 0.5


def test_cache_config_exposes_namespace_ttls() -> None:
    config = RedisCacheConfig(feature_ttl_seconds=60, market_data_ttl_seconds=1, prediction_ttl_seconds=300)

    assert config.ttl_for_namespace("feature") == 60
    assert config.ttl_for_namespace("market_data") == 1
    assert config.ttl_for_namespace("prediction") == 300
