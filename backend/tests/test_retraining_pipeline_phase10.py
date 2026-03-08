"""Phase 10 drift and retraining tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import joblib
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.ml.drift_detection import DriftDetector
from backend.ml.model_manager import DeploymentMode, ModelManager
from backend.ml.retraining import RetrainingPipeline
from backend.ml.trainer import TrainingPipeline


class _ConstantModel:
    def predict(self, X):  # noqa: N803
        return [0.01 for _ in range(len(X))]


def _make_training_frame(rows: int = 2200) -> pd.DataFrame:
    ts = pd.date_range("2025-01-01", periods=rows, freq="5min", tz="UTC")
    close = pd.Series(range(rows), dtype=float) * 0.01 + 100.0
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "mid": close,
            "spread": 0.1,
            "volume": [1000.0 + (idx % 25) * 5.0 for idx in range(rows)],
        }
    )


@pytest.mark.property_test
@settings(max_examples=20)
@given(scale=st.floats(min_value=1.3, max_value=3.0, allow_nan=False, allow_infinity=False))
def test_property_drift_alert_triggering(scale: float) -> None:
    detector = DriftDetector()
    now = datetime.now(UTC)
    for index in range(14):
        detector.record(
            model_id="m1",
            prediction=0.01 if index < 7 else 0.1 * scale,
            actual=0.01 if index < 7 else -0.02,
            features={"f1": 0.1 if index < 7 else scale, "f2": index / 10},
            timestamp=now - timedelta(days=14 - index),
        )
    report = detector.evaluate("m1", now=now)
    assert report.alert is True


@pytest.mark.property_test
@settings(max_examples=20)
@given(scale=st.floats(min_value=1.5, max_value=5.0, allow_nan=False, allow_infinity=False))
def test_property_psi_drift_detection(scale: float) -> None:
    detector = DriftDetector()
    baseline = [{"f1": 0.1 + i * 0.01} for i in range(20)]
    shifted = [{"f1": (0.1 + i * 0.01) * scale} for i in range(20)]
    psi = detector.detect_psi_drift(baseline, shifted)
    assert psi >= 0.0
    assert psi > 0.2


def test_retraining_trigger_validation_and_checkpoint(tmp_path: Path) -> None:
    output_dir = tmp_path / "models"
    registry_dir = tmp_path / "registry"
    training_pipeline = TrainingPipeline(output_dir=output_dir, registry_dir=registry_dir)
    retraining = RetrainingPipeline(training_pipeline=training_pipeline)
    now = datetime.now(UTC)

    scheduled = retraining.trigger_retraining(
        reason="scheduled",
        now=now,
        last_trained_at=now - timedelta(days=31),
    )
    volatility = retraining.trigger_retraining(
        reason="volatility",
        now=now,
        volatility_now=0.30,
        baseline_volatility=0.10,
    )
    performance = retraining.trigger_retraining(
        reason="performance",
        now=now,
        recent_accuracy=[0.50, 0.51, 0.49],
    )
    assert scheduled.should_retrain is True
    assert volatility.should_retrain is True
    assert performance.should_retrain is True

    frame = _make_training_frame()
    report = retraining.run_retraining(
        market_data=frame,
        target_columns=["y_5m"],
        algorithms=training_pipeline.available_algorithms()[:1],
    )
    assert "model_5m" in report["registrations"]

    manager = ModelManager(registry_dir)
    retraining.model_manager = manager
    artifact = output_dir / "model_5m.joblib"
    challenger = manager.register_model(
        model_id="model_5m",
        artifact_path=artifact,
        algorithm="weighted",
        hyperparameters={"lr": 0.1},
        feature_list=["mid"],
        performance_metrics={"sharpe_ratio": 0.5},
    )
    manager.deploy_model("model_5m", challenger.version, mode=DeploymentMode.PRODUCTION, traffic_allocation=1.0)
    newer = manager.register_model(
        model_id="model_5m",
        artifact_path=artifact,
        algorithm="weighted",
        hyperparameters={"lr": 0.2},
        feature_list=["mid"],
        performance_metrics={"sharpe_ratio": 0.7},
    )
    decision = retraining.validate_retrained_model(
        model_id="model_5m",
        production_metrics={"sharpe_ratio": 0.5},
        challenger_metrics={"sharpe_ratio": 0.8},
    )
    assert decision.shadow_deployed is True
    assert decision.promoted is True
    assert decision.challenger_version == newer.version
