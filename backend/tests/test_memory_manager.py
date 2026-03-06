"""Unit tests for MemoryManager."""

from datetime import UTC, datetime, timedelta

from backend.app.models.market import Candle
from backend.app.models.realtime_config import MemoryConfig, RetentionPolicy
from backend.app.realtime.memory_manager import MemoryManager


def _candle(ts: datetime, price: float) -> Candle:
    return Candle(
        timestamp=ts,
        open=price,
        high=price,
        low=price,
        close=price,
        mid=price,
        bid=price,
        ask=price,
        spread=0.0,
        volume=1.0,
        trade_count=1,
    )


def test_count_based_eviction():
    mm = MemoryManager(MemoryConfig(max_candles_per_market=3, retention_seconds=3600))
    now = datetime.now(UTC)
    for i in range(5):
        mm.add_candle("BTCUSDT", _candle(now + timedelta(seconds=i), 100 + i))
    candles = mm.get_candles("BTCUSDT")
    assert len(candles) == 3
    assert candles[0].close == 102


def test_time_based_eviction():
    mm = MemoryManager(MemoryConfig(max_candles_per_market=100, retention_seconds=60))
    now = datetime.now(UTC)
    mm.add_candle("BTCUSDT", _candle(now - timedelta(minutes=5), 100))
    mm.add_candle("BTCUSDT", _candle(now, 101))
    candles = mm.get_candles("BTCUSDT")
    assert len(candles) == 1
    assert candles[0].close == 101


def test_tier_policy_override():
    mm = MemoryManager(
        MemoryConfig(
            max_candles_per_market=10,
            retention_seconds=3600,
            tier_policies={"high": RetentionPolicy(max_candles=2, retention_seconds=3600)},
        )
    )
    mm.set_market_tier("BTCUSDT", "high")
    now = datetime.now(UTC)
    for i in range(3):
        mm.add_candle("BTCUSDT", _candle(now + timedelta(seconds=i), 100 + i))
    candles = mm.get_candles("BTCUSDT")
    assert len(candles) == 2
    assert candles[0].close == 101


def test_memory_stats():
    mm = MemoryManager(MemoryConfig(max_candles_per_market=5, retention_seconds=3600))
    now = datetime.now(UTC)
    mm.add_candle("ETHUSDT", _candle(now, 50))
    stats = mm.get_memory_stats()
    assert "ETHUSDT" in stats
    assert stats["ETHUSDT"].candle_count == 1
    assert stats["ETHUSDT"].approx_bytes > 0

