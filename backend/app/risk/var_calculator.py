"""VaR calculator supporting historical, parametric, and Monte Carlo methods."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from statistics import NormalDist


class VaRMethod(StrEnum):
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


@dataclass(frozen=True)
class VaRResult:
    confidence_level: float
    var_dollar: float
    var_percent: float
    method: VaRMethod
    timestamp: datetime


class VaRCalculator:
    """Risk cockpit VaR calculations for 95%/99% confidence levels."""

    def __init__(self, update_interval_seconds: int = 300):
        self.update_interval_seconds = update_interval_seconds

    def calculate_var(
        self,
        portfolio_value: float,
        returns: list[float],
        confidence_level: float = 0.95,
        method: VaRMethod = VaRMethod.HISTORICAL,
        simulations: int = 2000,
        seed: int = 42,
    ) -> VaRResult:
        if confidence_level not in (0.95, 0.99):
            raise ValueError("confidence_level must be 0.95 or 0.99")
        if portfolio_value < 0:
            raise ValueError("portfolio_value must be non-negative")
        if not returns:
            raise ValueError("returns must not be empty")

        if method == VaRMethod.HISTORICAL:
            var_percent = self._historical_var(returns, confidence_level)
        elif method == VaRMethod.PARAMETRIC:
            var_percent = self._parametric_var(returns, confidence_level)
        elif method == VaRMethod.MONTE_CARLO:
            var_percent = self._monte_carlo_var(returns, confidence_level, simulations, seed)
        else:
            raise ValueError(f"unsupported method: {method}")

        bounded = max(0.0, min(var_percent, 1.0))
        return VaRResult(
            confidence_level=confidence_level,
            var_dollar=portfolio_value * bounded,
            var_percent=bounded,
            method=method,
            timestamp=datetime.now(UTC),
        )

    def should_recalculate(self, now: datetime, last_update: datetime | None) -> bool:
        if last_update is None:
            return True
        elapsed = (now - last_update).total_seconds()
        return elapsed >= self.update_interval_seconds

    @staticmethod
    def check_var_threshold(var_result: VaRResult, threshold_percent: float) -> bool:
        return var_result.var_percent >= max(0.0, threshold_percent)

    def _historical_var(self, returns: list[float], confidence: float) -> float:
        losses = sorted(max(0.0, -value) for value in returns)
        index = min(len(losses) - 1, max(0, int(math.ceil(confidence * len(losses)) - 1)))
        return float(losses[index])

    def _parametric_var(self, returns: list[float], confidence: float) -> float:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / max(1, len(returns) - 1)
        sigma = math.sqrt(variance)
        z_score = NormalDist().inv_cdf(confidence)
        return max(0.0, (z_score * sigma) - mean)

    def _monte_carlo_var(
        self, returns: list[float], confidence: float, simulations: int, seed: int
    ) -> float:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / max(1, len(returns) - 1)
        sigma = math.sqrt(max(0.0, variance))
        rng = random.Random(seed)
        losses = sorted(max(0.0, -(rng.gauss(mean, sigma))) for _ in range(max(100, simulations)))
        index = min(len(losses) - 1, max(0, int(math.ceil(confidence * len(losses)) - 1)))
        return float(losses[index])
