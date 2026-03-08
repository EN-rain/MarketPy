"""Correlation calculator for risk cockpit heatmaps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import sqrt


@dataclass(frozen=True)
class CorrelationMatrix:
    assets: list[str]
    matrix: list[list[float]]
    window_days: int
    timestamp: datetime


class CorrelationCalculator:
    """Computes rolling pairwise correlations and detects major shifts."""

    def __init__(self, window_days: int = 30):
        self.window_days = window_days

    def calculate_correlations(self, returns_by_asset: dict[str, list[float]]) -> CorrelationMatrix:
        assets = sorted(returns_by_asset.keys())
        matrix: list[list[float]] = []
        for asset_a in assets:
            row: list[float] = []
            series_a = self._truncate(returns_by_asset[asset_a])
            for asset_b in assets:
                series_b = self._truncate(returns_by_asset[asset_b])
                value = self._pearson(series_a, series_b)
                row.append(max(-1.0, min(1.0, value)))
            matrix.append(row)

        return CorrelationMatrix(
            assets=assets,
            matrix=matrix,
            window_days=self.window_days,
            timestamp=datetime.now(UTC),
        )

    def detect_correlation_shifts(
        self,
        previous: CorrelationMatrix,
        current: CorrelationMatrix,
        threshold: float = 0.2,
    ) -> list[tuple[str, str, float, float]]:
        if previous.assets != current.assets:
            raise ValueError("asset sets must match for shift detection")
        shifts: list[tuple[str, str, float, float]] = []
        for i, asset_a in enumerate(current.assets):
            for j, asset_b in enumerate(current.assets):
                if j <= i:
                    continue
                old = previous.matrix[i][j]
                new = current.matrix[i][j]
                if abs(new - old) > threshold:
                    shifts.append((asset_a, asset_b, old, new))
        return shifts

    @staticmethod
    def should_recalculate_daily(now: datetime, last_update: datetime | None) -> bool:
        if last_update is None:
            return True
        return now.date() > last_update.date()

    def _truncate(self, values: list[float]) -> list[float]:
        if not values:
            return [0.0]
        return values[-self.window_days :]

    def _pearson(self, x_values: list[float], y_values: list[float]) -> float:
        n = min(len(x_values), len(y_values))
        if n < 2:
            return 0.0
        x = x_values[-n:]
        y = y_values[-n:]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((x_i - mean_x) * (y_i - mean_y) for x_i, y_i in zip(x, y, strict=False))
        var_x = sum((x_i - mean_x) ** 2 for x_i in x)
        var_y = sum((y_i - mean_y) ** 2 for y_i in y)
        denom = sqrt(var_x * var_y)
        if denom == 0:
            return 0.0
        return cov / denom
