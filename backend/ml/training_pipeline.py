"""Integrated ML training pipeline using indicators, scaling, and importance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pandas is required for MLTrainingPipeline") from exc

from sklearn.ensemble import RandomForestRegressor

from backend.dataset.indicators import IndicatorConfig, IndicatorPipeline
from backend.dataset.scalers import FeatureScaler, ScalerType
from backend.ml.feature_importance_tracker import FeatureImportanceResult, FeatureImportanceTracker

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrainingOutput:
    model: Any
    feature_names: list[str]
    scaler: FeatureScaler
    importance: FeatureImportanceResult
    train_rows: int
    test_rows: int


class MLTrainingPipeline:
    """End-to-end training helper for raw OHLCV -> model artifacts."""

    def __init__(
        self,
        indicator_config: IndicatorConfig | None = None,
        scaler_type: ScalerType = ScalerType.STANDARD,
        importance_tracker: FeatureImportanceTracker | None = None,
    ) -> None:
        self.indicator_pipeline = IndicatorPipeline(indicator_config or IndicatorConfig())
        self.scaler = FeatureScaler(scaler_type=scaler_type)
        self.importance_tracker = importance_tracker or FeatureImportanceTracker()

    def _split(self, X: np.ndarray, y: np.ndarray, train_ratio: float = 0.8) -> tuple[np.ndarray, ...]:
        pivot = max(1, int(len(X) * train_ratio))
        return X[:pivot], X[pivot:], y[:pivot], y[pivot:]

    def train(
        self,
        model_id: str,
        raw_ohlcv: pd.DataFrame,
        target_column: str = "target",
    ) -> TrainingOutput:
        if target_column not in raw_ohlcv.columns:
            raise ValueError(f"Missing target column '{target_column}' for ML training")

        enriched = self.indicator_pipeline.compute(raw_ohlcv)
        enriched = enriched.copy()
        enriched[target_column] = raw_ohlcv[target_column]
        enriched = enriched.dropna()
        if enriched.empty:
            raise ValueError("Not enough rows after indicator + NaN cleanup")

        feature_cols = [
            col for col in enriched.columns if col not in {"timestamp", target_column}
        ]
        X = enriched[feature_cols].to_numpy()
        y = enriched[target_column].to_numpy(dtype=float)

        X_train, X_test, y_train, y_test = self._split(X, y)
        X_train_scaled, X_test_scaled = self.scaler.fit_train_transform_test(X_train, X_test)

        model = RandomForestRegressor(
            n_estimators=200,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train_scaled, y_train)
        score = model.score(X_test_scaled, y_test) if len(X_test_scaled) else None
        logger.info("MLTrainingPipeline trained model_id=%s test_score=%s", model_id, score)

        importance = self.importance_tracker.from_tree_model(
            model_id=model_id,
            feature_names=feature_cols,
            model=model,
        )
        self.importance_tracker.save(importance)

        return TrainingOutput(
            model=model,
            feature_names=feature_cols,
            scaler=self.scaler,
            importance=importance,
            train_rows=len(X_train_scaled),
            test_rows=len(X_test_scaled),
        )
