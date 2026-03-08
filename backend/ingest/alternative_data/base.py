"""Base classes for alternative data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(slots=True)
class AlternativeDataPoint:
    source: str
    symbol: str
    observed_at: datetime
    value: dict[str, Any]
    quality_score: float
    is_stale: bool


class AlternativeDataSource(ABC):
    def quality_score(self, payload: dict[str, Any]) -> float:
        populated = sum(1 for value in payload.values() if value not in (None, "", [], {}))
        return max(0.0, min(populated / max(len(payload), 1), 1.0))

    def is_stale(self, observed_at: datetime, *, now: datetime | None = None) -> bool:
        reference = now or datetime.now(UTC)
        return observed_at < reference - timedelta(minutes=5)

    @abstractmethod
    def get_data(self, symbol: str) -> AlternativeDataPoint:
        """Retrieve raw alternative data."""

    @abstractmethod
    def normalize_data(self, payload: dict[str, Any]) -> dict[str, float]:
        """Normalize the payload for downstream use."""

    def validate_quality(self, point: AlternativeDataPoint) -> bool:
        return 0.0 <= point.quality_score <= 1.0
