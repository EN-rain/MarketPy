"""Model feature-importance computation and persistence helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.inspection import permutation_importance

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FeatureImportanceResult:
    model_id: str
    computed_at: datetime
    method: str
    scores: dict[str, float]

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.scores.items(), key=lambda item: item[1], reverse=True)


class FeatureImportanceTracker:
    """Computes, ranks, and persists feature importance scores."""

    def __init__(self, output_dir: str = "models/feature_importance") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize(scores: dict[str, float]) -> dict[str, float]:
        total = float(sum(max(v, 0.0) for v in scores.values()))
        if total <= 0:
            return {key: 0.0 for key in scores}
        return {key: float(max(value, 0.0) / total) for key, value in scores.items()}

    def from_tree_model(
        self,
        model_id: str,
        feature_names: list[str],
        model: Any,
    ) -> FeatureImportanceResult:
        raw = getattr(model, "feature_importances_", None)
        if raw is None:
            raise ValueError("Tree-based model does not expose feature_importances_")
        scores = {name: float(raw[idx]) for idx, name in enumerate(feature_names)}
        return FeatureImportanceResult(
            model_id=model_id,
            computed_at=datetime.now(UTC),
            method="tree",
            scores=self._normalize(scores),
        )

    def from_permutation(
        self,
        model_id: str,
        feature_names: list[str],
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        n_repeats: int = 5,
        random_state: int = 42,
    ) -> FeatureImportanceResult:
        result = permutation_importance(
            model,
            X,
            y,
            n_repeats=n_repeats,
            random_state=random_state,
        )
        scores = {name: float(result.importances_mean[idx]) for idx, name in enumerate(feature_names)}
        return FeatureImportanceResult(
            model_id=model_id,
            computed_at=datetime.now(UTC),
            method="permutation",
            scores=self._normalize(scores),
        )

    def from_shap(
        self,
        model_id: str,
        feature_names: list[str],
        model: Any,
        X: np.ndarray,
    ) -> FeatureImportanceResult:
        try:  # pragma: no cover - optional dependency path
            import shap  # type: ignore

            explainer = shap.Explainer(model)
            values = explainer(X[: min(500, len(X))])
            mean_abs = np.abs(values.values).mean(axis=0)
            scores = {name: float(mean_abs[idx]) for idx, name in enumerate(feature_names)}
        except Exception as exc:
            logger.warning("SHAP unavailable or failed, using zeroed fallback scores: %s", exc)
            scores = {name: 0.0 for name in feature_names}

        return FeatureImportanceResult(
            model_id=model_id,
            computed_at=datetime.now(UTC),
            method="shap",
            scores=self._normalize(scores),
        )

    def save(self, result: FeatureImportanceResult) -> Path:
        path = self.output_dir / f"{result.model_id}.json"
        payload = {
            "model_id": result.model_id,
            "computed_at": result.computed_at.isoformat(),
            "method": result.method,
            "scores": result.scores,
            "ranked": [{"feature": key, "score": value} for key, value in result.ranked()],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        top = result.ranked()[:10]
        logger.info("Top feature importance (%s): %s", result.model_id, top)
        return path

    def load(self, model_id: str) -> dict[str, Any] | None:
        path = self.output_dir / f"{model_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
