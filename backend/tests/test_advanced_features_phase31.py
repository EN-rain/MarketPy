from __future__ import annotations

import numpy as np
import pandas as pd

from backend.features.definitions.microstructure_features import (
    depth_ratio,
    order_book_imbalance,
    spread_bps,
    vpin,
)
from backend.ml.confidence_intervals import QuantileIntervalEstimator
from backend.ml.feature_importance_tracker import FeatureImportanceResult, FeatureImportanceTracker
from backend.ml.retraining import RetrainingPipeline
from backend.ml.trainer import TrainingPipeline
from backend.portfolio.optimizer import PortfolioOptimizer


def test_microstructure_features_and_constraints() -> None:
    assert -1.0 <= order_book_imbalance(120, 80) <= 1.0
    assert spread_bps(100, 101) > 0
    assert depth_ratio(10, 5) == 2.0
    assert 0.0 <= vpin(pd.Series([10, 12, 8]), pd.Series([4, -5, 3])) <= 1.0

    optimizer = PortfolioOptimizer()
    returns = pd.DataFrame(
        {
            "A": [0.01, 0.02, 0.015, -0.01],
            "B": [0.011, 0.021, 0.016, -0.011],
            "C": [0.002, -0.001, 0.003, 0.001],
        }
    )
    constrained = optimizer.apply_correlation_constraints(
        {"A": 0.5, "B": 0.4, "C": 0.1},
        returns,
        correlation_threshold=0.7,
        max_cluster_weight=0.4,
    )
    assert abs(sum(constrained.values()) - 1.0) < 1e-9


def test_adaptive_retraining_horizon_ensemble_confidence_and_diversity(tmp_path) -> None:
    days_fast = RetrainingPipeline.adaptive_retraining_interval_days(drift_score=0.9, volatility_ratio=2.0)
    days_slow = RetrainingPipeline.adaptive_retraining_interval_days(drift_score=0.01, volatility_ratio=0.2)
    assert days_fast <= days_slow

    trainer = TrainingPipeline(output_dir=tmp_path / "models")
    y_by_horizon = {"5m": np.array([0.01, -0.01, 0.02]), "1h": np.array([0.03, -0.02, 0.01])}
    p_by_horizon = {
        "5m": {"xgb": np.array([0.009, -0.012, 0.018]), "lgbm": np.array([0.01, -0.011, 0.019])},
        "1h": {"xgb": np.array([0.029, -0.021, 0.012]), "lgbm": np.array([0.028, -0.02, 0.011])},
    }
    optimized = trainer.optimize_horizon_specific_ensembles(y_by_horizon, p_by_horizon)
    assert set(optimized.keys()) == {"5m", "1h"}
    assert "diversity" in optimized["5m"]

    intervals = QuantileIntervalEstimator().estimate(0.01, np.array([-0.02, -0.01, 0.0, 0.01, 0.02]))
    assert intervals.lower <= intervals.median <= intervals.upper

    tracker = FeatureImportanceTracker(output_dir=str(tmp_path / "fi"))
    r1 = FeatureImportanceResult(model_id="m1", computed_at=pd.Timestamp.utcnow().to_pydatetime(), method="tree", scores={"a": 0.6, "b": 0.4})
    r2 = FeatureImportanceResult(model_id="m1", computed_at=pd.Timestamp.utcnow().to_pydatetime(), method="tree", scores={"a": 0.2, "b": 0.8})
    tracker.append_history(r1)
    tracker.append_history(r2)
    drift = tracker.detect_importance_drift("m1", threshold=0.2)
    assert drift["alert"] is True
