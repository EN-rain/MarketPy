"""Phase 9 inference pipeline tests."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings as hyp_settings
from hypothesis import strategies as st

from backend.app.models.signal import EdgeDecision, Horizon
from backend.ml.drift_detection import DriftDetector
from backend.ml.explainability import ExplainabilityEngine
from backend.ml.inference import Inferencer
from backend.ml.model_manager import DeploymentMode, ModelManager


class _ConstantModel:
    def __init__(self, value: float = 0.01) -> None:
        self.value = value
        self.feature_importances_ = np.asarray([0.7, 0.2, 0.1], dtype=float)

    def predict(self, X):  # noqa: N803
        return np.full(len(X), self.value, dtype=float)


def _write_artifact(model_dir: Path, model_name: str = "model_5m", value: float = 0.01) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "models": {"xgb": _ConstantModel(value)},
        "weights": {"xgb": 1.0},
        "feature_columns": ["mid", "spread_pct", "ret_1"],
        "thresholds": {"buy_threshold": 0.0, "sell_threshold": 0.0},
    }
    joblib.dump(artifact, model_dir / f"{model_name}.joblib")
    (model_dir / f"{model_name}_metrics.json").write_text(
        '{"rmse": 0.01, "validation": {"rmse": 0.01}}',
        encoding="utf-8",
    )


def test_feature_cache_hit_and_ttl_expiration(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    _write_artifact(model_dir)
    inferencer = Inferencer(model_dir=model_dir, feature_ttl_seconds=1, prediction_log_path=tmp_path / "pred.sqlite")
    timestamp = datetime.now(UTC)
    snapshot = {"mid": 100.0, "best_bid": 99.9, "best_ask": 100.1, "volume": 500.0}
    history = [{"mid": 99.0 + i * 0.1, "volume": 400.0 + i} for i in range(20)]

    first = inferencer.compute_inference_features(
        market_id="BTCUSDT",
        timestamp=timestamp,
        market_snapshot=snapshot,
        historical_window=history,
    )
    second = inferencer.compute_inference_features(
        market_id="BTCUSDT",
        timestamp=timestamp,
        market_snapshot={**snapshot, "mid": 999.0},
        historical_window=history,
    )
    assert first == second

    time.sleep(1.05)
    third = inferencer.compute_inference_features(
        market_id="BTCUSDT",
        timestamp=timestamp + timedelta(minutes=1),
        market_snapshot={**snapshot, "mid": 101.0},
        historical_window=history,
    )
    assert third["mid"] == 101.0


def test_active_model_selection_prediction_logging_and_signal_generation(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    registry_dir = tmp_path / "registry"
    _write_artifact(model_dir, "model_5m", value=0.02)

    manager = ModelManager(registry_dir)
    registered = manager.register_model(
        model_id="model_5m",
        artifact_path=model_dir / "model_5m.joblib",
        algorithm="weighted",
        hyperparameters={"lr": 0.1},
        feature_list=["mid", "spread_pct", "ret_1"],
        performance_metrics={"RMSE": 0.01},
    )
    manager.deploy_model("model_5m", registered.version, mode=DeploymentMode.PRODUCTION, traffic_allocation=1.0)

    inferencer = Inferencer(
        model_dir=model_dir,
        registry_dir=registry_dir,
        prediction_log_path=tmp_path / "pred.sqlite",
    )
    active = inferencer.get_active_models()
    assert active["model_5m"]["model_version"] == "1.0.0"

    predictions = inferencer.predict(
        {"mid": 100.0, "spread_pct": 0.001, "ret_1": 0.002},
        100.0,
        market_id="BTCUSDT",
    )
    assert predictions
    signal = inferencer.generate_signal(
        market_id="BTCUSDT",
        current_bid=99.8,
        current_ask=100.2,
        predictions=predictions,
        regime_adjustment=1.0,
    )
    assert signal.decision in {EdgeDecision.BUY, EdgeDecision.HOLD}
    assert inferencer.prediction_logger.recent(5)


def test_explainability_checkpoint_and_drift_detection(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    _write_artifact(model_dir)
    inferencer = Inferencer(model_dir=model_dir, prediction_log_path=tmp_path / "pred.sqlite")
    prediction = inferencer.predict({"mid": 100.0, "spread_pct": 0.001, "ret_1": 0.003}, 100.0)[0]

    engine = ExplainabilityEngine()
    explanation = engine.compute_shap_values(
        model=_ConstantModel(),
        feature_values={"mid": 100.0, "spread_pct": 0.001, "ret_1": 0.003},
    )
    assert len(explanation.top_features) <= 5
    assert explanation.narrative

    detector = DriftDetector()
    now = datetime.now(UTC)
    for index in range(10):
        detector.record(
            model_id="model_5m",
            prediction=0.01 if index < 5 else 0.20,
            actual=0.01 if index < 5 else -0.05,
            features={"mid": 100.0 + index, "ret_1": prediction.predicted_return + index * 0.01},
            timestamp=now - timedelta(days=10 - index),
        )
    report = detector.evaluate("model_5m", now=now)
    assert report.feature_drift >= 0.0
    assert report.psi_drift >= 0.0
    assert inferencer.inference_health()["inference_p95_ms"] >= 0.0


@pytest.mark.property_test
@hyp_settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(predicted_return=st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False))
def test_property_prediction_calibration(tmp_path: Path, predicted_return: float) -> None:
    model_dir = tmp_path / "models"
    _write_artifact(model_dir)
    inferencer = Inferencer(model_dir=model_dir, prediction_log_path=tmp_path / "pred.sqlite")

    confidence, interval, low_confidence = inferencer.calibrate_confidence("model_5m", predicted_return)

    assert 0.0 <= confidence <= 1.0
    assert interval[0] <= predicted_return <= interval[1]
    assert low_confidence is (confidence < 0.6)
