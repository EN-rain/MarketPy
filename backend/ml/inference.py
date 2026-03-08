"""Inference engine with feature caching, logging, and signal generation."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from backend.app.models.config import settings
from backend.app.models.signal import EdgeDecision, Horizon, Prediction, Signal
from backend.ml.confidence_intervals import QuantileIntervalEstimator
from backend.ml.model_manager import DeploymentMode, ModelManager
from backend.ml.prediction_tracker import PredictionTracker, get_prediction_tracker

logger = logging.getLogger(__name__)

MODEL_HORIZON_MAP: dict[str, Horizon] = {
    "model_5m": Horizon.M5,
    "model_15m": Horizon.M15,
    "model_1h": Horizon.H1,
    "model_4h": Horizon.H4,
    "model_6h": Horizon.H6,
    "model_1d": Horizon.D1,
}

DERIVED_MODEL_FALLBACKS: dict[str, str] = {
    "model_1h": "model_5m",
    "model_6h": "model_5m",
    "model_1d": "model_5m",
}


@dataclass(slots=True)
class LatencyTracker:
    feature_latencies_ms: list[float]
    inference_latencies_ms: list[float]

    def record_feature(self, value_ms: float) -> None:
        self.feature_latencies_ms.append(float(value_ms))
        del self.feature_latencies_ms[:-500]

    def record_inference(self, value_ms: float) -> None:
        self.inference_latencies_ms.append(float(value_ms))
        del self.inference_latencies_ms[:-500]

    @staticmethod
    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(math.ceil(len(ordered) * 0.95) - 1)))
        return float(ordered[index])

    def snapshot(self) -> dict[str, float]:
        return {
            "feature_p95_ms": self._p95(self.feature_latencies_ms),
            "inference_p95_ms": self._p95(self.inference_latencies_ms),
        }


class _TTLFeatureCache:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, dict[str, float]]] = {}

    def get(self, key: str) -> dict[str, float] | None:
        record = self._store.get(key)
        if record is None:
            return None
        inserted_at, value = record
        if time.time() - inserted_at > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        return dict(value)

    def set(self, key: str, value: dict[str, float]) -> None:
        self._store[key] = (time.time(), dict(value))


class PredictionLogger:
    """SQLite-backed prediction log used for monitoring and drift detection."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                horizon TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                predicted_return REAL NOT NULL,
                predicted_price REAL NOT NULL,
                confidence REAL NOT NULL,
                features TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_predictions_market_time ON predictions (market_id, timestamp)"
        )
        self._conn.commit()

    def log(
        self,
        *,
        market_id: str,
        model_id: str,
        model_version: str,
        prediction: Prediction,
        features: dict[str, float],
        metadata: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO predictions (
                market_id, model_id, model_version, horizon, timestamp,
                predicted_return, predicted_price, confidence, features, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                market_id,
                model_id,
                model_version,
                prediction.horizon.value,
                datetime.now(UTC).isoformat(),
                prediction.predicted_return,
                prediction.predicted_price,
                prediction.confidence,
                json.dumps(features),
                json.dumps(metadata),
            ),
        )
        self._conn.commit()

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT market_id, model_id, model_version, horizon, timestamp,
                   predicted_return, predicted_price, confidence, features, metadata
            FROM predictions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


class Inferencer:
    """Loads model artifacts and performs calibrated inference."""

    def __init__(
        self,
        model_dir: str | Path | None = None,
        *,
        registry_dir: str | Path | None = None,
        feature_ttl_seconds: int = 60,
        prediction_log_path: str | Path | None = None,
        tracker: PredictionTracker | None = None,
    ) -> None:
        self.model_dir = Path(model_dir or settings.model_dir)
        self.registry_dir = Path(registry_dir) if registry_dir else None
        self.models: dict[str, dict[str, Any]] = {}
        self.metrics: dict[str, dict[str, Any]] = {}
        self.thresholds: dict[str, dict[str, float]] = {}
        self.feature_cache = _TTLFeatureCache(ttl_seconds=feature_ttl_seconds)
        self.latency = LatencyTracker([], [])
        self.tracker = tracker or get_prediction_tracker()
        self.prediction_logger = PredictionLogger(
            prediction_log_path or (Path(settings.data_dir) / "prediction_logs.sqlite")
        )
        self.model_manager = ModelManager(self.registry_dir) if self.registry_dir else None
        self.interval_estimator = QuantileIntervalEstimator()
        self._active_models_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._active_models_ttl_seconds = 5.0
        self._load_models()

    @staticmethod
    def _clone_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        return {
            **artifact,
            "models": dict(artifact.get("models", {})),
            "weights": dict(artifact.get("weights", {})),
            "thresholds": dict(artifact.get("thresholds", {"buy_threshold": 0.0, "sell_threshold": 0.0})),
        }

    def _load_models(self) -> None:
        for model_name in MODEL_HORIZON_MAP:
            model_path = self.model_dir / f"{model_name}.joblib"
            if not model_path.exists():
                continue
            artifact = joblib.load(model_path)
            if isinstance(artifact, dict) and "models" in artifact and "weights" in artifact:
                self.models[model_name] = artifact
            else:
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

        for model_name, fallback_model in DERIVED_MODEL_FALLBACKS.items():
            if model_name in self.models or fallback_model not in self.models:
                continue
            self.models[model_name] = self._clone_artifact(self.models[fallback_model])
            fallback_metrics = dict(self.metrics.get(fallback_model, {}))
            self.metrics[model_name] = {
                **fallback_metrics,
                "model_name": model_name,
                "derived_from": fallback_model,
                "is_derived": True,
                "dataset": str(fallback_metrics.get("dataset") or "derived_from_model_5m"),
            }
            self.thresholds[model_name] = self.models[model_name].get(
                "thresholds", {"buy_threshold": 0.0, "sell_threshold": 0.0}
            )

        if not self.models:
            raise FileNotFoundError(
                f"No trained model artifacts found in {self.model_dir}. "
                "Expected files: model_5m.joblib, model_1h.joblib, model_6h.joblib, model_1d.joblib"
            )

    def get_active_models(self) -> dict[str, dict[str, Any]]:
        if self.model_manager is not None and self._active_models_cache is not None:
            cached_at, cached_payload = self._active_models_cache
            if time.time() - cached_at <= self._active_models_ttl_seconds:
                return dict(cached_payload)

        if self.model_manager is None:
            return dict(self.models)
        active: dict[str, dict[str, Any]] = {}
        for model_id in self.available_horizons:
            try:
                deployed = self.model_manager.get_model(model_id, deployment_mode=DeploymentMode.PRODUCTION)
            except Exception:
                try:
                    deployed = self.model_manager.get_model(model_id, deployment_mode=DeploymentMode.AB_TEST)
                except Exception:
                    continue
            if model_id in self.models:
                active[model_id] = self.models[model_id] | {"model_version": deployed.version}
        resolved = active or dict(self.models)
        self._active_models_cache = (time.time(), dict(resolved))
        return resolved

    def compute_inference_features(
        self,
        *,
        market_id: str,
        timestamp: datetime,
        market_snapshot: dict[str, float],
        alternative_features: dict[str, float] | None = None,
        historical_window: list[dict[str, float]] | None = None,
    ) -> dict[str, float]:
        started = time.perf_counter()
        cache_key = f"{market_id}:{timestamp.replace(second=0, microsecond=0).isoformat()}"
        cached = self.feature_cache.get(cache_key)
        if cached is not None:
            self.latency.record_feature((time.perf_counter() - started) * 1000)
            return cached

        features = {key: float(value) for key, value in market_snapshot.items() if isinstance(value, (int, float))}
        if alternative_features:
            features.update(
                {key: float(value) for key, value in alternative_features.items() if isinstance(value, (int, float))}
            )
        if "mid" not in features and "close" in features:
            features["mid"] = features["close"]
        if "spread" not in features:
            best_bid = features.get("best_bid", features.get("bid", features.get("mid", 0.0)))
            best_ask = features.get("best_ask", features.get("ask", features.get("mid", 0.0)))
            features["spread"] = max(0.0, best_ask - best_bid)
        mid = max(1e-9, float(features.get("mid", 0.0)))
        features["spread_pct"] = features["spread"] / mid

        if historical_window:
            mids = np.asarray([float(item.get("mid", mid)) for item in historical_window[-48:]], dtype=float)
            volumes = np.asarray([float(item.get("volume", 0.0)) for item in historical_window[-48:]], dtype=float)
            if len(mids) >= 2:
                returns = np.diff(np.log(np.clip(mids, 1e-9, None)))
                features["ret_1"] = float(returns[-1])
                features["volatility_12"] = float(np.std(returns[-12:])) if len(returns) >= 12 else float(np.std(returns))
                features["volatility_48"] = float(np.std(returns))
                features["momentum_12"] = float(mids[-1] / mids[max(0, len(mids) - 12)] - 1.0) if len(mids) >= 12 else 0.0
            if len(volumes) > 0:
                features["volume_mean_12"] = float(np.mean(volumes[-12:]))
                features["volume_zscore"] = float(
                    (volumes[-1] - np.mean(volumes)) / max(np.std(volumes), 1e-9)
                )

        validated: dict[str, float] = {}
        for key, value in features.items():
            if not math.isfinite(value):
                validated[key] = 0.0
            else:
                validated[key] = float(max(-1e6, min(1e6, value)))

        self.feature_cache.set(cache_key, validated)
        self.latency.record_feature((time.perf_counter() - started) * 1000)
        return validated

    def _predict_one(self, model_name: str, X: np.ndarray) -> float:
        artifact = self.models[model_name]
        weighted = 0.0
        for name, model in artifact["models"].items():
            pred = float(model.predict(X)[0])
            weighted += float(artifact["weights"].get(name, 0.0)) * pred
        calibrator = artifact.get("calibrator")
        if calibrator is not None:
            try:
                weighted = float(calibrator.transform(np.asarray([weighted]))[0])
            except Exception:
                pass
        return weighted

    def calibrate_confidence(self, model_name: str, predicted_return: float) -> tuple[float, tuple[float, float], bool]:
        rmse = float(self.metrics.get(model_name, {}).get("validation", {}).get("rmse", self.metrics.get(model_name, {}).get("rmse", 0.02)))
        candidate_count = len(self.models.get(model_name, {}).get("models", {}))
        conf_rmse = max(0.0, min(1.0, 1.0 - rmse / 0.05))
        conf_ensemble = min(1.0, 0.6 + 0.2 * candidate_count)
        confidence = float(max(0.0, min(1.0, 0.7 * conf_rmse + 0.3 * conf_ensemble)))
        interval_scale = max(rmse, abs(predicted_return) * (1.0 - confidence))
        return confidence, (predicted_return - interval_scale, predicted_return + interval_scale), confidence < 0.6

    def get_threshold(self, horizon: Horizon) -> dict[str, float]:
        model_name = {value: key for key, value in MODEL_HORIZON_MAP.items()}[horizon]
        return self.thresholds.get(model_name, {"buy_threshold": 0.0, "sell_threshold": 0.0})

    def predict(
        self,
        features: dict[str, float],
        current_mid: float,
        feature_columns: list[str] | None = None,
        *,
        market_id: str | None = None,
    ) -> list[Prediction]:
        started = time.perf_counter()
        active_models = self.get_active_models()
        if not active_models:
            return []
        if feature_columns is None:
            sample = next(iter(active_models.values()))
            feature_columns = sample.get("feature_columns") or sorted(features.keys())

        X = np.array([[features.get(column, 0.0) for column in feature_columns]], dtype=float)
        predictions: list[Prediction] = []
        for model_name, horizon in MODEL_HORIZON_MAP.items():
            if model_name not in active_models:
                continue
            pred_return = self._predict_one(model_name, X)
            pred_price = current_mid * math.exp(pred_return)
            confidence, interval, low_confidence = self.calibrate_confidence(model_name, pred_return)
            interval_stats = self.interval_estimator.estimate(
                predicted_return=pred_return,
                residuals=np.asarray([pred_return - interval[0], interval[1] - pred_return], dtype=float),
            )
            if self.metrics.get(model_name, {}).get("is_derived"):
                confidence *= 0.92
            predictions.append(
                Prediction(
                    horizon=horizon,
                    predicted_return=float(pred_return),
                    predicted_price=float(pred_price),
                    confidence=float(max(0.0, min(1.0, min(confidence, interval_stats.confidence)))),
                    interval_low=float(current_mid * math.exp(interval_stats.lower)),
                    interval_high=float(current_mid * math.exp(interval_stats.upper)),
                )
            )
            if market_id:
                self.prediction_logger.log(
                    market_id=market_id,
                    model_id=model_name,
                    model_version=str(active_models[model_name].get("model_version", "local")),
                    prediction=predictions[-1],
                    features=features,
                    metadata={
                        "prediction_interval": interval,
                        "low_confidence": low_confidence,
                        "latency_target_ms": 100,
                    },
                )

        self.latency.record_inference((time.perf_counter() - started) * 1000)
        return predictions

    def predict_batch(
        self,
        *,
        features_batch: list[dict[str, float]],
        current_mids: list[float],
        feature_columns: list[str] | None = None,
    ) -> list[list[Prediction]]:
        if len(features_batch) != len(current_mids):
            raise ValueError("features_batch and current_mids must have identical length")
        return [
            self.predict(features=features, current_mid=current_mid, feature_columns=feature_columns)
            for features, current_mid in zip(features_batch, current_mids, strict=False)
        ]

    def generate_signal(
        self,
        *,
        market_id: str,
        current_bid: float,
        current_ask: float,
        predictions: list[Prediction],
        regime_adjustment: float = 1.0,
    ) -> Signal:
        current_mid = (current_bid + current_ask) / 2.0
        best = max(predictions, key=lambda item: abs(item.predicted_price - current_mid), default=None)
        edge = 0.0
        decision = EdgeDecision.HOLD
        reason = "no_predictions"
        if best is not None:
            edge = (best.predicted_price - current_mid) * regime_adjustment
            threshold = current_mid * 0.001
            if edge > threshold:
                decision = EdgeDecision.BUY
                reason = f"{best.horizon.value}_upside"
            elif edge < -threshold:
                decision = EdgeDecision.SELL
                reason = f"{best.horizon.value}_downside"
            else:
                reason = "edge_below_threshold"

        signal = Signal(
            market_id=market_id,
            timestamp=datetime.now(UTC),
            current_mid=current_mid,
            current_bid=current_bid,
            current_ask=current_ask,
            predictions=predictions,
            edge=edge,
            decision=decision,
            strategy="ai",
            reason=reason,
        )
        self.tracker.record_signal(signal)
        return signal

    def inference_health(self) -> dict[str, float]:
        return self.latency.snapshot()

    @property
    def available_horizons(self) -> list[str]:
        return list(self.models.keys())


InferenceEngine = Inferencer
