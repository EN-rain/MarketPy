"""Walk-forward optimization helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    train_rows: int
    validation_rows: int


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    windows: list[WalkForwardWindow]
    metrics: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    window_count: int
    overall_sharpe: float
    win_rate: float
    max_drawdown: float
    stability_cv: float
    mean_window_return: float
    regime_performance: dict[str, dict[str, float]]


class WalkForwardOptimizer:
    """Creates temporally ordered train/validation windows."""

    def __init__(
        self,
        *,
        initial_cash: float = 10_000.0,
        fee_rate: float = 0.001,
        slippage: float = 0.0,
    ) -> None:
        self.initial_cash = float(initial_cash)
        self.fee_rate = float(fee_rate)
        self.slippage = float(slippage)

    def _build_engine(self):
        from backend.sim.vectorized_engine import VectorizedBacktestEngine

        return VectorizedBacktestEngine(
            initial_cash=self.initial_cash,
            fee_rate=self.fee_rate,
            slippage=self.slippage,
        )

    def run_walk_forward(
        self,
        frame: pd.DataFrame,
        *,
        train_days: int = 90,
        validation_days: int = 30,
        step_days: int = 30,
    ) -> WalkForwardResult:
        ordered = frame.sort_values("timestamp").reset_index(drop=True)
        ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True)
        if ordered.empty:
            return WalkForwardResult([], [])

        windows: list[WalkForwardWindow] = []
        metrics: list[dict[str, Any]] = []
        start = ordered["timestamp"].min()
        end = ordered["timestamp"].max()
        cursor = start
        while cursor + pd.Timedelta(days=train_days + validation_days) <= end:
            train_start = cursor
            train_end = cursor + pd.Timedelta(days=train_days)
            validation_start = train_end
            validation_end = validation_start + pd.Timedelta(days=validation_days)

            train_df = ordered[(ordered["timestamp"] >= train_start) & (ordered["timestamp"] < train_end)]
            validation_df = ordered[(ordered["timestamp"] >= validation_start) & (ordered["timestamp"] < validation_end)]
            if len(train_df) and len(validation_df):
                windows.append(
                    WalkForwardWindow(
                        train_start=train_start,
                        train_end=train_end,
                        validation_start=validation_start,
                        validation_end=validation_end,
                        train_rows=len(train_df),
                        validation_rows=len(validation_df),
                    )
                )
                metrics.append(
                    {
                        "train_rows": len(train_df),
                        "validation_rows": len(validation_df),
                        "stability_score": float(len(validation_df) / max(len(train_df), 1)),
                    }
                )
            cursor = cursor + pd.Timedelta(days=step_days)

        return WalkForwardResult(windows, metrics)

    @staticmethod
    def detect_regime_changes(frame: pd.DataFrame, regime_column: str = "regime") -> list[pd.Timestamp]:
        if frame.empty or regime_column not in frame.columns:
            return []
        ordered = frame.sort_values("timestamp").reset_index(drop=True).copy()
        ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True)
        changes = ordered[regime_column].astype(str).ne(ordered[regime_column].astype(str).shift(1))
        change_rows = ordered.loc[changes & ordered.index.to_series().gt(0), "timestamp"]
        return list(change_rows)

    @staticmethod
    def model_slippage(
        order_size: float,
        volatility: float,
        liquidity: float,
        *,
        calibration_factor: float = 1.0,
        base_bps: float = 1.0,
    ) -> float:
        safe_liquidity = max(float(liquidity), 1e-9)
        size_ratio = max(float(order_size), 0.0) / safe_liquidity
        size_term = 15.0 * math.sqrt(size_ratio)
        volatility_term = 25.0 * max(float(volatility), 0.0)
        liquidity_term = 10.0 / math.sqrt(safe_liquidity)
        slippage_bps = base_bps + max(float(calibration_factor), 0.0) * (
            size_term + volatility_term + liquidity_term
        )
        return float(slippage_bps / 10_000.0)

    def calibrate_slippage(self, execution_records: pd.DataFrame | None) -> float:
        if execution_records is None or execution_records.empty:
            return 1.0
        required = {"order_size", "volatility", "liquidity", "observed_slippage_bps"}
        if not required.issubset(execution_records.columns):
            return 1.0

        modeled_bps: list[float] = []
        observed_bps: list[float] = []
        for row in execution_records.itertuples(index=False):
            modeled = self.model_slippage(
                getattr(row, "order_size"),
                getattr(row, "volatility"),
                getattr(row, "liquidity"),
                calibration_factor=1.0,
            )
            modeled_bps.append(modeled * 10_000.0)
            observed_bps.append(abs(float(getattr(row, "observed_slippage_bps"))))

        mean_modeled = float(np.mean(modeled_bps)) if modeled_bps else 0.0
        mean_observed = float(np.mean(observed_bps)) if observed_bps else 0.0
        if mean_modeled <= 0:
            return 1.0
        return float(max(mean_observed / mean_modeled, 0.1))

    def optimize_regime_parameters(
        self,
        strategy,
        train_df: pd.DataFrame,
        param_grid: dict[str, list[Any]],
        *,
        regime_column: str = "regime",
        metric: str = "total_return",
    ) -> dict[str, dict[str, Any]]:
        if regime_column not in train_df.columns:
            return {}

        engine = self._build_engine()
        regime_results: dict[str, dict[str, Any]] = {}
        for regime, regime_df in train_df.groupby(regime_column):
            regime_frame = regime_df.sort_values("timestamp").reset_index(drop=True)
            if len(regime_frame) < 10:
                continue
            optimization = engine.optimize(strategy, regime_frame, param_grid, metric=metric)
            regime_results[str(regime)] = {
                "best_params": optimization.best_params,
                "best_score": float(optimization.best_score),
                "trials": optimization.trials,
                "rows": int(len(regime_frame)),
            }
        return regime_results

    def validate_regime_parameters(
        self,
        strategy,
        validation_df: pd.DataFrame,
        regime_parameters: dict[str, dict[str, Any]],
        *,
        regime_column: str = "regime",
    ) -> dict[str, dict[str, float]]:
        engine = self._build_engine()
        regime_metrics: dict[str, dict[str, float]] = {}

        if regime_column not in validation_df.columns:
            result = engine.run(strategy, validation_df.sort_values("timestamp").reset_index(drop=True))
            return {
                "unknown": {
                    "total_return": float(result.total_return),
                    "sharpe_ratio": float(result.sharpe_ratio),
                    "max_drawdown": float(result.max_drawdown),
                    "win_rate": float(result.win_rate),
                    "rows": float(len(validation_df)),
                }
            }

        for regime, regime_df in validation_df.groupby(regime_column):
            regime_name = str(regime)
            params = regime_parameters.get(regime_name, {}).get("best_params")
            ordered = regime_df.sort_values("timestamp").reset_index(drop=True)
            if ordered.empty:
                continue
            result = engine.run(strategy, ordered, params=params)
            regime_metrics[regime_name] = {
                "total_return": float(result.total_return),
                "sharpe_ratio": float(result.sharpe_ratio),
                "max_drawdown": float(result.max_drawdown),
                "win_rate": float(result.win_rate),
                "rows": float(len(ordered)),
            }

        return regime_metrics

    def run_regime_walk_forward(
        self,
        strategy,
        frame: pd.DataFrame,
        param_grid: dict[str, list[Any]],
        *,
        regime_column: str = "regime",
        train_days: int = 90,
        validation_days: int = 30,
        step_days: int = 30,
        metric: str = "total_return",
        execution_records: pd.DataFrame | None = None,
    ) -> WalkForwardResult:
        base = self.run_walk_forward(
            frame,
            train_days=train_days,
            validation_days=validation_days,
            step_days=step_days,
        )
        ordered = frame.sort_values("timestamp").reset_index(drop=True).copy()
        ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True)
        calibration_factor = self.calibrate_slippage(execution_records)

        enriched_metrics: list[dict[str, Any]] = []
        for window in base.windows:
            train_df = ordered[
                (ordered["timestamp"] >= window.train_start) & (ordered["timestamp"] < window.train_end)
            ].copy()
            validation_df = ordered[
                (ordered["timestamp"] >= window.validation_start)
                & (ordered["timestamp"] < window.validation_end)
            ].copy()

            regime_parameters = self.optimize_regime_parameters(
                strategy,
                train_df,
                param_grid,
                regime_column=regime_column,
                metric=metric,
            )
            regime_performance = self.validate_regime_parameters(
                strategy,
                validation_df,
                regime_parameters,
                regime_column=regime_column,
            )
            regime_changes = self.detect_regime_changes(validation_df, regime_column=regime_column)

            weighted_return = 0.0
            total_rows = 0.0
            avg_volatility = float(validation_df.get("volatility", pd.Series([0.0])).fillna(0.0).mean())
            avg_liquidity = float(validation_df.get("liquidity", pd.Series([1_000_000.0])).fillna(1_000_000.0).mean())
            avg_order_size = float(validation_df.get("order_size", pd.Series([1.0])).fillna(1.0).mean())
            modeled_slippage = self.model_slippage(
                avg_order_size,
                avg_volatility,
                avg_liquidity,
                calibration_factor=calibration_factor,
            )

            for values in regime_performance.values():
                rows = float(values.get("rows", 0.0))
                total_rows += rows
                weighted_return += values.get("total_return", 0.0) * rows

            validation_total_return = weighted_return / total_rows if total_rows else 0.0
            enriched_metrics.append(
                {
                    "train_rows": window.train_rows,
                    "validation_rows": window.validation_rows,
                    "stability_score": float(window.validation_rows / max(window.train_rows, 1)),
                    "regime_change_count": len(regime_changes),
                    "regime_parameters": regime_parameters,
                    "regime_performance": regime_performance,
                    "validation_total_return": float(validation_total_return),
                    "modeled_slippage": float(modeled_slippage),
                }
            )

        return WalkForwardResult(base.windows, enriched_metrics)

    @staticmethod
    def generate_report(result: WalkForwardResult) -> WalkForwardReport:
        window_returns = np.array(
            [float(metric.get("validation_total_return", 0.0)) for metric in result.metrics],
            dtype=float,
        )
        if window_returns.size == 0:
            return WalkForwardReport(
                window_count=0,
                overall_sharpe=0.0,
                win_rate=0.0,
                max_drawdown=0.0,
                stability_cv=0.0,
                mean_window_return=0.0,
                regime_performance={},
            )

        win_rate = float(np.mean(window_returns > 0))
        std = float(np.std(window_returns, ddof=0))
        mean_return = float(np.mean(window_returns))
        overall_sharpe = float((mean_return / std) * math.sqrt(len(window_returns))) if std > 0 else 0.0
        equity = np.cumprod(1.0 + window_returns)
        peak = np.maximum.accumulate(equity)
        max_drawdown = float(np.max(1.0 - (equity / np.maximum(peak, 1e-12))))
        stability_cv = float(std / abs(mean_return)) if abs(mean_return) > 1e-12 else 0.0

        regime_aggregate: dict[str, dict[str, list[float]]] = {}
        for metric in result.metrics:
            for regime, values in metric.get("regime_performance", {}).items():
                entry = regime_aggregate.setdefault(regime, {"total_return": [], "sharpe_ratio": [], "win_rate": []})
                entry["total_return"].append(float(values.get("total_return", 0.0)))
                entry["sharpe_ratio"].append(float(values.get("sharpe_ratio", 0.0)))
                entry["win_rate"].append(float(values.get("win_rate", 0.0)))

        regime_performance = {
            regime: {
                key: float(np.mean(series)) if series else 0.0
                for key, series in values.items()
            }
            for regime, values in regime_aggregate.items()
        }

        return WalkForwardReport(
            window_count=len(result.windows),
            overall_sharpe=overall_sharpe,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            stability_cv=stability_cv,
            mean_window_return=mean_return,
            regime_performance=regime_performance,
        )
