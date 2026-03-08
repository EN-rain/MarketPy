"""Phase 8 training pipeline coverage."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.ml.trainer import TrainingPipeline


def _make_market_frame(rows: int = 2200) -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-01", periods=rows, freq="5min", tz="UTC")
    base = np.linspace(100.0, 118.0, rows)
    seasonal = 1.8 * np.sin(np.linspace(0.0, 25.0, rows))
    close = base + seasonal
    open_ = close - 0.2
    high = close + 0.4
    low = close - 0.4
    volume = 1_000 + 40 * np.cos(np.linspace(0.0, 18.0, rows))
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "mid": close,
            "spread": np.full(rows, 0.12),
            "volume": volume,
        }
    )


def _make_alternative_frame(timestamps: pd.Series) -> pd.DataFrame:
    values = np.sin(np.linspace(0.0, 12.0, len(timestamps)))
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "sentiment_score": values,
            "funding_rate": values * 0.001,
        }
    )


def _make_feature_frame(timestamps: pd.Series) -> pd.DataFrame:
    feature = np.cos(np.linspace(0.0, 8.0, len(timestamps)))
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "cached_feature": feature,
            "cached_feature_dup": feature * 1.0,
        }
    )


def test_collect_training_data_merges_and_scores_quality(tmp_path: Path) -> None:
    pipeline = TrainingPipeline(output_dir=tmp_path / "models", registry_dir=tmp_path / "registry")
    market = _make_market_frame()
    alternative = _make_alternative_frame(market["timestamp"])
    features = _make_feature_frame(market["timestamp"])

    collected = pipeline.collect_training_data(
        market_data=market,
        alternative_data=alternative,
        historical_features=features,
        lookback_days=7,
    )

    assert collected.rows > 0
    assert collected.completeness_ratio > 0.95
    assert collected.quality_score > 0.9
    assert {"sentiment_score", "cached_feature"}.issubset(collected.merged_data.columns)


def test_feature_engineering_and_selection_reduce_correlated_columns(tmp_path: Path) -> None:
    pipeline = TrainingPipeline(output_dir=tmp_path / "models", registry_dir=tmp_path / "registry")
    market = _make_market_frame()
    alternative = _make_alternative_frame(market["timestamp"])
    features = _make_feature_frame(market["timestamp"])
    collected = pipeline.collect_training_data(
        market_data=market,
        alternative_data=alternative,
        historical_features=features,
        lookback_days=7,
    )

    engineered = pipeline.compute_training_features(collected.merged_data)
    selection = pipeline.feature_selection(
        engineered.frame,
        target_column="y_5m",
        feature_columns=engineered.feature_columns,
    )

    means = engineered.frame[engineered.feature_columns].mean().abs()
    assert float(means.max()) < 1.0
    assert "cached_feature_dup" not in selection.selected_features
    assert selection.selected_features


def test_training_pipeline_end_to_end_registers_shadow_models(tmp_path: Path) -> None:
    pipeline = TrainingPipeline(output_dir=tmp_path / "models", registry_dir=tmp_path / "registry")
    market = _make_market_frame()
    alternative = _make_alternative_frame(market["timestamp"])
    features = _make_feature_frame(market["timestamp"])
    algorithms = pipeline.available_algorithms()[:1]

    report = pipeline.run_complete_training_pipeline(
        market_data=market,
        alternative_data=alternative,
        historical_features=features,
        lookback_days=7,
        target_columns=["y_5m"],
        algorithms=algorithms,
        optimization_trials=1,
        optimization_hours=0.001,
    )

    assert report["selected_features"]
    assert "y_5m" in report["trained_models"]
    trained = report["trained_models"]["y_5m"]
    assert Path(trained["artifact_path"]).exists()
    assert trained["ensemble_method"] in {"average", "weighted", "stacking"}
    registration = report["registrations"]["model_5m"]
    assert registration["deployment_mode"] == "shadow"
