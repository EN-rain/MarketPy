"""Data quality monitoring primitives for market ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from backend.monitoring.influx import InfluxMetricWriter


@dataclass(frozen=True, slots=True)
class DataQualityMetrics:
    completeness: float
    staleness_seconds: float
    outlier_rate: float
    missing_rate: float
    quarantined_rows: int
    valid_ohlcv_ratio: float
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class DataQualityAlert:
    metric: str
    threshold: float
    observed: float
    message: str


@dataclass(slots=True)
class DataMonitor:
    writer: InfluxMetricWriter | None = None
    completeness_threshold: float = 0.95
    staleness_threshold_seconds: float = 60.0
    outlier_rate_threshold: float = 0.05
    quarantine_frames: list[pd.DataFrame] = field(default_factory=list)

    def detect_missing_timestamps(
        self,
        frame: pd.DataFrame,
        *,
        timestamp_col: str = "timestamp",
        expected_frequency: pd.Timedelta | None = None,
    ) -> list[pd.Timestamp]:
        if frame.empty or timestamp_col not in frame.columns or len(frame) < 2:
            return []
        ordered = pd.to_datetime(frame[timestamp_col], utc=True).sort_values().reset_index(drop=True)
        deltas = ordered.diff().dropna()
        frequency = expected_frequency or (deltas.median() if not deltas.empty else None)
        if frequency is None or frequency <= pd.Timedelta(0):
            return []
        gap_threshold = frequency * 1.5
        missing: list[pd.Timestamp] = []
        for previous, current in zip(ordered[:-1], ordered[1:], strict=False):
            gap = current - previous
            if gap > gap_threshold:
                cursor = previous + frequency
                while cursor < current:
                    missing.append(pd.Timestamp(cursor))
                    cursor += frequency
        return missing

    def detect_outliers(
        self,
        frame: pd.DataFrame,
        *,
        columns: tuple[str, ...] = ("open", "high", "low", "close", "volume"),
        z_threshold: float = 5.0,
    ) -> dict[str, list[int]]:
        outliers: dict[str, list[int]] = {}
        if frame.empty:
            return outliers
        for column in columns:
            if column not in frame.columns:
                continue
            series = pd.to_numeric(frame[column], errors="coerce")
            std = float(series.std(ddof=0))
            if std <= 0 or pd.isna(std):
                continue
            z_scores = (series - float(series.mean())) / std
            flagged = z_scores.abs() > z_threshold
            if bool(flagged.any()):
                outliers[column] = [int(idx) for idx in frame.index[flagged]]
        return outliers

    def validate_ohlcv_integrity(self, frame: pd.DataFrame) -> pd.Series:
        if frame.empty:
            return pd.Series(dtype=bool)
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(frame.columns):
            return pd.Series(False, index=frame.index)
        high_ok = (frame["high"] >= frame["open"]) & (frame["high"] >= frame["close"]) & (frame["high"] >= frame["low"])
        low_ok = (frame["low"] <= frame["open"]) & (frame["low"] <= frame["close"]) & (frame["low"] <= frame["high"])
        volume_ok = pd.to_numeric(frame["volume"], errors="coerce") >= 0
        return (high_ok & low_ok & volume_ok).fillna(False)

    def detect_staleness(
        self,
        frame: pd.DataFrame,
        *,
        timestamp_col: str = "timestamp",
        max_age_seconds: float = 60.0,
        now: datetime | None = None,
    ) -> bool:
        if frame.empty or timestamp_col not in frame.columns:
            return True
        reference = now or datetime.now(UTC)
        latest = pd.to_datetime(frame[timestamp_col], utc=True).max()
        age_seconds = (reference - latest.to_pydatetime()).total_seconds()
        return age_seconds > max_age_seconds

    def quarantine_suspicious_data(self, frame: pd.DataFrame, suspicious_rows: pd.Series) -> pd.DataFrame:
        quarantined = frame.loc[suspicious_rows].copy()
        if not quarantined.empty:
            self.quarantine_frames.append(quarantined)
        return quarantined

    def compute_metrics(
        self,
        frame: pd.DataFrame,
        *,
        timestamp_col: str = "timestamp",
        expected_frequency: pd.Timedelta | None = None,
        now: datetime | None = None,
    ) -> DataQualityMetrics:
        missing = self.detect_missing_timestamps(frame, timestamp_col=timestamp_col, expected_frequency=expected_frequency)
        outliers = self.detect_outliers(frame)
        integrity_mask = self.validate_ohlcv_integrity(frame)
        suspicious_index = set(idx for rows in outliers.values() for idx in rows)
        if not integrity_mask.empty:
            suspicious_index.update(int(idx) for idx in frame.index[~integrity_mask])
        suspicious_mask = frame.index.to_series().isin(suspicious_index)
        quarantined = self.quarantine_suspicious_data(frame, suspicious_mask)

        total_rows = max(len(frame), 1)
        valid_rows = int(integrity_mask.sum()) if not integrity_mask.empty else 0
        completeness = float(max(0.0, 1.0 - (len(missing) / total_rows)))
        outlier_rate = float(len(suspicious_index) / total_rows)
        missing_rate = float(len(missing) / total_rows)
        valid_ratio = float(valid_rows / total_rows)

        if frame.empty or timestamp_col not in frame.columns:
            staleness_seconds = float("inf")
        else:
            reference = now or datetime.now(UTC)
            latest = pd.to_datetime(frame[timestamp_col], utc=True).max()
            staleness_seconds = float((reference - latest.to_pydatetime()).total_seconds())

        return DataQualityMetrics(
            completeness=completeness,
            staleness_seconds=staleness_seconds,
            outlier_rate=outlier_rate,
            missing_rate=missing_rate,
            quarantined_rows=int(len(quarantined)),
            valid_ohlcv_ratio=valid_ratio,
            timestamp=now or datetime.now(UTC),
        )

    def record_metrics(self, metrics: DataQualityMetrics) -> None:
        if self.writer is None:
            return
        self.writer.append(
            "data_quality",
            fields={
                "completeness": metrics.completeness,
                "staleness_seconds": metrics.staleness_seconds,
                "outlier_rate": metrics.outlier_rate,
                "missing_rate": metrics.missing_rate,
                "quarantined_rows": metrics.quarantined_rows,
                "valid_ohlcv_ratio": metrics.valid_ohlcv_ratio,
            },
            timestamp=metrics.timestamp,
        )

    def generate_alerts(self, metrics: DataQualityMetrics) -> list[DataQualityAlert]:
        alerts: list[DataQualityAlert] = []
        if metrics.completeness < self.completeness_threshold:
            alerts.append(
                DataQualityAlert(
                    metric="completeness",
                    threshold=self.completeness_threshold,
                    observed=metrics.completeness,
                    message=f"Data completeness {metrics.completeness:.3f} below {self.completeness_threshold:.3f}",
                )
            )
        if metrics.staleness_seconds > self.staleness_threshold_seconds:
            alerts.append(
                DataQualityAlert(
                    metric="staleness_seconds",
                    threshold=self.staleness_threshold_seconds,
                    observed=metrics.staleness_seconds,
                    message=f"Data staleness {metrics.staleness_seconds:.1f}s exceeds {self.staleness_threshold_seconds:.1f}s",
                )
            )
        if metrics.outlier_rate > self.outlier_rate_threshold:
            alerts.append(
                DataQualityAlert(
                    metric="outlier_rate",
                    threshold=self.outlier_rate_threshold,
                    observed=metrics.outlier_rate,
                    message=f"Outlier rate {metrics.outlier_rate:.3f} exceeds {self.outlier_rate_threshold:.3f}",
                )
            )
        return alerts

    def evaluate(
        self,
        frame: pd.DataFrame,
        *,
        timestamp_col: str = "timestamp",
        expected_frequency: pd.Timedelta | None = None,
        now: datetime | None = None,
    ) -> tuple[DataQualityMetrics, list[DataQualityAlert]]:
        metrics = self.compute_metrics(
            frame,
            timestamp_col=timestamp_col,
            expected_frequency=expected_frequency,
            now=now,
        )
        self.record_metrics(metrics)
        return metrics, self.generate_alerts(metrics)
