"""Performance attribution by strategy, regime, and time."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class AttributionReport:
    by_strategy: dict[str, float]
    by_regime: dict[str, float]
    by_period: dict[str, float]
    total_return: float


class PerformanceAttributor:
    def generate_report(self, frame: pd.DataFrame) -> AttributionReport:
        if frame.empty:
            return AttributionReport(by_strategy={}, by_regime={}, by_period={}, total_return=0.0)
        if "return" not in frame.columns:
            raise ValueError("Attribution frame must include `return` column")
        by_strategy = {
            str(key): float(value)
            for key, value in frame.groupby(frame.get("strategy", "unknown"))["return"].sum().to_dict().items()
        }
        by_regime = {
            str(key): float(value)
            for key, value in frame.groupby(frame.get("regime", "unknown"))["return"].sum().to_dict().items()
        }
        period_index = pd.to_datetime(frame["timestamp"], utc=True).dt.to_period("M").astype(str)
        by_period = {str(key): float(value) for key, value in frame.groupby(period_index)["return"].sum().to_dict().items()}
        return AttributionReport(
            by_strategy=by_strategy,
            by_regime=by_regime,
            by_period=by_period,
            total_return=float(frame["return"].sum()),
        )
