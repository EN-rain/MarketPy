"""Phase 11 regime classification tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.regime.classifier import REGIMES, RegimeClassifier
from backend.regime.events import RegimeEventSystem
from backend.regime.features import RegimeFeatureComputer
from backend.regime.parameters import RegimeParameterManager
from backend.regime.predictor import RegimePredictor


def _make_frame(rows: int = 120, slope: float = 0.2, volatility: float = 0.5) -> pd.DataFrame:
    base = [100.0 + slope * idx + ((-1) ** idx) * volatility for idx in range(rows)]
    ts = [datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=idx) for idx in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "close": base,
            "volume": [1000.0 + (idx % 10) * 10 for idx in range(rows)],
            "spread": [0.05 + (idx % 5) * 0.01 for idx in range(rows)],
            "order_book_depth": [5000.0 - (idx % 7) * 20 for idx in range(rows)],
        }
    )


def test_regime_features_classifier_predictor_and_checkpoint() -> None:
    frame = _make_frame(slope=0.3, volatility=0.2)
    features = RegimeFeatureComputer().compute(frame)
    assert "trend_strength" in features
    assert "liquidity_score" in features

    classifier = RegimeClassifier()
    first = classifier.classify_from_frame(frame)
    second = classifier.classify_from_frame(_make_frame(slope=-0.3, volatility=0.8))
    assert first.regime in REGIMES
    assert second.regime in REGIMES

    predictor = RegimePredictor()
    predictor.fit(classifier.history)
    probabilities = predictor.predict_regime_transition(first.regime)
    assert set(probabilities) == set(REGIMES)
    assert abs(sum(probabilities.values()) - 1.0) < 1e-6


def test_regime_parameters_and_event_system_checkpoint() -> None:
    manager = RegimeParameterManager()
    adjusted = manager.adjust(
        "high_volatility",
        profit_target=10.0,
        stop_loss=5.0,
        position_size=1000.0,
    )
    assert adjusted["position_size"] < 1000.0
    assert adjusted["profit_target"] < 10.0

    events = RegimeEventSystem()
    seen: list[str] = []
    events.subscribe(lambda event: seen.append(f"{event.previous_regime}->{event.current_regime}"))
    event = events.emit_transition("ranging", "high_volatility", 0.8)
    events.record_performance("high_volatility", -0.02)

    assert seen == ["ranging->high_volatility"]
    assert event.confidence == 0.8
    assert events.performance_by_regime["high_volatility"] == [-0.02]
    assert events.alert_log


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    slope=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    volatility=st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_property_regime_confidence_range(slope: float, volatility: float) -> None:
    frame = _make_frame(slope=slope, volatility=volatility)
    classification = RegimeClassifier().classify_from_frame(frame)
    assert 0.0 <= classification.confidence <= 1.0
    assert all(0.0 <= score <= 1.0 for score in classification.scores.values())


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    slope=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    volatility=st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_property_regime_classification_validity(slope: float, volatility: float) -> None:
    frame = _make_frame(slope=slope, volatility=volatility)
    classification = RegimeClassifier().classify_from_frame(frame)
    assert classification.regime in REGIMES
