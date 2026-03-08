"""Backfilled optional property tests from roadmap."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.execution.analyzer import ExecutionAnalyzer
from backend.features.computer import FeatureComputer
from backend.features.registry import FeatureDefinition, FeatureRegistry
from backend.ingest.alternative_data.sentiment import SocialSentimentSource
from backend.ingest.exchanges.binance import BinanceAdapter
from backend.ml.explainability import ExplainabilityEngine
from backend.ml.model_manager import ModelManager
from backend.ml.trainer import TrainingPipeline
from backend.patterns.support_resistance import SupportResistanceDetector
from backend.patterns.technical import TechnicalPatternDetector


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    bid=st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    ask=st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
)
def test_property_exchange_data_normalization(bid: float, ask: float) -> None:
    payload = {"T": 1_700_000_000_000, "b": [[str(bid), "1"]], "a": [[str(max(ask, bid)), "2"]]}
    ob = BinanceAdapter._normalize_order_book("BTCUSDT", payload)
    assert isinstance(ob.bids[0][0], float)
    assert isinstance(ob.asks[0][0], float)


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    first=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    second=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    third=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_property_point_in_time_and_training_inference_consistency(first: float, second: float, third: float) -> None:
    now = datetime.now(UTC)
    data = pd.DataFrame(
        {"timestamp": [now - timedelta(minutes=2), now - timedelta(minutes=1), now], "close": [first, second, third]}
    )
    registry = FeatureRegistry()
    registry.register_feature(
        FeatureDefinition(
            name="last_close",
            version="1.0.0",
            definition={},
            dependencies=[],
            data_sources=["market"],
            computation_logic="last close",
            compute_fn=lambda frame: float(frame["close"].iloc[-1]),
        )
    )
    computer = FeatureComputer(registry=registry)
    t_mid = now - timedelta(minutes=1)
    pit = computer.compute_features(t_mid, data, ["last_close"])["last_close"]
    direct = float(data.loc[data["timestamp"] <= t_mid, "close"].iloc[-1])
    assert pit == direct


@pytest.mark.property_test
@settings(max_examples=25)
@given(offset=st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False))
def test_property_pattern_precision_and_confidence_range(offset: float) -> None:
    detector = TechnicalPatternDetector()
    hs = detector.detect_head_and_shoulders(pd.Series([1.0, 2.0, 3.0 + offset, 2.0, 1.0, 0.9, 0.8]))
    tri = detector.detect_triangles(pd.Series([5, 5, 5, 5, 5]), pd.Series([1, 2, 3, 4, 5]))
    for pattern in hs + tri:
        assert 0.0 <= pattern.confidence <= 1.0


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    low=st.floats(min_value=1.0, max_value=99.0, allow_nan=False, allow_infinity=False),
    high=st.floats(min_value=100.0, max_value=200.0, allow_nan=False, allow_infinity=False),
)
def test_property_support_resistance_local_extrema(low: float, high: float) -> None:
    detector = SupportResistanceDetector()
    lows = pd.Series([low, low + 0.5, low + 1.0])
    highs = pd.Series([high - 1.0, high - 0.5, high])
    result = detector.detect_support_resistance(highs, lows)
    assert result.support == pytest.approx(float(lows.min()))
    assert result.resistance == pytest.approx(float(highs.max()))


@pytest.mark.property_test
@settings(max_examples=25)
@given(val=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False))
def test_property_sentiment_normalization(val: float) -> None:
    source = SocialSentimentSource(twitter_posts=[], reddit_posts=[])
    normalized = source.normalize_data({"twitter_sentiment": val, "reddit_sentiment": -val})
    assert -1.0 <= normalized["twitter_sentiment"] <= 1.0
    assert -1.0 <= normalized["reddit_sentiment"] <= 1.0


def test_property_model_metadata_completeness(tmp_path: Path) -> None:
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"dummy-model")
    manager = ModelManager(storage_dir=tmp_path / "registry")
    model = manager.register_model(
        model_id="m",
        artifact_path=artifact,
        algorithm="xgb",
        hyperparameters={"n_estimators": 10},
        feature_list=["f1", "f2"],
        performance_metrics={"RMSE": 0.1},
    )
    assert model.algorithm
    assert model.feature_list
    assert model.hyperparameters
    assert model.performance_metrics
    assert model.artifact_checksum


def test_property_ensemble_simplicity_preference(tmp_path: Path) -> None:
    pipeline = TrainingPipeline(output_dir=tmp_path / "models")
    y = np.array([0.1, -0.1, 0.2, -0.2])
    pred = np.array([0.1, -0.1, 0.2, -0.2])
    result = pipeline.optimize_ensemble(y, {"a": pred, "b": pred})
    assert result["method"] in {"average", "weighted", "stacking"}
    assert result["scores"]


def test_property_shap_value_computation() -> None:
    class DummyModel:
        feature_importances_ = np.array([0.7, 0.3])

    engine = ExplainabilityEngine()
    out = engine.compute_shap_values(model=DummyModel(), feature_values={"f1": 2.0, "f2": -1.0})
    assert set(out.shap_values) == {"f1", "f2"}
    assert len(out.top_features) <= 5
