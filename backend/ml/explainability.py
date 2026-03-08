"""Prediction explainability helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(slots=True)
class ExplanationResult:
    shap_values: dict[str, float]
    top_features: list[tuple[str, float]]
    narrative: str
    is_anomalous: bool


class ExplainabilityEngine:
    """Computes lightweight SHAP-like attributions for tree and linear models."""

    def compute_shap_values(
        self,
        *,
        model: Any,
        feature_values: dict[str, float],
        top_k: int = 5,
    ) -> ExplanationResult:
        names = list(feature_values)
        values = np.asarray([float(feature_values[name]) for name in names], dtype=float)

        importances = getattr(model, "feature_importances_", None)
        if importances is not None and len(importances) == len(names):
            weights = np.asarray(importances, dtype=float)
        else:
            coefficients = getattr(model, "coef_", None)
            if coefficients is not None:
                weights = np.asarray(coefficients, dtype=float).reshape(-1)[: len(names)]
            else:
                weights = np.ones(len(names), dtype=float)

        scores = values * weights
        shap_values = {name: float(score) for name, score in zip(names, scores, strict=False)}
        ranked = sorted(shap_values.items(), key=lambda item: abs(item[1]), reverse=True)[:top_k]
        anomaly_threshold = float(np.mean(np.abs(scores)) + 2.0 * np.std(np.abs(scores)))
        is_anomalous = bool(np.any(np.abs(scores) > anomaly_threshold)) if len(scores) else False

        direction = "bullish" if sum(score for _, score in ranked) >= 0 else "bearish"
        feature_text = ", ".join(f"{name}={score:.3f}" for name, score in ranked)
        narrative = f"{direction} drivers: {feature_text}" if ranked else "no significant drivers"

        return ExplanationResult(
            shap_values=shap_values,
            top_features=ranked,
            narrative=narrative,
            is_anomalous=is_anomalous,
        )
