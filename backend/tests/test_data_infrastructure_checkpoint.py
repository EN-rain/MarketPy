from __future__ import annotations

from backend.monitoring.influx import InfluxMetricWriter


class FakeInfluxClient:
    def __init__(self) -> None:
        self.records = []

    def write(self, bucket: str, org: str, record):
        self.records.append((bucket, org, record))


def test_data_infrastructure_checkpoint_smoke() -> None:
    from pathlib import Path

    migration = Path("deploy/migrations/20260307_add_ml_trading_core_tables.sql")
    assert migration.exists()

    from backend.features.cache import RedisFeatureCache

    class FakeRedis:
        def __init__(self) -> None:
            self.values = {}

        def get(self, key: str):
            return self.values.get(key)

        def set(self, key: str, value, ex=None) -> None:
            self.values[key] = value

    cache = RedisFeatureCache(FakeRedis())
    cache.set_feature("BTCUSDT", "rsi_14", "2026-03-07T12:00:00Z", 50.0)
    assert cache.get_feature("BTCUSDT", "rsi_14", "2026-03-07T12:00:00Z") == 50.0

    writer = InfluxMetricWriter(FakeInfluxClient())
    writer.append("model_performance", fields={"accuracy": 0.61})
    assert writer.flush() == 1
