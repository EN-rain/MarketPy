"""Model drift detection and metric persistence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean


@dataclass(frozen=True)
class DriftMetrics:
    model_id: str
    timestamp: datetime
    accuracy_drift: float
    feature_drift: float
    prediction_drift: float


@dataclass(frozen=True)
class PredictionRecord:
    timestamp: datetime
    prediction: float
    actual: float
    features: dict[str, float]


class DriftDetector:
    """Tracks predictions and detects accuracy/feature/prediction drift."""

    _COUNT_QUERIES = {
        "drift_metrics": "SELECT COUNT(*) AS cnt FROM drift_metrics",
        "prediction_tracking": "SELECT COUNT(*) AS cnt FROM prediction_tracking",
    }

    def __init__(self, db_path: str, baseline_window_days: int = 30):
        self.db_path = db_path
        self.baseline_window_days = baseline_window_days
        self._records: dict[str, list[PredictionRecord]] = {}
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
            CREATE TABLE IF NOT EXISTS drift_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                accuracy_drift REAL NOT NULL,
                feature_drift REAL NOT NULL,
                prediction_drift REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_drift_metrics_model_ts
            ON drift_metrics (model_id, timestamp)
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                prediction REAL NOT NULL,
                actual REAL NOT NULL,
                features TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_prediction_tracking_model_ts
            ON prediction_tracking (model_id, timestamp)
            """
        )
        self._conn.commit()

    def track_prediction(
        self,
        model_id: str,
        prediction: float,
        actual: float,
        features: dict[str, float],
        timestamp: datetime | None = None,
    ) -> None:
        ts = timestamp or datetime.now(UTC)
        record = PredictionRecord(
            timestamp=ts, prediction=prediction, actual=actual, features=features
        )
        self._records.setdefault(model_id, []).append(record)
        self._conn.execute(
            """
            INSERT INTO prediction_tracking (model_id, timestamp, prediction, actual, features)
            VALUES (?, ?, ?, ?, ?)
            """,
            (model_id, ts.isoformat(), prediction, actual, json.dumps(features)),
        )
        self._conn.commit()

    def calculate_drift(self, model_id: str, now: datetime | None = None) -> DriftMetrics:
        current_time = now or datetime.now(UTC)
        records = self._load_records(model_id)
        if len(records) < 4:
            metrics = DriftMetrics(
                model_id=model_id,
                timestamp=current_time,
                accuracy_drift=0.0,
                feature_drift=0.0,
                prediction_drift=0.0,
            )
            self._persist_drift(metrics)
            return metrics

        split = current_time - timedelta(days=self.baseline_window_days)
        baseline = [item for item in records if item.timestamp <= split]
        recent = [item for item in records if item.timestamp > split]
        if not baseline or not recent:
            midpoint = len(records) // 2
            baseline = records[:midpoint]
            recent = records[midpoint:]

        baseline_acc = self._accuracy(baseline)
        recent_acc = self._accuracy(recent)
        accuracy_drift = baseline_acc - recent_acc

        feature_drift = self._feature_drift(baseline, recent)
        baseline_mean = mean(item.prediction for item in baseline)
        recent_mean = mean(item.prediction for item in recent)
        prediction_drift = abs(baseline_mean - recent_mean)

        metrics = DriftMetrics(
            model_id=model_id,
            timestamp=current_time,
            accuracy_drift=accuracy_drift,
            feature_drift=feature_drift,
            prediction_drift=prediction_drift,
        )
        self._persist_drift(metrics)
        return metrics

    def detect_drift_alert(self, metrics: DriftMetrics, threshold: float = 0.10) -> bool:
        return metrics.accuracy_drift > threshold

    def count_rows(self, table_name: str) -> int:
        query = self._COUNT_QUERIES.get(table_name)
        if query is None:
            raise ValueError(f"Unsupported table for count_rows: {table_name}")
        row = self._conn.execute(query).fetchone()
        return int(row["cnt"]) if row else 0

    def _load_records(self, model_id: str) -> list[PredictionRecord]:
        rows = self._conn.execute(
            """
            SELECT timestamp, prediction, actual, features
            FROM prediction_tracking
            WHERE model_id = ?
            ORDER BY timestamp ASC
            """,
            (model_id,),
        ).fetchall()
        records: list[PredictionRecord] = []
        for row in rows:
            timestamp = datetime.fromisoformat(row["timestamp"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            features = json.loads(row["features"])
            if not isinstance(features, dict):
                continue
            records.append(
                PredictionRecord(
                    timestamp=timestamp,
                    prediction=float(row["prediction"]),
                    actual=float(row["actual"]),
                    features={str(k): float(v) for k, v in features.items()},
                )
            )
        self._records[model_id] = records
        return records

    def _persist_drift(self, metrics: DriftMetrics) -> None:
        self._conn.execute(
            """
            INSERT INTO drift_metrics (
                model_id, timestamp, accuracy_drift, feature_drift, prediction_drift
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                metrics.model_id,
                metrics.timestamp.isoformat(),
                metrics.accuracy_drift,
                metrics.feature_drift,
                metrics.prediction_drift,
            ),
        )
        self._conn.commit()

    def _accuracy(self, records: list[PredictionRecord]) -> float:
        if not records:
            return 0.0
        correct = 0
        for item in records:
            pred_label = 1 if item.prediction >= 0.5 else 0
            actual_label = 1 if item.actual >= 0.5 else 0
            if pred_label == actual_label:
                correct += 1
        return correct / len(records)

    def _feature_drift(
        self, baseline: list[PredictionRecord], recent: list[PredictionRecord]
    ) -> float:
        keys = set()
        for item in baseline:
            keys.update(item.features.keys())
        for item in recent:
            keys.update(item.features.keys())
        if not keys:
            return 0.0

        stats: list[float] = []
        for key in keys:
            baseline_values = sorted(item.features.get(key, 0.0) for item in baseline)
            recent_values = sorted(item.features.get(key, 0.0) for item in recent)
            stats.append(self._ks_statistic(baseline_values, recent_values))
        return max(stats) if stats else 0.0

    def _ks_statistic(self, sample_a: list[float], sample_b: list[float]) -> float:
        if not sample_a or not sample_b:
            return 0.0
        points = sorted(set(sample_a + sample_b))
        max_diff = 0.0
        for point in points:
            cdf_a = sum(1 for value in sample_a if value <= point) / len(sample_a)
            cdf_b = sum(1 for value in sample_b if value <= point) / len(sample_b)
            max_diff = max(max_diff, abs(cdf_a - cdf_b))
        return max_diff
