"""Retraining pipeline with trigger evaluation and shadow promotion flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from backend.ml.drift_detection import DriftDetector, DriftReport
from backend.ml.model_manager import DeploymentMode, ManagedModel, ModelManager
from backend.ml.trainer import TrainingPipeline


@dataclass(slots=True)
class RetrainingDecision:
    should_retrain: bool
    reason: str
    details: dict[str, Any]


@dataclass(slots=True)
class ValidationDecision:
    shadow_deployed: bool
    promoted: bool
    rolled_back: bool
    shadow_improvement: float
    production_version: str | None
    challenger_version: str | None


class RetrainingPipeline:
    """Coordinates retraining, shadow deployment, and promotion checks."""

    def __init__(
        self,
        *,
        training_pipeline: TrainingPipeline | None = None,
        model_manager: ModelManager | None = None,
        drift_detector: DriftDetector | None = None,
    ) -> None:
        self.training_pipeline = training_pipeline or TrainingPipeline()
        self.model_manager = model_manager or self.training_pipeline.model_manager
        self.drift_detector = drift_detector or DriftDetector()

    def trigger_retraining(
        self,
        *,
        reason: str,
        now: datetime,
        last_trained_at: datetime | None = None,
        drift_report: DriftReport | None = None,
        volatility_now: float | None = None,
        baseline_volatility: float | None = None,
        recent_accuracy: list[float] | None = None,
    ) -> RetrainingDecision:
        details: dict[str, Any] = {"reason": reason}
        if reason == "scheduled":
            should = last_trained_at is None or (now - last_trained_at) >= timedelta(days=30)
            details["days_since_last_train"] = None if last_trained_at is None else (now - last_trained_at).days
            return RetrainingDecision(should, reason, details)
        if reason == "drift":
            should = bool(drift_report and drift_report.alert)
            if drift_report is not None:
                details["drift_report"] = {
                    "performance_drift": drift_report.performance_drift,
                    "feature_drift": drift_report.feature_drift,
                    "psi_drift": drift_report.psi_drift,
                    "prediction_shift": drift_report.prediction_shift,
                }
            return RetrainingDecision(should, reason, details)
        if reason == "volatility":
            base = max(float(baseline_volatility or 0.0), 1e-9)
            current = float(volatility_now or 0.0)
            increase = (current - base) / base
            details["volatility_increase"] = increase
            return RetrainingDecision(increase >= 0.5, reason, details)
        if reason == "performance":
            accuracy = recent_accuracy or []
            should = len(accuracy) >= 3 and all(value < 0.52 for value in accuracy[-3:])
            details["recent_accuracy"] = accuracy[-3:]
            return RetrainingDecision(should, reason, details)
        raise ValueError(f"Unsupported retraining reason: {reason}")

    @staticmethod
    def adaptive_retraining_interval_days(
        *,
        drift_score: float,
        volatility_ratio: float,
        min_days: int = 1,
        max_days: int = 30,
        base_days: int = 7,
    ) -> int:
        """Adjust retraining cadence based on drift and volatility regime."""
        drift_score = max(0.0, min(1.0, float(drift_score)))
        volatility_ratio = max(0.0, float(volatility_ratio))
        pressure = max(drift_score, min(volatility_ratio / 2.0, 1.0))
        interval = int(round(base_days - (base_days - min_days) * pressure))
        if pressure < 0.15:
            interval = int(round(min(max_days, base_days * 2)))
        return max(min_days, min(max_days, interval))

    def run_retraining(
        self,
        *,
        market_data: pd.DataFrame,
        alternative_data: pd.DataFrame | None = None,
        historical_features: pd.DataFrame | None = None,
        target_columns: list[str] | None = None,
        algorithms: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.training_pipeline.run_complete_training_pipeline(
            market_data=market_data,
            alternative_data=alternative_data,
            historical_features=historical_features,
            target_columns=target_columns,
            algorithms=algorithms,
            optimization_trials=1,
            optimization_hours=0.001,
        )

    def validate_retrained_model(
        self,
        *,
        model_id: str,
        production_metrics: dict[str, float],
        challenger_metrics: dict[str, float],
    ) -> ValidationDecision:
        production = self.model_manager.get_model(model_id, deployment_mode=DeploymentMode.PRODUCTION)
        challenger = self.model_manager.get_model(model_id)
        challenger = challenger if challenger.version != production.version else production
        if challenger.version == production.version:
            return ValidationDecision(False, False, False, 0.0, production.version, challenger.version)

        challenger_shadow = self.model_manager.deploy_model(
            model_id,
            challenger.version,
            mode=DeploymentMode.SHADOW,
            traffic_allocation=0.0,
        )
        prod_score = float(production_metrics.get("sharpe_ratio", production_metrics.get("directional_accuracy", 0.0)))
        challenger_score = float(challenger_metrics.get("sharpe_ratio", challenger_metrics.get("directional_accuracy", 0.0)))
        baseline = max(abs(prod_score), 1e-9)
        improvement = (challenger_score - prod_score) / baseline
        promoted = improvement >= 0.05
        rolled_back = False

        if promoted:
            self.model_manager.deploy_model(
                model_id,
                challenger_shadow.version,
                mode=DeploymentMode.PRODUCTION,
                traffic_allocation=1.0,
            )
        else:
            rolled_back = True
            self.model_manager.deploy_model(
                model_id,
                production.version,
                mode=DeploymentMode.PRODUCTION,
                traffic_allocation=1.0,
            )

        return ValidationDecision(
            shadow_deployed=True,
            promoted=promoted,
            rolled_back=rolled_back,
            shadow_improvement=float(improvement),
            production_version=production.version,
            challenger_version=challenger.version,
        )
