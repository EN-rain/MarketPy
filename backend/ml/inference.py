"""Real-time inference engine for ensemble models."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from backend.app.models.config import settings
from backend.app.models.signal import Horizon, Prediction

logger = logging.getLogger(__name__)


class Inferencer:
    """Loads ensemble artifacts and produces calibrated predictions."""

    def __init__(self, model_dir: str | Path | None = None) -> None:
        self.model_dir = Path(model_dir or settings.model_dir)
        self.models: dict[str, dict[str, Any]] = {}
        self.metrics: dict[str, dict[str, Any]] = {}
        self.thresholds: dict[str, dict[str, float]] = {}
        self._load_models()

    def _load_models(self) -> None:
        horizon_map = {
            "model_1h": Horizon.H1,
            "model_6h": Horizon.H6,
            "model_1d": Horizon.D1,
        }
        for model_name in horizon_map:
            model_path = self.model_dir / f"{model_name}.joblib"
            if not model_path.exists():
                logger.warning("Model not found: %s", model_path)
                continue
            artifact = joblib.load(model_path)
            if isinstance(artifact, dict) and "models" in artifact and "weights" in artifact:
                self.models[model_name] = artifact
            else:
                # Backward compatibility with single-model artifacts.
                self.models[model_name] = {
                    "models": {"xgb": artifact},
                    "weights": {"xgb": 1.0},
                    "calibrator": None,
                    "feature_columns": None,
                    "thresholds": {"buy_threshold": 0.0, "sell_threshold": 0.0},
                }
            metrics_path = self.model_dir / f"{model_name}_metrics.json"
            if metrics_path.exists():
                try:
                    self.metrics[model_name] = json.loads(metrics_path.read_text(encoding="utf-8"))
                except Exception:
                    self.metrics[model_name] = {}
            self.thresholds[model_name] = self.models[model_name].get(
                "thresholds", {"buy_threshold": 0.0, "sell_threshold": 0.0}
            )
            logger.info("Loaded model: %s", model_name)

    def _predict_one(self, model_name: str, X: np.ndarray) -> float:
        artifact = self.models[model_name]
        weighted = 0.0
        models = artifact["models"]
        weights = artifact["weights"]
        for name, model in models.items():
            pred = float(model.predict(X)[0])
            weighted += float(weights.get(name, 0.0)) * pred
        calibrator = artifact.get("calibrator")
        if calibrator is not None:
            try:
                weighted = float(calibrator.transform(np.asarray([weighted]))[0])
            except Exception:
                pass
        return weighted

    def get_threshold(self, horizon: Horizon) -> dict[str, float]:
        map_name = {
            Horizon.H1: "model_1h",
            Horizon.H6: "model_6h",
            Horizon.D1: "model_1d",
        }[horizon]
        return self.thresholds.get(map_name, {"buy_threshold": 0.0, "sell_threshold": 0.0})

    def predict(
        self,
        features: dict[str, float],
        current_mid: float,
        feature_columns: list[str] | None = None,
    ) -> list[Prediction]:
        if not self.models:
            return []
        if feature_columns is None:
            # Prefer trained feature order if available.
            sample = next(iter(self.models.values()))
            trained_cols = sample.get("feature_columns")
            feature_columns = trained_cols or sorted(features.keys())

        X = np.array([[features.get(col, 0.0) for col in feature_columns]])
        predictions: list[Prediction] = []
        horizon_map = {
            "model_1h": Horizon.H1,
            "model_6h": Horizon.H6,
            "model_1d": Horizon.D1,
        }
        for model_name, horizon in horizon_map.items():
            if model_name not in self.models:
                continue
            pred_return = self._predict_one(model_name, X)
            pred_price = current_mid * math.exp(pred_return)

            rmse = float(self.metrics.get(model_name, {}).get("rmse", 0.02))
            candidate_count = len(self.models[model_name]["models"])
            # Confidence incorporates calibration quality and ensemble size.
            conf_rmse = max(0.0, min(1.0, 1.0 - rmse / 0.05))
            conf_ensemble = min(1.0, 0.6 + 0.2 * candidate_count)
            confidence = float(max(0.0, min(1.0, 0.7 * conf_rmse + 0.3 * conf_ensemble)))

            predictions.append(
                Prediction(
                    horizon=horizon,
                    predicted_return=float(pred_return),
                    predicted_price=float(pred_price),
                    confidence=confidence,
                )
            )
        return predictions

    @property
    def available_horizons(self) -> list[str]:
        return list(self.models.keys())

