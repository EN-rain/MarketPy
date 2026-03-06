"""Property tests for model drift detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.ml.drift_detector import DriftDetector


# Property 42: Prediction Accuracy Tracking
@given(count=st.integers(min_value=10, max_value=80))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_prediction_accuracy_tracking(count: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        detector = DriftDetector(str(Path(tmp_dir) / "drift.db"), baseline_window_days=30)
        try:
            now = datetime.now(UTC)
            for i in range(count):
                pred = 0.9 if i % 2 == 0 else 0.1
                actual = pred
                detector.track_prediction(
                    model_id="m1",
                    prediction=pred,
                    actual=actual,
                    features={"f1": i / max(1, count)},
                    timestamp=now - timedelta(days=60 - i),
                )
            metrics = detector.calculate_drift("m1", now=now)
            assert detector.count_rows("prediction_tracking") == count
            assert detector.count_rows("drift_metrics") >= 1
            assert metrics.accuracy_drift >= -1.0
        finally:
            detector.close()


# Property 43: Drift Metric Calculation
@given(seed=st.integers(min_value=0, max_value=1000))
@settings(max_examples=30, deadline=7000)
@pytest.mark.property_test
def test_property_drift_metric_calculation(seed: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        detector = DriftDetector(str(Path(tmp_dir) / f"drift_{seed}.db"), baseline_window_days=30)
        try:
            now = datetime.now(UTC)
            for i in range(30):
                detector.track_prediction(
                    "m2",
                    prediction=0.9,
                    actual=0.9,
                    features={"f1": 0.1},
                    timestamp=now - timedelta(days=60 - i),
                )
            for i in range(30):
                detector.track_prediction(
                    "m2",
                    prediction=0.9,
                    actual=0.1,
                    features={"f1": 0.9},
                    timestamp=now - timedelta(days=29 - i),
                )
            metrics = detector.calculate_drift("m2", now=now)
            assert metrics.accuracy_drift > 0.10
            assert detector.detect_drift_alert(metrics) is True
        finally:
            detector.close()


# Property 44: Feature Distribution Monitoring
@given(scale=st.floats(min_value=0.2, max_value=3.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_feature_distribution_monitoring(scale: float) -> None:
    with TemporaryDirectory() as tmp_dir:
        detector = DriftDetector(str(Path(tmp_dir) / "drift.db"), baseline_window_days=30)
        try:
            now = datetime.now(UTC)
            for i in range(25):
                detector.track_prediction(
                    "m3",
                    prediction=0.6,
                    actual=0.6,
                    features={"f1": i / 25},
                    timestamp=now - timedelta(days=60 - i),
                )
            for i in range(25):
                detector.track_prediction(
                    "m3",
                    prediction=0.6,
                    actual=0.6,
                    features={"f1": min(1.0, (i / 25) * scale)},
                    timestamp=now - timedelta(days=29 - i),
                )
            metrics = detector.calculate_drift("m3", now=now)
            assert 0.0 <= metrics.feature_drift <= 1.0
        finally:
            detector.close()
