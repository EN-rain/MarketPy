"""Tests for feature importance method normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.ml.feature_importance import FeatureImportanceTracker


def test_legacy_method_aliases_are_normalized(tmp_path: Path) -> None:
    tracker = FeatureImportanceTracker(str(tmp_path / "fi.db"))
    try:
        result = tracker.calculate_importance(
            model_id="m1",
            version="1.0.0",
            features={"f1": [0.1, 0.2, 0.3], "f2": [0.2, 0.1, 0.3]},
            target=[0.1, 0.2, 0.3],
            method="shap",
        )
        assert result.method == "heuristic_shap_proxy"
    finally:
        tracker.close()


def test_unknown_feature_importance_method_raises(tmp_path: Path) -> None:
    tracker = FeatureImportanceTracker(str(tmp_path / "fi.db"))
    try:
        with pytest.raises(ValueError):
            tracker.calculate_importance(
                model_id="m1",
                version="1.0.0",
                features={"f1": [0.1, 0.2, 0.3]},
                target=[0.1, 0.2, 0.3],
                method="unknown",  # type: ignore[arg-type]
            )
    finally:
        tracker.close()
