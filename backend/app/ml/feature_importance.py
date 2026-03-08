"""Feature importance tracking across model versions."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Literal

ImportanceMethod = Literal[
    "heuristic_shap_proxy",
    "heuristic_permutation_proxy",
    "heuristic_gain_proxy",
    "shap",
    "permutation",
    "gain",
]

_METHOD_ALIASES = {
    "shap": "heuristic_shap_proxy",
    "permutation": "heuristic_permutation_proxy",
    "gain": "heuristic_gain_proxy",
}
_CANONICAL_METHODS = frozenset(
    {"heuristic_shap_proxy", "heuristic_permutation_proxy", "heuristic_gain_proxy"}
)


@dataclass(frozen=True)
class FeatureImportance:
    model_id: str
    version: str
    timestamp: datetime
    feature_scores: dict[str, float]
    method: ImportanceMethod


@dataclass(frozen=True)
class FeatureShift:
    model_id: str
    version: str
    timestamp: datetime
    changed_features: dict[str, float]
    threshold: float


class FeatureImportanceTracker:
    """Calculates and stores feature importance snapshots."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_importance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                version TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                method TEXT NOT NULL,
                feature_scores TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feature_importance_model_version_ts
            ON feature_importance_snapshots (model_id, version, timestamp)
            """
        )
        self._conn.commit()

    def calculate_importance(
        self,
        model_id: str,
        version: str,
        features: dict[str, list[float]],
        target: list[float],
        method: ImportanceMethod = "heuristic_shap_proxy",
        timestamp: datetime | None = None,
    ) -> FeatureImportance:
        canonical_method = self._normalize_method(method)
        scores: dict[str, float] = {}
        target_mean = mean(target) if target else 0.0
        for name, values in features.items():
            if not values:
                scores[name] = 0.0
                continue
            feature_mean = mean(values)
            centered = sum(abs(value - feature_mean) for value in values) / len(values)
            target_distance = abs(feature_mean - target_mean)
            base = centered + target_distance
            if canonical_method == "heuristic_permutation_proxy":
                base *= 0.9
            elif canonical_method == "heuristic_gain_proxy":
                base *= 1.1
            scores[name] = max(0.0, base)

        total = sum(scores.values()) or 1.0
        normalized = {key: value / total for key, value in scores.items()}
        return FeatureImportance(
            model_id=model_id,
            version=version,
            timestamp=timestamp or datetime.now(UTC),
            feature_scores=normalized,
            method=canonical_method,
        )

    def should_store_weekly(self, now: datetime, last_snapshot: datetime | None) -> bool:
        if last_snapshot is None:
            return True
        return now - last_snapshot >= timedelta(days=7)

    def store_snapshot(self, importance: FeatureImportance) -> None:
        self._conn.execute(
            """
            INSERT INTO feature_importance_snapshots (
                model_id, version, timestamp, method, feature_scores
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                importance.model_id,
                importance.version,
                importance.timestamp.isoformat(),
                importance.method,
                json.dumps(importance.feature_scores),
            ),
        )
        self._conn.commit()

    def detect_importance_shift(
        self,
        previous: FeatureImportance,
        current: FeatureImportance,
        threshold: float = 0.30,
    ) -> FeatureShift:
        changed: dict[str, float] = {}
        keys = set(previous.feature_scores) | set(current.feature_scores)
        for key in keys:
            old = previous.feature_scores.get(key, 0.0)
            new = current.feature_scores.get(key, 0.0)
            delta = new - old
            if abs(delta) > threshold:
                changed[key] = delta
        return FeatureShift(
            model_id=current.model_id,
            version=current.version,
            timestamp=current.timestamp,
            changed_features=changed,
            threshold=threshold,
        )

    def count_rows(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM feature_importance_snapshots"
        ).fetchone()
        return int(row["cnt"]) if row else 0

    def _normalize_method(self, method: ImportanceMethod) -> ImportanceMethod:
        if method in _CANONICAL_METHODS:
            return method
        alias = _METHOD_ALIASES.get(method)
        if alias is None:
            raise ValueError(f"Unsupported feature importance method: {method}")
        return alias
