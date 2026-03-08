"""Memory manager for realtime candle storage with retention policies."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.models.realtime_config import MemoryConfig, RetentionPolicy


@dataclass
class MemoryStats:
    """Memory usage statistics for a single market."""

    market_id: str
    candle_count: int
    oldest_timestamp: datetime | None
    newest_timestamp: datetime | None
    approx_bytes: int
    tier: str | None = None


class MemoryManager:
    """Manage in-memory candle history with count/time/tier retention."""

    def __init__(self, config: MemoryConfig):
        self.default_max_candles = config.max_candles_per_market
        self.default_retention_seconds = config.retention_seconds
        self.tier_policies = config.tier_policies

        self._candles: dict[str, list[Any]] = defaultdict(list)
        self._market_tiers: dict[str, str] = {}

    def set_market_tier(self, market_id: str, tier: str) -> None:
        """Assign a tier name to a market for policy lookup."""
        self._market_tiers[market_id] = tier

    def get_candles(self, market_id: str) -> list[Any]:
        """Return a copy of candles for a market."""
        return list(self._candles.get(market_id, []))

    def add_candle(self, market_id: str, candle: Any) -> None:
        """Add a candle and immediately enforce retention policies."""
        self._candles[market_id].append(candle)
        self.evict_old_candles(market_id)

    def evict_old_candles(self, market_id: str) -> int:
        """Evict candles outside retention rules. Returns eviction count."""
        if market_id not in self._candles:
            return 0

        candles = self._candles[market_id]
        if not candles:
            return 0

        policy = self._get_policy_for_market(market_id)
        original_len = len(candles)

        # Count-based retention.
        if len(candles) > policy.max_candles:
            self._candles[market_id] = candles[-policy.max_candles :]
            candles = self._candles[market_id]

        # Time-based retention.
        cutoff = datetime.now(UTC) - timedelta(seconds=policy.retention_seconds)
        self._candles[market_id] = [
            candle
            for candle in candles
            if self._extract_timestamp(candle) is None
            or self._extract_timestamp(candle) >= cutoff
        ]

        return max(0, original_len - len(self._candles[market_id]))

    def get_memory_stats(self) -> dict[str, MemoryStats]:
        """Get memory statistics for all tracked markets."""
        result: dict[str, MemoryStats] = {}
        for market_id, candles in self._candles.items():
            timestamps = [
                ts for ts in (self._extract_timestamp(candle) for candle in candles) if ts is not None
            ]
            oldest = min(timestamps) if timestamps else None
            newest = max(timestamps) if timestamps else None
            # Approximate size using a conservative per-candle estimate.
            approx_bytes = len(candles) * 320
            result[market_id] = MemoryStats(
                market_id=market_id,
                candle_count=len(candles),
                oldest_timestamp=oldest,
                newest_timestamp=newest,
                approx_bytes=approx_bytes,
                tier=self._market_tiers.get(market_id),
            )
        return result

    def _get_policy_for_market(self, market_id: str) -> RetentionPolicy:
        tier = self._market_tiers.get(market_id)
        if tier and tier in self.tier_policies:
            return self.tier_policies[tier]
        return RetentionPolicy(
            max_candles=self.default_max_candles,
            retention_seconds=self.default_retention_seconds,
        )

    @staticmethod
    def _extract_timestamp(candle: Any) -> datetime | None:
        ts = getattr(candle, "timestamp", None)
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        return None

