"""Property tests for feature importance tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.ml.feature_importance import FeatureImportance, FeatureImportanceTracker

FEATURE_VALUES = st.dictionaries(
    keys=st.sampled_from(["f1", "f2", "f3", "f4"]),
    values=st.lists(
        st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=30,
    ),
    min_size=1,
    max_size=4,
)


# Property 45: Feature Importance Calculation
@given(features=FEATURE_VALUES)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_feature_importance_calculation(features: dict[str, list[float]]) -> None:
    with TemporaryDirectory() as tmp_dir:
        tracker = FeatureImportanceTracker(str(Path(tmp_dir) / "fi.db"))
        try:
            target = [0.1] * 20
            result = tracker.calculate_importance("m1", "1.0.0", features, target, method="shap")
            assert result.feature_scores
            assert result.method == "heuristic_shap_proxy"
            total = sum(result.feature_scores.values())
            assert total == pytest.approx(1.0, rel=1e-6)
            assert all(value >= 0.0 for value in result.feature_scores.values())
        finally:
            tracker.close()


# Property 46: Feature Importance Snapshot Frequency
@given(days=st.integers(min_value=0, max_value=30))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_feature_importance_snapshot_frequency(days: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        tracker = FeatureImportanceTracker(str(Path(tmp_dir) / "fi.db"))
        try:
            now = datetime.now(UTC)
            last = now - timedelta(days=days)
            should = tracker.should_store_weekly(now, last)
            assert should is (days >= 7)
        finally:
            tracker.close()


# Property 47: Feature Importance Shift Flagging
@given(delta=st.floats(min_value=0.31, max_value=1.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_feature_importance_shift_flagging(delta: float) -> None:
    with TemporaryDirectory() as tmp_dir:
        tracker = FeatureImportanceTracker(str(Path(tmp_dir) / "fi.db"))
        try:
            prev = FeatureImportance(
                model_id="m2",
                version="1.0.0",
                timestamp=datetime.now(UTC) - timedelta(days=7),
                feature_scores={"f1": 0.1, "f2": 0.9},
                method="shap",
            )
            current = FeatureImportance(
                model_id="m2",
                version="1.0.1",
                timestamp=datetime.now(UTC),
                feature_scores={"f1": min(1.0, 0.1 + delta), "f2": max(0.0, 0.9 - delta)},
                method="shap",
            )
            shift = tracker.detect_importance_shift(prev, current, threshold=0.30)
            assert shift.changed_features
        finally:
            tracker.close()
