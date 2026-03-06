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
import polars as pl
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from backend.app.models.config import settings
from backend.dataset.features import build_feature_matrix, get_feature_columns

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

