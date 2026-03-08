"""Funding rate data source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean

from .base import AlternativeDataPoint, AlternativeDataSource


@dataclass(slots=True)
class FundingRateSource(AlternativeDataSource):
    exchange_rates: dict[str, float]

    def get_data(self, symbol: str) -> AlternativeDataPoint:
        observed_at = datetime.now(UTC)
        values = list(self.exchange_rates.values())
        payload = {
            "rates": self.exchange_rates,
            "mean_rate": mean(values) if values else 0.0,
            "max_rate": max(values) if values else 0.0,
            "min_rate": min(values) if values else 0.0,
            "anomaly_spread": (max(values) - min(values)) if len(values) > 1 else 0.0,
        }
        return AlternativeDataPoint(
            source="funding_rates",
            symbol=symbol,
            observed_at=observed_at,
            value=payload,
            quality_score=self.quality_score(payload),
            is_stale=self.is_stale(observed_at),
        )

    def normalize_data(self, payload: dict[str, object]) -> dict[str, float]:
        return {
            "mean_rate": float(payload["mean_rate"]),
            "anomaly_spread": float(payload["anomaly_spread"]),
        }
