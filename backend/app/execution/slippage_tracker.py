"""Slippage tracking and analysis for execution quality."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import sqrt
from statistics import mean


@dataclass(frozen=True)
class SlippageRecord:
    symbol: str
    side: str
    expected_price: float
    executed_price: float
    size: float
    timestamp: datetime
    volatility: float = 0.0
    volume: float = 0.0
    spread: float = 0.0

    @property
    def slippage_bps(self) -> float:
        if self.expected_price == 0:
            return 0.0
        raw = ((self.executed_price - self.expected_price) / self.expected_price) * 10_000.0
        if self.side.upper() == "SELL":
            raw = -raw
        return raw


@dataclass(frozen=True)
class SlippageAnalysis:
    count: int
    avg_slippage_bps: float
    by_symbol: dict[str, float]
    by_size_bucket: dict[str, float]
    by_hour: dict[int, float]
    condition_correlations: dict[str, float]


class SlippageTracker:
    """Tracks and aggregates execution slippage records."""

    def __init__(self) -> None:
        self.records: list[SlippageRecord] = []

    def record_execution(
        self,
        symbol: str,
        side: str,
        expected_price: float,
        executed_price: float,
        size: float,
        timestamp: datetime | None = None,
        volatility: float = 0.0,
        volume: float = 0.0,
        spread: float = 0.0,
    ) -> SlippageRecord:
        record = SlippageRecord(
            symbol=symbol,
            side=side,
            expected_price=expected_price,
            executed_price=executed_price,
            size=size,
            timestamp=timestamp or datetime.now(UTC),
            volatility=volatility,
            volume=volume,
            spread=spread,
        )
        self.records.append(record)
        return record

    def detect_slippage_alert(self, record: SlippageRecord, threshold_bps: float = 20.0) -> bool:
        return abs(record.slippage_bps) >= abs(threshold_bps)

    def analyze_patterns(self) -> SlippageAnalysis:
        if not self.records:
            return SlippageAnalysis(
                count=0,
                avg_slippage_bps=0.0,
                by_symbol={},
                by_size_bucket={},
                by_hour={},
                condition_correlations={"volatility": 0.0, "volume": 0.0, "spread": 0.0},
            )

        by_symbol = self._group_mean(self.records, key_fn=lambda item: item.symbol)
        by_size_bucket = self._group_mean(
            self.records, key_fn=lambda item: self._size_bucket(item.size)
        )
        by_hour = self._group_mean(self.records, key_fn=lambda item: item.timestamp.hour)

        slips = [item.slippage_bps for item in self.records]
        correlations = {
            "volatility": self._pearson(slips, [item.volatility for item in self.records]),
            "volume": self._pearson(slips, [item.volume for item in self.records]),
            "spread": self._pearson(slips, [item.spread for item in self.records]),
        }

        return SlippageAnalysis(
            count=len(self.records),
            avg_slippage_bps=mean(slips),
            by_symbol={str(k): v for k, v in by_symbol.items()},
            by_size_bucket={str(k): v for k, v in by_size_bucket.items()},
            by_hour={int(k): v for k, v in by_hour.items()},
            condition_correlations=correlations,
        )

    def _group_mean(self, items: list[SlippageRecord], key_fn):
        grouped: dict[object, list[float]] = {}
        for item in items:
            key = key_fn(item)
            grouped.setdefault(key, []).append(item.slippage_bps)
        return {key: mean(values) for key, values in grouped.items()}

    def _size_bucket(self, size: float) -> str:
        if size < 1:
            return "small"
        if size < 10:
            return "medium"
        return "large"

    def _pearson(self, x_values: list[float], y_values: list[float]) -> float:
        n = min(len(x_values), len(y_values))
        if n < 2:
            return 0.0
        x = x_values[:n]
        y = y_values[:n]
        x_mean = mean(x)
        y_mean = mean(y)
        cov = sum((x_i - x_mean) * (y_i - y_mean) for x_i, y_i in zip(x, y, strict=False))
        var_x = sum((x_i - x_mean) ** 2 for x_i in x)
        var_y = sum((y_i - y_mean) ** 2 for y_i in y)
        denom = sqrt(var_x * var_y)
        if denom == 0:
            return 0.0
        return max(-1.0, min(1.0, cov / denom))
