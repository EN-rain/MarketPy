"""Liquidation data source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .base import AlternativeDataPoint, AlternativeDataSource


@dataclass(slots=True)
class LiquidationDataSource(AlternativeDataSource):
    long_liquidations: float
    short_liquidations: float
    levels: dict[str, float]

    def get_data(self, symbol: str) -> AlternativeDataPoint:
        observed_at = datetime.now(UTC)
        total = self.long_liquidations + self.short_liquidations
        imbalance = 0.0 if total == 0 else (self.long_liquidations - self.short_liquidations) / total
        payload = {
            "long_liquidations": self.long_liquidations,
            "short_liquidations": self.short_liquidations,
            "heatmap_levels": self.levels,
            "imbalance": imbalance,
            "cascade_risk": min(abs(imbalance) + (total / 1_000_000), 1.0),
        }
        return AlternativeDataPoint(
            source="liquidations",
            symbol=symbol,
            observed_at=observed_at,
            value=payload,
            quality_score=self.quality_score(payload),
            is_stale=self.is_stale(observed_at),
        )

    def normalize_data(self, payload: dict[str, object]) -> dict[str, float]:
        return {
            "imbalance": float(payload["imbalance"]),
            "cascade_risk": float(payload["cascade_risk"]),
        }
