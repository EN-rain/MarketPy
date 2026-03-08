"""Feature store facade."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backend.features.cache import RedisFeatureCache
from backend.features.computer import FeatureComputer
from backend.features.registry import FeatureRegistry
from backend.features.validator import FeatureValidationResult, FeatureValidator


class FeatureStore:
    def __init__(
        self,
        registry: FeatureRegistry,
        computer: FeatureComputer,
        validator: FeatureValidator,
        cache: RedisFeatureCache | None = None,
    ) -> None:
        self.registry = registry
        self.computer = computer
        self.validator = validator
        self.cache = cache

    def compute_features(self, timestamp: datetime, market_data: pd.DataFrame, feature_names: list[str]) -> dict[str, float]:
        return self.computer.compute_features(timestamp, market_data, feature_names)

    def get_historical_features(self, market_data: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
        return self.computer.get_historical_features(market_data, feature_names)

    def get_feature_metadata(self, feature_name: str) -> dict[str, object]:
        metadata = self.registry.metadata(feature_name)
        metadata["lineage"] = metadata["data_sources"]
        return metadata

    def validate(self, features: dict[str, float], *, computed_at: datetime, now: datetime) -> FeatureValidationResult:
        return self.validator.validate(features, computed_at=computed_at, now=now)
