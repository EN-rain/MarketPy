"""Regime transition predictor."""

from __future__ import annotations

from collections import Counter, defaultdict

from backend.regime.classifier import REGIMES, RegimeClassification


class RegimePredictor:
    """Predicts next-regime probabilities from historical transitions."""

    def __init__(self) -> None:
        self._transitions: dict[str, Counter[str]] = defaultdict(Counter)

    def fit(self, history: list[RegimeClassification]) -> None:
        for previous, current in zip(history, history[1:], strict=False):
            self._transitions[previous.regime][current.regime] += 1

    def predict_regime_transition(self, current_regime: str) -> dict[str, float]:
        counts = self._transitions.get(current_regime)
        if not counts:
            return {regime: 1.0 / len(REGIMES) for regime in REGIMES}
        total = sum(counts.values()) or 1
        probabilities = {regime: float(counts.get(regime, 0) / total) for regime in REGIMES}
        missing_mass = max(0.0, 1.0 - sum(probabilities.values()))
        if missing_mass > 0:
            probabilities[current_regime] = probabilities.get(current_regime, 0.0) + missing_mass
        return probabilities
