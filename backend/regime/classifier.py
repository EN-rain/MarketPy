"""Regime classifier for crypto market states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.regime.features import RegimeFeatureComputer


REGIMES = [
    "trending_up",
    "trending_down",
    "ranging",
    "high_volatility",
    "low_volatility",
    "crisis",
]


@dataclass(slots=True)
class RegimeClassification:
    regime: str
    confidence: float
    scores: dict[str, float]
    timestamp: datetime


class RegimeClassifier:
    """Rule-backed regime classifier with normalized confidence scores."""

    def __init__(self, feature_computer: RegimeFeatureComputer | None = None) -> None:
        self.feature_computer = feature_computer or RegimeFeatureComputer()
        self.history: list[RegimeClassification] = []

    def classify_regime(self, features: dict[str, float]) -> RegimeClassification:
        slope = float(features.get("linear_regression_slope", 0.0))
        trend = float(features.get("trend_strength", 0.0))
        volatility = float(features.get("volatility_percentile", 0.0))
        liquidity = float(features.get("liquidity_score", 0.0))

        scores = {
            "trending_up": max(0.0, slope) + trend / 100.0,
            "trending_down": max(0.0, -slope) + trend / 100.0,
            "ranging": max(0.0, 1.0 - abs(slope) * 10) + max(0.0, 0.5 - volatility),
            "high_volatility": volatility + max(0.0, trend / 200.0),
            "low_volatility": max(0.0, 1.0 - volatility),
            "crisis": max(0.0, volatility * 1.5 + (0.2 if liquidity < 50 else 0.0)),
        }
        total = sum(max(value, 0.0) for value in scores.values()) or 1.0
        normalized = {key: float(max(value, 0.0) / total) for key, value in scores.items()}
        regime = max(normalized, key=normalized.get)
        classification = RegimeClassification(
            regime=regime,
            confidence=normalized[regime],
            scores=normalized,
            timestamp=datetime.now(UTC),
        )
        self.history.append(classification)
        return classification

    def classify_from_frame(self, frame) -> RegimeClassification:
        return self.classify_regime(self.feature_computer.compute(frame))
