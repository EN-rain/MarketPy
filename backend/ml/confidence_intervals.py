"""Prediction confidence intervals via lightweight quantile proxies."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    lower: float
    upper: float
    median: float
    confidence: float


class QuantileIntervalEstimator:
    """Approximates quantile intervals for predicted returns."""

    def __init__(self, lower_q: float = 0.1, upper_q: float = 0.9) -> None:
        if not 0.0 < lower_q < upper_q < 1.0:
            raise ValueError("Quantiles must satisfy 0 < lower < upper < 1")
        self.lower_q = lower_q
        self.upper_q = upper_q

    def estimate(self, predicted_return: float, residuals: np.ndarray) -> ConfidenceInterval:
        residuals = np.asarray(residuals, dtype=float)
        if residuals.size == 0:
            width = max(abs(predicted_return) * 0.25, 0.001)
            return ConfidenceInterval(
                lower=float(predicted_return - width),
                upper=float(predicted_return + width),
                median=float(predicted_return),
                confidence=0.5,
            )
        lower_res = float(np.quantile(residuals, self.lower_q))
        upper_res = float(np.quantile(residuals, self.upper_q))
        lower = float(predicted_return + lower_res)
        upper = float(predicted_return + upper_res)
        spread = max(upper - lower, 1e-9)
        confidence = float(max(0.0, min(1.0, 1.0 - min(spread, 0.2) / 0.2)))
        return ConfidenceInterval(lower=lower, upper=upper, median=float(predicted_return), confidence=confidence)
