"""Rolling-window drift detection for inference monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean, pstdev


@dataclass(slots=True)
class DriftReport:
    model_id: str
    window_start: datetime
    window_end: datetime
    performance_drift: float
    feature_drift: float
    psi_drift: float
    prediction_shift: float
    alert: bool


@dataclass(slots=True)
class DriftSample:
    timestamp: datetime
    prediction: float
    actual: float
    features: dict[str, float]


class DriftDetector:
    """Detects performance, feature, PSI, and prediction-distribution drift."""

    def __init__(self, rolling_window_days: int = 7) -> None:
        self.rolling_window_days = rolling_window_days
        self._samples: dict[str, list[DriftSample]] = {}

    def record(
        self,
        *,
        model_id: str,
        prediction: float,
        actual: float,
        features: dict[str, float],
        timestamp: datetime | None = None,
    ) -> None:
        ts = timestamp or datetime.now(UTC)
        self._samples.setdefault(model_id, []).append(
            DriftSample(timestamp=ts, prediction=prediction, actual=actual, features=dict(features))
        )

    def detect_performance_drift(self, baseline_error: float, recent_error: float) -> float:
        if baseline_error <= 1e-12:
            return 0.0
        return (recent_error - baseline_error) / baseline_error

    def detect_feature_drift(self, baseline: list[dict[str, float]], recent: list[dict[str, float]]) -> float:
        keys = set().union(*(row.keys() for row in baseline), *(row.keys() for row in recent))
        if not keys:
            return 0.0
        return max(
            self._ks_statistic(
                sorted(row.get(key, 0.0) for row in baseline),
                sorted(row.get(key, 0.0) for row in recent),
            )
            for key in keys
        )

    def detect_psi_drift(self, baseline: list[dict[str, float]], recent: list[dict[str, float]], bins: int = 10) -> float:
        keys = set().union(*(row.keys() for row in baseline), *(row.keys() for row in recent))
        psi_scores: list[float] = []
        for key in keys:
            base_values = [row.get(key, 0.0) for row in baseline]
            recent_values = [row.get(key, 0.0) for row in recent]
            if not base_values or not recent_values:
                continue
            min_value = min(base_values + recent_values)
            max_value = max(base_values + recent_values)
            if max_value == min_value:
                continue
            step = (max_value - min_value) / bins
            psi = 0.0
            for bucket in range(bins):
                lower = min_value + bucket * step
                upper = max_value if bucket == bins - 1 else lower + step
                base_pct = sum(lower <= value <= upper for value in base_values) / len(base_values)
                recent_pct = sum(lower <= value <= upper for value in recent_values) / len(recent_values)
                base_pct = max(base_pct, 1e-6)
                recent_pct = max(recent_pct, 1e-6)
                psi += (recent_pct - base_pct) * __import__("math").log(recent_pct / base_pct)
            psi_scores.append(float(psi))
        return max(psi_scores) if psi_scores else 0.0

    def detect_prediction_distribution_shift(self, baseline_predictions: list[float], recent_predictions: list[float]) -> float:
        if not baseline_predictions or not recent_predictions:
            return 0.0
        mean_shift = abs(mean(recent_predictions) - mean(baseline_predictions))
        variance_shift = abs(pstdev(recent_predictions) - pstdev(baseline_predictions))
        baseline_std = max(pstdev(baseline_predictions), 1e-6)
        return float(max(mean_shift, variance_shift) / baseline_std)

    def evaluate(self, model_id: str, now: datetime | None = None) -> DriftReport:
        end = now or datetime.now(UTC)
        start = end - timedelta(days=self.rolling_window_days)
        samples = sorted(self._samples.get(model_id, []), key=lambda item: item.timestamp)
        recent = [sample for sample in samples if sample.timestamp >= start]
        baseline = [sample for sample in samples if sample.timestamp < start]
        if not baseline and len(recent) >= 4:
            midpoint = len(recent) // 2
            baseline = recent[:midpoint]
            recent = recent[midpoint:]

        baseline_errors = [abs(item.prediction - item.actual) for item in baseline]
        recent_errors = [abs(item.prediction - item.actual) for item in recent]
        performance_drift = self.detect_performance_drift(
            mean(baseline_errors) if baseline_errors else 0.0,
            mean(recent_errors) if recent_errors else 0.0,
        )
        feature_drift = self.detect_feature_drift(
            [item.features for item in baseline],
            [item.features for item in recent],
        )
        psi_drift = self.detect_psi_drift(
            [item.features for item in baseline],
            [item.features for item in recent],
        )
        prediction_shift = self.detect_prediction_distribution_shift(
            [item.prediction for item in baseline],
            [item.prediction for item in recent],
        )
        alert = bool(performance_drift > 0.2 or feature_drift > 0.05 or psi_drift > 0.2 or prediction_shift > 2.0)
        return DriftReport(
            model_id=model_id,
            window_start=start,
            window_end=end,
            performance_drift=float(performance_drift),
            feature_drift=float(feature_drift),
            psi_drift=float(psi_drift),
            prediction_shift=float(prediction_shift),
            alert=alert,
        )

    @staticmethod
    def _ks_statistic(sample_a: list[float], sample_b: list[float]) -> float:
        if not sample_a or not sample_b:
            return 0.0
        points = sorted(set(sample_a + sample_b))
        max_diff = 0.0
        for point in points:
            cdf_a = sum(1 for value in sample_a if value <= point) / len(sample_a)
            cdf_b = sum(1 for value in sample_b if value <= point) / len(sample_b)
            max_diff = max(max_diff, abs(cdf_a - cdf_b))
        return float(max_diff)
