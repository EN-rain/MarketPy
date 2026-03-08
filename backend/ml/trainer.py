"""Walk-forward ensemble trainer for crypto return prediction.

Trains per horizon using candidate models:
- XGBoost
- LightGBM (if installed)
- CatBoost (if installed)

Adds:
- Isotonic calibration on validation predictions
- Threshold tuning for buy/sell signal generation
- Ensemble weighting by inverse validation RMSE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import polars as pl
from sklearn.feature_selection import RFE
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor

from backend.app.models.config import settings
from backend.dataset.features import build_feature_matrix, get_feature_columns
from backend.dataset.indicators import IndicatorConfig, IndicatorPipeline
from backend.dataset.scalers import FeatureScaler, ScalerType
from backend.ml.feature_importance_tracker import FeatureImportanceTracker
from backend.ml.model_manager import DeploymentMode, ManagedModel, ModelManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


try:
    from lightgbm import LGBMRegressor  # type: ignore
except Exception:
    LGBMRegressor = None

try:
    from catboost import CatBoostRegressor  # type: ignore
except Exception:
    CatBoostRegressor = None

try:
    import optuna
except Exception:  # pragma: no cover - optional dependency path
    optuna = None  # type: ignore[assignment]


@dataclass
class SplitData:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    train_size: int
    val_size: int
    test_size: int


@dataclass(slots=True)
class CollectedTrainingData:
    merged_data: pd.DataFrame
    lookback_days: int
    completeness_ratio: float
    quality_score: float
    rows: int


@dataclass(slots=True)
class FeatureEngineeringResult:
    frame: pd.DataFrame
    feature_columns: list[str]
    target_columns: list[str]
    scaler: FeatureScaler
    fill_limit: int


@dataclass(slots=True)
class FeatureSelectionResult:
    selected_features: list[str]
    dropped_low_importance: list[str]
    dropped_correlated: list[str]
    importance_scores: dict[str, float]


@dataclass(slots=True)
class HyperparameterOptimizationResult:
    algorithm: str
    best_params: dict[str, Any]
    best_value: float
    trial_count: int


@dataclass(slots=True)
class TrainedModelArtifact:
    model_id: str
    target_column: str
    algorithm_metrics: dict[str, dict[str, float]]
    validation: dict[str, Any]
    ensemble_method: str
    ensemble_summary: dict[str, Any]
    artifact_path: Path
    metrics_path: Path
    metadata_path: Path
    feature_columns: list[str]
    hyperparameters: dict[str, dict[str, Any]]


def walk_forward_split(
    df: pl.DataFrame,
    train_pct: float = 0.6,
    val_pct: float = 0.2,
    embargo_bars: int = 0,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Time-sorted walk-forward split with optional embargo."""
    n = len(df)
    train_end = int(n * train_pct)
    val_end = int(n * (train_pct + val_pct))
    val_start = min(train_end + embargo_bars, n)
    test_start = min(val_end + embargo_bars, n)
    return df[:train_end], df[val_start:val_end], df[test_start:]


def _prepare_split(df: pl.DataFrame, target_col: str, feature_cols: list[str], embargo_bars: int) -> SplitData:
    train_df, val_df, test_df = walk_forward_split(df, embargo_bars=embargo_bars)
    if len(train_df) == 0 or len(val_df) == 0 or len(test_df) == 0:
        raise ValueError(
            f"Insufficient rows after split: train={len(train_df)} val={len(val_df)} test={len(test_df)}"
        )
    return SplitData(
        X_train=train_df.select(feature_cols).to_numpy(),
        y_train=train_df[target_col].to_numpy(),
        X_val=val_df.select(feature_cols).to_numpy(),
        y_val=val_df[target_col].to_numpy(),
        X_test=test_df.select(feature_cols).to_numpy(),
        y_test=test_df[target_col].to_numpy(),
        train_size=len(train_df),
        val_size=len(val_df),
        test_size=len(test_df),
    )


def _candidate_models() -> dict[str, Any]:
    models: dict[str, Any] = {
        "xgb": XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            early_stopping_rounds=50,
            random_state=42,
            verbosity=0,
        )
    }
    if LGBMRegressor is not None:
        models["lgbm"] = LGBMRegressor(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=63,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
        )
    if CatBoostRegressor is not None:
        models["catboost"] = CatBoostRegressor(
            iterations=500,
            learning_rate=0.05,
            depth=6,
            random_seed=42,
            verbose=False,
        )
    return models


def _fit_model(name: str, model: Any, split: SplitData) -> tuple[Any, np.ndarray]:
    if name == "xgb":
        model.fit(split.X_train, split.y_train, eval_set=[(split.X_val, split.y_val)], verbose=False)
    elif name == "lgbm":
        model.fit(split.X_train, split.y_train, eval_set=[(split.X_val, split.y_val)])
    else:
        model.fit(split.X_train, split.y_train)
    val_pred = model.predict(split.X_val)
    return model, np.asarray(val_pred, dtype=float)


def _directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.sign(y_true) == np.sign(y_pred)))


def _sharpe_like(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    mean = float(np.mean(returns))
    std = float(np.std(returns))
    if std <= 1e-12:
        return 0.0
    return mean / std


def _profit_factor(trade_returns: np.ndarray) -> float:
    gains = float(np.sum(trade_returns[trade_returns > 0]))
    losses = float(np.sum(np.abs(trade_returns[trade_returns < 0])))
    if losses <= 1e-12:
        return gains if gains > 0 else 0.0
    return gains / losses


def _tune_thresholds(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Tune buy/sell thresholds on validation set using simple Sharpe-like objective."""
    candidates = np.linspace(0.0, max(1e-6, float(np.std(y_pred)) * 1.5), 20)
    best = {"buy_threshold": 0.0, "sell_threshold": 0.0, "objective": -1e9}

    for t in candidates:
        long_mask = y_pred >= t
        short_mask = y_pred <= -t
        pnl = np.zeros_like(y_true, dtype=float)
        pnl[long_mask] = y_true[long_mask]
        pnl[short_mask] = -y_true[short_mask]
        objective = _sharpe_like(pnl)
        if objective > best["objective"]:
            best = {"buy_threshold": float(t), "sell_threshold": float(-t), "objective": float(objective)}
    return best


class TrainingPipeline:
    """End-to-end training pipeline for model training and registration."""

    def __init__(
        self,
        *,
        output_dir: str | Path | None = None,
        registry_dir: str | Path | None = None,
        scaler_type: ScalerType = ScalerType.STANDARD,
        indicator_config: IndicatorConfig | None = None,
        feature_importance_tracker: FeatureImportanceTracker | None = None,
        model_manager: ModelManager | None = None,
    ) -> None:
        self.output_dir = Path(output_dir or settings.model_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.indicator_pipeline = IndicatorPipeline(indicator_config or IndicatorConfig())
        self.scaler_type = scaler_type
        self.feature_importance_tracker = feature_importance_tracker or FeatureImportanceTracker(
            str(self.output_dir / "feature_importance")
        )
        self.model_manager = model_manager or ModelManager(registry_dir or (self.output_dir / "registry"))

    @staticmethod
    def _prepare_timestamped_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
        if frame is None:
            return None
        out = frame.copy()
        if "timestamp" not in out.columns:
            raise ValueError("Training data frames must include a 'timestamp' column")
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
        out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        return out.reset_index(drop=True)

    @staticmethod
    def _infer_fill_limit(frame: pd.DataFrame) -> int:
        if "timestamp" not in frame.columns or len(frame) < 3:
            return 12
        diffs = frame["timestamp"].diff().dropna()
        if diffs.empty:
            return 12
        median_seconds = max(1.0, float(diffs.dt.total_seconds().median()))
        return max(1, int(3600 / median_seconds))

    @staticmethod
    def _target_horizons() -> dict[str, int]:
        return {"y_5m": 1, "y_15m": 3, "y_1h": 12, "y_4h": 48}

    @staticmethod
    def _model_id_from_target(target_column: str) -> str:
        return {
            "y_5m": "model_5m",
            "y_15m": "model_15m",
            "y_1h": "model_1h",
            "y_4h": "model_4h",
        }.get(target_column, f"model_{target_column.replace('y_', '')}")

    def available_algorithms(self) -> list[str]:
        names = ["xgb"]
        if LGBMRegressor is not None:
            names.append("lgbm")
        if CatBoostRegressor is not None:
            names.append("catboost")
        return names

    def collect_training_data(
        self,
        *,
        market_data: pd.DataFrame,
        alternative_data: pd.DataFrame | None = None,
        historical_features: pd.DataFrame | None = None,
        lookback_days: int = 90,
        min_completeness: float = 0.75,
    ) -> CollectedTrainingData:
        market = self._prepare_timestamped_frame(market_data)
        alternative = self._prepare_timestamped_frame(alternative_data)
        features = self._prepare_timestamped_frame(historical_features)
        assert market is not None

        latest_ts = market["timestamp"].max()
        start_ts = latest_ts - pd.Timedelta(days=lookback_days)
        merged = market.loc[market["timestamp"] >= start_ts].copy()

        for extra in (alternative, features):
            if extra is None:
                continue
            merged = pd.merge_asof(
                merged.sort_values("timestamp"),
                extra.sort_values("timestamp"),
                on="timestamp",
                direction="backward",
            )

        completeness_ratio = float(1.0 - (merged.isna().sum().sum() / max(1, merged.size)))
        uniqueness_ratio = float(merged["timestamp"].nunique() / max(1, len(merged)))
        quality_score = float(max(0.0, min(1.0, 0.7 * completeness_ratio + 0.3 * uniqueness_ratio)))
        if completeness_ratio < min_completeness:
            raise ValueError(
                f"Training data completeness {completeness_ratio:.3f} below minimum {min_completeness:.3f}"
            )

        return CollectedTrainingData(
            merged_data=merged.reset_index(drop=True),
            lookback_days=lookback_days,
            completeness_ratio=completeness_ratio,
            quality_score=quality_score,
            rows=len(merged),
        )

    def compute_training_features(
        self,
        dataset: pd.DataFrame,
        *,
        target_horizons: dict[str, int] | None = None,
    ) -> FeatureEngineeringResult:
        frame = self._prepare_timestamped_frame(dataset)
        assert frame is not None

        fill_limit = self._infer_fill_limit(frame)
        frame = frame.ffill(limit=fill_limit)

        required_ohlcv = {"open", "high", "low", "close", "volume"}
        if required_ohlcv.issubset(frame.columns):
            indicator_input = frame[
                ["timestamp", "open", "high", "low", "close", "volume"]
            ].copy()
            indicator_output = self.indicator_pipeline.compute(indicator_input)
            for column in indicator_output.columns:
                if column not in frame.columns:
                    frame[column] = indicator_output[column].to_numpy()

        if "mid" not in frame.columns:
            if "close" in frame.columns:
                frame["mid"] = frame["close"]
            else:
                raise ValueError("Expected at least one of 'mid' or 'close' in training data")
        if "spread" not in frame.columns:
            frame["spread"] = 0.0

        frame["hour_of_day"] = frame["timestamp"].dt.hour
        frame["day_of_week"] = frame["timestamp"].dt.dayofweek
        frame["ret_1"] = np.log(frame["mid"].clip(lower=1e-6)).diff()
        frame["spread_pct"] = frame["spread"] / frame["mid"].replace(0.0, np.nan)

        target_horizons = target_horizons or self._target_horizons()
        for target_name, bars_ahead in target_horizons.items():
            if target_name not in frame.columns:
                frame[target_name] = (
                    np.log(frame["mid"].shift(-bars_ahead).clip(lower=1e-6))
                    - np.log(frame["mid"].clip(lower=1e-6))
                )

        frame = frame.dropna(axis=1, how="all")
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
        target_columns = [column for column in target_horizons if column in frame.columns]
        excluded = {"timestamp", *target_columns}
        feature_columns = [
            column
            for column in frame.columns
            if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])
        ]

        scaler = FeatureScaler(self.scaler_type)
        scaled = scaler.fit_transform(frame[feature_columns])
        out = frame.copy()
        for column in feature_columns:
            out[column] = out[column].astype(float)
        out.loc[:, feature_columns] = np.asarray(scaled, dtype=float)

        return FeatureEngineeringResult(
            frame=out,
            feature_columns=feature_columns,
            target_columns=target_columns,
            scaler=scaler,
            fill_limit=fill_limit,
        )

    def feature_selection(
        self,
        frame: pd.DataFrame,
        *,
        target_column: str,
        feature_columns: list[str],
        importance_threshold: float = 0.01,
        correlation_threshold: float = 0.95,
    ) -> FeatureSelectionResult:
        X = frame[feature_columns].to_numpy(dtype=float)
        y = frame[target_column].to_numpy(dtype=float)
        base_model = XGBRegressor(
            n_estimators=80,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            verbosity=0,
        )
        base_model.fit(X, y)
        result = permutation_importance(base_model, X, y, n_repeats=5, random_state=42)
        raw_scores = {
            name: max(0.0, float(result.importances_mean[idx]))
            for idx, name in enumerate(feature_columns)
        }
        total = float(sum(raw_scores.values()))
        importance_scores = (
            {name: float(score / total) for name, score in raw_scores.items()}
            if total > 0
            else {name: 0.0 for name in feature_columns}
        )
        kept = [name for name, score in importance_scores.items() if score >= importance_threshold]
        dropped_low = [name for name in feature_columns if name not in kept]
        if not kept:
            kept = sorted(feature_columns, key=lambda name: importance_scores[name], reverse=True)[
                : min(10, len(feature_columns))
            ]
            dropped_low = [name for name in feature_columns if name not in kept]

        corr = frame[kept].corr(numeric_only=True).abs()
        dropped_correlated: list[str] = []
        if not corr.empty:
            upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
            for column in upper.columns:
                if any(upper[column].fillna(0.0) > correlation_threshold):
                    dropped_correlated.append(column)
            kept = [column for column in kept if column not in dropped_correlated]

        if len(kept) > 3:
            selector = RFE(
                estimator=XGBRegressor(
                    n_estimators=60,
                    max_depth=3,
                    learning_rate=0.1,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    random_state=42,
                    verbosity=0,
                ),
                n_features_to_select=max(3, len(kept) // 2),
                step=1,
            )
            selector.fit(frame[kept].to_numpy(dtype=float), y)
            kept = [name for name, keep_flag in zip(kept, selector.support_, strict=False) if keep_flag]

        return FeatureSelectionResult(
            selected_features=kept,
            dropped_low_importance=dropped_low,
            dropped_correlated=dropped_correlated,
            importance_scores=importance_scores,
        )

    def _build_estimator(self, algorithm: str, params: dict[str, Any]) -> Any:
        if algorithm == "xgb":
            return XGBRegressor(
                n_estimators=int(params.get("n_estimators", 120)),
                max_depth=int(params.get("max_depth", 4)),
                learning_rate=float(params.get("learning_rate", 0.05)),
                subsample=float(params.get("subsample", 0.9)),
                colsample_bytree=float(params.get("colsample_bytree", 0.9)),
                random_state=42,
                verbosity=0,
            )
        if algorithm == "lgbm" and LGBMRegressor is not None:
            return LGBMRegressor(
                n_estimators=int(params.get("n_estimators", 120)),
                learning_rate=float(params.get("learning_rate", 0.05)),
                num_leaves=int(params.get("num_leaves", 31)),
                subsample=float(params.get("subsample", 0.9)),
                colsample_bytree=float(params.get("colsample_bytree", 0.9)),
                random_state=42,
            )
        if algorithm == "catboost" and CatBoostRegressor is not None:
            return CatBoostRegressor(
                iterations=int(params.get("iterations", 120)),
                learning_rate=float(params.get("learning_rate", 0.05)),
                depth=int(params.get("depth", 4)),
                random_seed=42,
                verbose=False,
            )
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    def _suggest_params(self, trial: Any, algorithm: str) -> dict[str, Any]:
        if algorithm == "xgb":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 160),
                "max_depth": trial.suggest_int("max_depth", 2, 6),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
                "subsample": trial.suggest_float("subsample", 0.7, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            }
        if algorithm == "lgbm":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 160),
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
                "subsample": trial.suggest_float("subsample", 0.7, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            }
        return {
            "iterations": trial.suggest_int("iterations", 50, 160),
            "depth": trial.suggest_int("depth", 2, 6),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
        }

    def hyperparameter_optimization(
        self,
        frame: pd.DataFrame,
        *,
        target_column: str,
        feature_columns: list[str],
        algorithms: list[str] | None = None,
        n_trials: int = 100,
        timeout_hours: float = 4.0,
    ) -> dict[str, HyperparameterOptimizationResult]:
        algorithms = algorithms or self.available_algorithms()
        X = frame[feature_columns].to_numpy(dtype=float)
        y = frame[target_column].to_numpy(dtype=float)
        n_splits = min(5, max(2, len(frame) // 30))
        splitter = TimeSeriesSplit(n_splits=n_splits)
        timeout_seconds = int(timeout_hours * 3600)
        results: dict[str, HyperparameterOptimizationResult] = {}

        for algorithm in algorithms:
            if optuna is None:
                results[algorithm] = HyperparameterOptimizationResult(
                    algorithm=algorithm,
                    best_params={},
                    best_value=0.0,
                    trial_count=0,
                )
                continue

            def objective(trial: Any) -> float:
                params = self._suggest_params(trial, algorithm)
                scores: list[float] = []
                for train_idx, val_idx in splitter.split(X):
                    model = self._build_estimator(algorithm, params)
                    model.fit(X[train_idx], y[train_idx])
                    pred = np.asarray(model.predict(X[val_idx]), dtype=float)
                    pnl = np.sign(pred) * y[val_idx]
                    scores.append(_sharpe_like(pnl))
                return float(np.mean(scores))

            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=n_trials, timeout=timeout_seconds, show_progress_bar=False)
            results[algorithm] = HyperparameterOptimizationResult(
                algorithm=algorithm,
                best_params=dict(study.best_trial.params),
                best_value=float(study.best_value),
                trial_count=len(study.trials),
            )

        return results

    @staticmethod
    def _split_dataframe(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        ordered = frame.sort_values("timestamp").reset_index(drop=True)
        if "timestamp" in ordered.columns and not ordered.empty:
            max_ts = ordered["timestamp"].max()
            test_start = max_ts - pd.Timedelta(days=7)
            test_df = ordered.loc[ordered["timestamp"] >= test_start].copy()
            train_val_df = ordered.loc[ordered["timestamp"] < test_start].copy()
            if len(test_df) >= 10 and len(train_val_df) >= 20:
                val_size = max(5, int(len(train_val_df) * 0.2))
                train_df = train_val_df.iloc[:-val_size].copy()
                val_df = train_val_df.iloc[-val_size:].copy()
                if len(train_df) > 0 and len(val_df) > 0:
                    return train_df, val_df, test_df
        train_end = int(len(ordered) * 0.6)
        val_end = int(len(ordered) * 0.8)
        return ordered.iloc[:train_end].copy(), ordered.iloc[train_end:val_end].copy(), ordered.iloc[val_end:].copy()

    def optimize_ensemble(
        self,
        y_true: np.ndarray,
        candidate_predictions: dict[str, np.ndarray],
    ) -> dict[str, Any]:
        if not candidate_predictions:
            raise ValueError("No candidate predictions available for ensemble optimization")

        names = list(candidate_predictions)
        stacked = np.column_stack([candidate_predictions[name] for name in names])
        methods: dict[str, np.ndarray] = {"average": np.mean(stacked, axis=1)}

        rmses = {
            name: float(np.sqrt(mean_squared_error(y_true, pred)))
            for name, pred in candidate_predictions.items()
        }
        inverse = {name: 1.0 / max(1e-9, value) for name, value in rmses.items()}
        total = sum(inverse.values())
        weights = {name: float(value / total) for name, value in inverse.items()}
        weighted = np.zeros_like(y_true, dtype=float)
        for name, prediction in candidate_predictions.items():
            weighted += weights[name] * prediction
        methods["weighted"] = weighted

        stacker = LinearRegression()
        stacker.fit(stacked, y_true)
        methods["stacking"] = np.asarray(stacker.predict(stacked), dtype=float)

        scores: dict[str, dict[str, float]] = {}
        for method_name, prediction in methods.items():
            pnl = np.sign(prediction) * y_true
            scores[method_name] = {
                "rmse": float(np.sqrt(mean_squared_error(y_true, prediction))),
                "directional_accuracy": _directional_accuracy(y_true, prediction),
                "sharpe_ratio": _sharpe_like(pnl),
            }

        best_method = max(scores, key=lambda name: (scores[name]["sharpe_ratio"], -scores[name]["rmse"]))
        best_individual_sharpe = max(_sharpe_like(np.sign(pred) * y_true) for pred in candidate_predictions.values())
        improvement = 0.0
        if abs(best_individual_sharpe) > 1e-12:
            improvement = (scores[best_method]["sharpe_ratio"] - best_individual_sharpe) / abs(best_individual_sharpe)

        diversity = self.measure_ensemble_diversity(candidate_predictions)

        return {
            "method": best_method,
            "predictions": methods[best_method],
            "scores": scores,
            "weights": weights,
            "stacker": stacker,
            "exceeds_best_individual_by_2pct": improvement >= 0.02,
            "improvement_vs_best_individual": float(improvement),
            "diversity": diversity,
        }

    @staticmethod
    def measure_ensemble_diversity(candidate_predictions: dict[str, np.ndarray]) -> dict[str, Any]:
        names = list(candidate_predictions.keys())
        if len(names) < 2:
            return {"avg_pairwise_correlation": 0.0, "penalty": 0.0, "diversity_score": 1.0}
        series = [np.asarray(candidate_predictions[name], dtype=float) for name in names]
        correlations: list[float] = []
        for i in range(len(series)):
            for j in range(i + 1, len(series)):
                a = series[i]
                b = series[j]
                if np.std(a) <= 1e-12 or np.std(b) <= 1e-12:
                    corr = 1.0
                else:
                    corr = float(np.corrcoef(a, b)[0, 1])
                correlations.append(corr)
        avg_corr = float(np.mean(np.abs(correlations))) if correlations else 0.0
        penalty = float(max(0.0, avg_corr - 0.8))
        return {
            "avg_pairwise_correlation": avg_corr,
            "penalty": penalty,
            "diversity_score": float(max(0.0, 1.0 - avg_corr)),
        }

    def optimize_horizon_specific_ensembles(
        self,
        y_true_by_horizon: dict[str, np.ndarray],
        predictions_by_horizon: dict[str, dict[str, np.ndarray]],
    ) -> dict[str, dict[str, Any]]:
        """Optimize ensemble weights independently for each horizon."""
        output: dict[str, dict[str, Any]] = {}
        for horizon, y_true in y_true_by_horizon.items():
            candidates = predictions_by_horizon.get(horizon, {})
            if not candidates:
                continue
            output[horizon] = self.optimize_ensemble(np.asarray(y_true, dtype=float), candidates)
        return output

    def validate_model(
        self,
        y_true: np.ndarray,
        predictions: np.ndarray,
        *,
        confidence: np.ndarray | None = None,
    ) -> dict[str, Any]:
        y_true = np.asarray(y_true, dtype=float)
        predictions = np.asarray(predictions, dtype=float)
        trade_returns = np.sign(predictions) * y_true
        confidence = (
            np.asarray(confidence, dtype=float)
            if confidence is not None
            else np.clip(np.abs(predictions) / max(1e-9, float(np.std(predictions)) * 2.0), 0.0, 1.0)
        )

        bins = np.linspace(0.0, 1.0, 6)
        reliability: list[dict[str, float]] = []
        for left, right in zip(bins[:-1], bins[1:], strict=False):
            mask = (confidence >= left) & (confidence <= right if right == 1.0 else confidence < right)
            if not np.any(mask):
                continue
            reliability.append(
                {
                    "bin_start": float(left),
                    "bin_end": float(right),
                    "mean_confidence": float(np.mean(confidence[mask])),
                    "empirical_accuracy": float(np.mean(np.sign(predictions[mask]) == np.sign(y_true[mask]))),
                }
            )

        validation = {
            "mae": float(mean_absolute_error(y_true, predictions)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, predictions))),
            "directional_accuracy": _directional_accuracy(y_true, predictions),
            "sharpe_ratio": _sharpe_like(trade_returns),
            "win_rate": float(np.mean(trade_returns > 0)),
            "profit_factor": _profit_factor(trade_returns),
            "reliability_diagram": reliability,
        }
        validation["passes_validation"] = bool(
            validation["sharpe_ratio"] > 0.5 and validation["directional_accuracy"] > 0.52
        )
        return validation

    def train_models(
        self,
        frame: pd.DataFrame,
        *,
        target_columns: list[str],
        feature_columns: list[str],
        optimized_hyperparameters: dict[str, HyperparameterOptimizationResult] | None = None,
        algorithms: list[str] | None = None,
    ) -> dict[str, TrainedModelArtifact]:
        algorithms = algorithms or self.available_algorithms()
        optimized_hyperparameters = optimized_hyperparameters or {}
        train_df, val_df, test_df = self._split_dataframe(frame)
        trained: dict[str, TrainedModelArtifact] = {}

        for target_column in target_columns:
            X_train = train_df[feature_columns].to_numpy(dtype=float)
            y_train = train_df[target_column].to_numpy(dtype=float)
            X_val = val_df[feature_columns].to_numpy(dtype=float)
            y_val = val_df[target_column].to_numpy(dtype=float)
            X_test = test_df[feature_columns].to_numpy(dtype=float)
            y_test = test_df[target_column].to_numpy(dtype=float)
            if min(len(X_train), len(X_val), len(X_test)) == 0:
                raise ValueError(f"Insufficient rows for training target {target_column}")

            fitted_models: dict[str, Any] = {}
            val_predictions: dict[str, np.ndarray] = {}
            algorithm_metrics: dict[str, dict[str, float]] = {}
            used_hyperparameters: dict[str, dict[str, Any]] = {}

            for algorithm in algorithms:
                params = optimized_hyperparameters.get(algorithm)
                used_hyperparameters[algorithm] = params.best_params if params is not None else {}
                model = self._build_estimator(algorithm, used_hyperparameters[algorithm])
                model.fit(X_train, y_train)
                val_prediction = np.asarray(model.predict(X_val), dtype=float)
                fitted_models[algorithm] = model
                val_predictions[algorithm] = val_prediction
                algorithm_metrics[algorithm] = {
                    "rmse": float(np.sqrt(mean_squared_error(y_val, val_prediction))),
                    "directional_accuracy": _directional_accuracy(y_val, val_prediction),
                    "sharpe_ratio": _sharpe_like(np.sign(val_prediction) * y_val),
                }

            ensemble = self.optimize_ensemble(y_val, val_predictions)
            test_predictions = {
                algorithm: np.asarray(model.predict(X_test), dtype=float)
                for algorithm, model in fitted_models.items()
            }
            if ensemble["method"] == "average":
                test_prediction = np.mean(np.column_stack(list(test_predictions.values())), axis=1)
            elif ensemble["method"] == "weighted":
                test_prediction = np.zeros_like(y_test, dtype=float)
                for algorithm, prediction in test_predictions.items():
                    test_prediction += ensemble["weights"].get(algorithm, 0.0) * prediction
            else:
                stacked_test = np.column_stack([test_predictions[name] for name in test_predictions])
                test_prediction = np.asarray(ensemble["stacker"].predict(stacked_test), dtype=float)

            calibrator = IsotonicRegression(out_of_bounds="clip")
            calibrator.fit(np.asarray(ensemble["predictions"], dtype=float), y_val)
            calibrated_prediction = np.asarray(calibrator.transform(test_prediction), dtype=float)
            thresholds = _tune_thresholds(y_val, np.asarray(calibrator.transform(ensemble["predictions"]), dtype=float))
            validation = self.validate_model(y_test, calibrated_prediction)
            model_id = self._model_id_from_target(target_column)

            artifact_payload = {
                "models": fitted_models,
                "weights": ensemble["weights"],
                "calibrator": calibrator,
                "feature_columns": feature_columns,
                "thresholds": thresholds,
                "ensemble_method": ensemble["method"],
                "trained_at": datetime.now(UTC).isoformat(),
            }
            artifact_path = self.output_dir / f"{model_id}.joblib"
            metrics_path = self.output_dir / f"{model_id}_metrics.json"
            metadata_path = self.output_dir / f"{model_id}_metadata.json"
            joblib.dump(artifact_payload, artifact_path)
            metrics_path.write_text(
                json.dumps(
                    {
                        "model_id": model_id,
                        "target_column": target_column,
                        "algorithm_metrics": algorithm_metrics,
                        "ensemble_summary": {
                            key: value for key, value in ensemble.items() if key not in {"predictions", "stacker"}
                        },
                        "validation": validation,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            metadata_path.write_text(
                json.dumps(
                    {
                        "model_id": model_id,
                        "target_column": target_column,
                        "feature_columns": feature_columns,
                        "feature_hash": hashlib.sha256(",".join(feature_columns).encode("utf-8")).hexdigest(),
                        "trained_at": datetime.now(UTC).isoformat(),
                        "row_count": len(frame),
                        "algorithms": algorithms,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            trained[target_column] = TrainedModelArtifact(
                model_id=model_id,
                target_column=target_column,
                algorithm_metrics=algorithm_metrics,
                validation=validation,
                ensemble_method=ensemble["method"],
                ensemble_summary={key: value for key, value in ensemble.items() if key not in {"predictions", "stacker"}},
                artifact_path=artifact_path,
                metrics_path=metrics_path,
                metadata_path=metadata_path,
                feature_columns=feature_columns,
                hyperparameters=used_hyperparameters,
            )

        return trained

    def register_trained_models(
        self,
        trained_models: dict[str, TrainedModelArtifact],
    ) -> dict[str, ManagedModel]:
        registrations: dict[str, ManagedModel] = {}
        for artifact in trained_models.values():
            registered = self.model_manager.register_model(
                model_id=artifact.model_id,
                artifact_path=artifact.artifact_path,
                algorithm=artifact.ensemble_method,
                hyperparameters=artifact.hyperparameters,
                feature_list=artifact.feature_columns,
                performance_metrics={
                    "MAE": float(artifact.validation["mae"]),
                    "RMSE": float(artifact.validation["rmse"]),
                    "directional_accuracy": float(artifact.validation["directional_accuracy"]),
                    "sharpe_ratio": float(artifact.validation["sharpe_ratio"]),
                },
            )
            registrations[artifact.model_id] = self.model_manager.deploy_model(
                artifact.model_id,
                registered.version,
                mode=DeploymentMode.SHADOW,
                traffic_allocation=0.0,
            )
        return registrations

    def run_complete_training_pipeline(
        self,
        *,
        market_data: pd.DataFrame,
        alternative_data: pd.DataFrame | None = None,
        historical_features: pd.DataFrame | None = None,
        lookback_days: int = 90,
        target_columns: list[str] | None = None,
        algorithms: list[str] | None = None,
        optimization_trials: int = 5,
        optimization_hours: float = 0.01,
    ) -> dict[str, Any]:
        collected = self.collect_training_data(
            market_data=market_data,
            alternative_data=alternative_data,
            historical_features=historical_features,
            lookback_days=lookback_days,
        )
        engineered = self.compute_training_features(collected.merged_data)
        target_columns = target_columns or engineered.target_columns
        selection = self.feature_selection(
            engineered.frame,
            target_column=target_columns[0],
            feature_columns=engineered.feature_columns,
        )
        optimized = self.hyperparameter_optimization(
            engineered.frame,
            target_column=target_columns[0],
            feature_columns=selection.selected_features,
            algorithms=algorithms,
            n_trials=optimization_trials,
            timeout_hours=optimization_hours,
        )
        trained = self.train_models(
            engineered.frame,
            target_columns=target_columns,
            feature_columns=selection.selected_features,
            optimized_hyperparameters=optimized,
            algorithms=algorithms,
        )
        registrations = self.register_trained_models(trained)
        return {
            "data_quality": {
                "rows": collected.rows,
                "completeness_ratio": collected.completeness_ratio,
                "quality_score": collected.quality_score,
            },
            "selected_features": selection.selected_features,
            "optimization": {
                name: {
                    "best_params": result.best_params,
                    "best_value": result.best_value,
                    "trial_count": result.trial_count,
                }
                for name, result in optimized.items()
            },
            "trained_models": {
                name: {
                    "artifact_path": str(artifact.artifact_path),
                    "passes_validation": bool(artifact.validation["passes_validation"]),
                    "ensemble_method": artifact.ensemble_method,
                }
                for name, artifact in trained.items()
            },
            "registrations": {
                name: {"version": model.version, "deployment_mode": model.deployment_mode}
                for name, model in registrations.items()
            },
        }


def train_model(
    df: pl.DataFrame,
    target_col: str,
    feature_cols: list[str],
    model_name: str = "model",
    output_dir: Path | None = None,
    embargo_bars: int = 0,
) -> dict[str, Any]:
    output_dir = output_dir or Path(settings.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    split = _prepare_split(df, target_col, feature_cols, embargo_bars)
    logger.info(
        "Training %s: train=%s val=%s test=%s",
        model_name,
        split.train_size,
        split.val_size,
        split.test_size,
    )

    fitted: dict[str, Any] = {}
    val_preds: dict[str, np.ndarray] = {}
    val_rmse: dict[str, float] = {}

    for name, model in _candidate_models().items():
        try:
            fit_model, pred = _fit_model(name, model, split)
            fitted[name] = fit_model
            val_preds[name] = pred
            val_rmse[name] = float(np.sqrt(mean_squared_error(split.y_val, pred)))
            logger.info("  Candidate %-8s val_rmse=%.6f", name, val_rmse[name])
        except Exception as exc:
            logger.warning("  Candidate %s failed: %s", name, exc)

    if not fitted:
        raise RuntimeError("No candidate model trained successfully")

    # Ensemble weights from inverse RMSE.
    inv = {name: 1.0 / max(rmse, 1e-9) for name, rmse in val_rmse.items()}
    total_inv = sum(inv.values())
    weights = {name: float(v / total_inv) for name, v in inv.items()}

    val_ensemble = np.zeros_like(split.y_val, dtype=float)
    for name, pred in val_preds.items():
        val_ensemble += weights[name] * pred

    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(val_ensemble, split.y_val)

    test_ensemble = np.zeros_like(split.y_test, dtype=float)
    for name, model in fitted.items():
        pred = np.asarray(model.predict(split.X_test), dtype=float)
        test_ensemble += weights[name] * pred
    test_calibrated = np.asarray(calibrator.transform(test_ensemble), dtype=float)

    thresholds = _tune_thresholds(split.y_val, np.asarray(calibrator.transform(val_ensemble), dtype=float))

    metrics = {
        "model_name": model_name,
        "target": target_col,
        "train_size": split.train_size,
        "val_size": split.val_size,
        "test_size": split.test_size,
        "mae": float(mean_absolute_error(split.y_test, test_calibrated)),
        "rmse": float(np.sqrt(mean_squared_error(split.y_test, test_calibrated))),
        "r2": float(r2_score(split.y_test, test_calibrated)),
        "directional_accuracy": _directional_accuracy(split.y_test, test_calibrated),
        "calibration_rmse": float(np.sqrt(mean_squared_error(split.y_test, test_calibrated))),
        "embargo_bars": embargo_bars,
        "candidates": {name: {"val_rmse": val_rmse[name], "weight": weights[name]} for name in fitted},
        "thresholds": thresholds,
    }

    # Save artifacts.
    model_artifact = {
        "models": fitted,
        "weights": weights,
        "calibrator": calibrator,
        "feature_columns": feature_cols,
        "thresholds": thresholds,
        "trained_at": datetime.now(UTC).isoformat(),
    }
    model_path = output_dir / f"{model_name}.joblib"
    metrics_path = output_dir / f"{model_name}_metrics.json"
    metadata_path = output_dir / f"{model_name}_metadata.json"
    thresholds_path = output_dir / f"{model_name}_thresholds.json"

    joblib.dump(model_artifact, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    metadata = {
        "model_name": model_name,
        "target_col": target_col,
        "feature_columns": feature_cols,
        "feature_hash": hashlib.sha256(",".join(feature_cols).encode("utf-8")).hexdigest(),
        "trained_at": datetime.now(UTC).isoformat(),
        "row_count": len(df),
        "embargo_bars": embargo_bars,
        "model_candidates": list(fitted.keys()),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    thresholds_path.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")

    logger.info(
        "  MAE=%.6f RMSE=%.6f R2=%.4f DirAcc=%.3f",
        metrics["mae"],
        metrics["rmse"],
        metrics["r2"],
        metrics["directional_accuracy"],
    )
    logger.info("  Saved: %s", model_path)
    return metrics


def train_all_horizons(
    data_path: str | Path,
    horizons: dict[str, int] | None = None,
    output_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if horizons is None:
        horizons = {"y_1h": 12, "y_6h": 72, "y_1d": 288}

    output_path = Path(output_dir) if output_dir else Path(settings.model_dir)
    embargo_bars = max(horizons.values())

    logger.info("Loading data from %s", data_path)
    df = pl.read_parquet(str(data_path))
    logger.info("Loaded %s bars", len(df))

    df = build_feature_matrix(df, horizons=horizons, embargo_bars=embargo_bars)
    feature_cols = get_feature_columns(df)
    logger.info("Features: %s columns, %s rows after cleanup", len(feature_cols), len(df))
    if len(df) < 100:
        logger.warning("Not enough data for training (need at least 100 rows)")
        return []

    all_metrics: list[dict[str, Any]] = []
    for target_col in horizons:
        name = f"model_{target_col.replace('y_', '')}"
        all_metrics.append(
            train_model(
                df=df,
                target_col=target_col,
                feature_cols=feature_cols,
                model_name=name,
                output_dir=output_path,
                embargo_bars=embargo_bars,
            )
        )
    return all_metrics


def main():
    parser = argparse.ArgumentParser(description="Train ensemble return prediction models")
    parser.add_argument("--data-path", type=str, required=True, help="Path to Parquet bar data")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for models")
    args = parser.parse_args()
    train_all_horizons(data_path=args.data_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
