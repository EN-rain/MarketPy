"""Persistence-focused tests for drift detector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.ml.drift_detector import DriftDetector


def test_calculate_drift_uses_persisted_predictions_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "drift.db"
    now = datetime.now(UTC)

    detector = DriftDetector(str(db_path), baseline_window_days=30)
    for day in range(60, 30, -1):
        detector.track_prediction(
            model_id="m1",
            prediction=0.8,
            actual=0.8,
            features={"f1": 0.2},
            timestamp=now - timedelta(days=day),
        )
    for day in range(29, -1, -1):
        detector.track_prediction(
            model_id="m1",
            prediction=0.8,
            actual=0.2,
            features={"f1": 0.9},
            timestamp=now - timedelta(days=day),
        )
    detector.close()

    restarted = DriftDetector(str(db_path), baseline_window_days=30)
    try:
        metrics = restarted.calculate_drift("m1", now=now)
        assert restarted.count_rows("prediction_tracking") == 60
        assert metrics.accuracy_drift > 0.1
    finally:
        restarted.close()


def test_count_rows_rejects_unknown_tables(tmp_path: Path) -> None:
    detector = DriftDetector(str(tmp_path / "drift.db"))
    try:
        with pytest.raises(ValueError):
            detector.count_rows("sqlite_master")
    finally:
        detector.close()
