"""Feature computation utilities."""

from __future__ import annotations

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd

from backend.features.cache import RedisFeatureCache
from backend.features.registry import FeatureRegistry


class FeatureComputer:
    def __init__(self, registry: FeatureRegistry, cache: RedisFeatureCache | None = None) -> None:
        self.registry = registry
        self.cache = cache

    def compute_features(
        self,
        timestamp: datetime,
        market_data: pd.DataFrame,
        feature_names: list[str],
    ) -> dict[str, float]:
        point_in_time = market_data[market_data["timestamp"] <= timestamp].copy()
        if point_in_time.empty:
            raise ValueError("No market data available at or before requested timestamp")
        result: dict[str, float] = {}
        ts_key = timestamp.isoformat()
        cached_values = self.cache.get_features_batch("market", feature_names, ts_key) if self.cache else {}
        for name, value in cached_values.items():
            result[name] = float(value)

        missing = [name for name in feature_names if name not in result]
        if missing:
            workers = min(4, len(missing))

            def _compute(name: str) -> tuple[str, float]:
                feature = self.registry.get_feature(name)
                if feature.compute_fn is None:
                    raise ValueError(f"Feature {name} has no compute function")
                return name, float(feature.compute_fn(point_in_time))

            if workers > 1:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    computed_pairs = list(pool.map(_compute, missing))
            else:
                computed_pairs = [_compute(missing[0])]

            computed = {name: value for name, value in computed_pairs}
            result.update(computed)
            if self.cache is not None:
                self.cache.set_features_batch("market", ts_key, computed)
        return result

    def get_historical_features(self, market_data: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for timestamp in market_data["timestamp"]:
            row = {"timestamp": timestamp}
            row.update(self.compute_features(timestamp, market_data, feature_names))
            rows.append(row)
        return pd.DataFrame(rows)
