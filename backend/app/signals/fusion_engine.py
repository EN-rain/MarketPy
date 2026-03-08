"""Sentiment + on-chain fusion signal engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean, pstdev


@dataclass(frozen=True)
class FusionSignal:
    signal: float
    confidence: float
    components: dict[str, float]
    timestamp: datetime


class FusionSignalEngine:
    """Generates normalized fusion signals from heterogeneous features."""

    def __init__(self) -> None:
        self.weights = {
            "sentiment": 0.45,
            "mempool": 0.25,
            "fees": 0.15,
            "hash_rate": 0.15,
        }

    def normalize_features(self, features: dict[str, list[float]]) -> dict[str, list[float]]:
        normalized: dict[str, list[float]] = {}
        for key, values in features.items():
            if not values:
                normalized[key] = []
                continue
            mu = mean(values)
            sigma = pstdev(values) or 1.0
            normalized[key] = [(value - mu) / sigma for value in values]
        return normalized

    def train(self, features: dict[str, list[float]], target: list[float]) -> None:
        # Lightweight training: adjust weights by absolute correlation proxy.
        if not target:
            return
        t_mean = mean(target)
        for key, values in features.items():
            if not values:
                continue
            v_mean = mean(values)
            score = abs(v_mean - t_mean)
            self.weights[key] = max(0.01, min(0.8, score))
        total = sum(self.weights.values()) or 1.0
        self.weights = {k: v / total for k, v in self.weights.items()}

    def generate_signal(self, features: dict[str, float]) -> FusionSignal:
        weighted = 0.0
        for key, value in features.items():
            weighted += self.weights.get(key, 0.0) * value
        signal = max(-1.0, min(1.0, weighted))
        confidence = min(1.0, sum(abs(self.weights.get(k, 0.0) * v) for k, v in features.items()))
        return FusionSignal(
            signal=signal,
            confidence=max(0.0, confidence),
            components={k: self.weights.get(k, 0.0) * v for k, v in features.items()},
            timestamp=datetime.now(UTC),
        )

    def backtest_signals(self, signals: list[float], returns: list[float]) -> dict[str, float]:
        n = min(len(signals), len(returns))
        if n == 0:
            return {"total_return": 0.0, "hit_rate": 0.0}
        pnl = 0.0
        hits = 0
        for s, r in zip(signals[:n], returns[:n], strict=False):
            pnl += s * r
            if (s >= 0 and r >= 0) or (s < 0 and r < 0):
                hits += 1
        return {"total_return": pnl, "hit_rate": hits / n}
