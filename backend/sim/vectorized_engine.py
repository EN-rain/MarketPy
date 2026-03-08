"""Vectorized backtesting engine with vectorbt fallback support."""

from __future__ import annotations

import itertools
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pandas is required for VectorizedBacktestEngine") from exc

try:  # pragma: no cover - optional dependency
    import vectorbt as vbt  # type: ignore
except Exception:  # pragma: no cover
    vbt = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    EVENT_DRIVEN = "event_driven"
    VECTORIZED = "vectorized"


class VectorizedStrategy(ABC):
    """Base class for vectorized strategies."""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return dataframe with `entries` and `exits` boolean columns."""
        raise NotImplementedError


@dataclass(slots=True)
class BacktestResult:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    trades: pd.DataFrame
    equity_curve: pd.Series
    execution_mode: ExecutionMode


@dataclass(slots=True)
class OptimizationResult:
    best_params: dict[str, Any]
    best_score: float
    trials: list[dict[str, Any]]


class VectorizedBacktestEngine:
    """Runs signal-based backtests in vectorized mode."""

    def __init__(
        self,
        initial_cash: float = 10_000.0,
        fee_rate: float = 0.001,
        slippage: float = 0.0,
    ) -> None:
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.slippage = slippage

    def _fallback_run(self, signals: pd.DataFrame) -> BacktestResult:
        close = signals["close"].astype(float).to_numpy()
        entries = signals["entries"].fillna(False).astype(bool).to_numpy()
        exits = signals["exits"].fillna(False).astype(bool).to_numpy()

        cash = self.initial_cash
        position = 0.0
        entry_price = 0.0
        equity_points: list[float] = []
        trade_returns: list[float] = []
        trade_rows: list[dict[str, Any]] = []

        for idx, price in enumerate(close):
            if entries[idx] and position <= 0:
                fill_price = price * (1 + self.slippage)
                size = cash / fill_price if fill_price > 0 else 0.0
                fee = fill_price * size * self.fee_rate
                cash -= fill_price * size + fee
                position = size
                entry_price = fill_price
                trade_rows.append({"timestamp": signals.index[idx], "side": "BUY", "price": fill_price, "size": size})
            elif exits[idx] and position > 0:
                fill_price = price * (1 - self.slippage)
                proceeds = fill_price * position
                fee = proceeds * self.fee_rate
                cash += proceeds - fee
                ret = (fill_price - entry_price) / entry_price if entry_price > 0 else 0.0
                trade_returns.append(ret)
                trade_rows.append({"timestamp": signals.index[idx], "side": "SELL", "price": fill_price, "size": position})
                position = 0.0
                entry_price = 0.0

            equity = cash + position * price
            equity_points.append(equity)

        equity_curve = pd.Series(equity_points, index=signals.index, name="equity")
        total_return = (equity_curve.iloc[-1] / self.initial_cash - 1.0) if len(equity_curve) else 0.0
        returns = equity_curve.pct_change().dropna()
        sharpe = float((returns.mean() / returns.std()) * math.sqrt(252)) if returns.std() and len(returns) else 0.0
        running_max = equity_curve.cummax()
        drawdown = (equity_curve / running_max - 1.0).min() if len(equity_curve) else 0.0

        wins = [value for value in trade_returns if value > 0]
        losses = [abs(value) for value in trade_returns if value < 0]
        profit_factor = float(sum(wins) / sum(losses)) if losses else float("inf") if wins else 0.0
        win_rate = float(len(wins) / len(trade_returns)) if trade_returns else 0.0

        return BacktestResult(
            total_return=float(total_return),
            sharpe_ratio=sharpe,
            max_drawdown=float(abs(drawdown)),
            win_rate=win_rate,
            profit_factor=float(profit_factor if np.isfinite(profit_factor) else 0.0),
            trades=pd.DataFrame(trade_rows),
            equity_curve=equity_curve,
            execution_mode=ExecutionMode.VECTORIZED,
        )

    def run(self, strategy: VectorizedStrategy, data: pd.DataFrame, params: dict[str, Any] | None = None) -> BacktestResult:
        frame = data.copy()
        if "close" not in frame.columns:
            raise ValueError("Vectorized backtest requires `close` column")

        if params:
            for key, value in params.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)

        signals = strategy.generate_signals(frame)
        if "entries" not in signals.columns or "exits" not in signals.columns:
            raise ValueError("Strategy must output `entries` and `exits` columns")
        signals = signals.copy()
        if "close" not in signals.columns:
            signals["close"] = frame["close"]

        if vbt is None:
            return self._fallback_run(signals)

        portfolio = vbt.Portfolio.from_signals(  # pragma: no cover - optional dependency
            close=signals["close"],
            entries=signals["entries"].astype(bool),
            exits=signals["exits"].astype(bool),
            init_cash=self.initial_cash,
            fees=self.fee_rate,
            slippage=self.slippage,
        )
        stats = portfolio.stats()
        total_return = float(stats.get("Total Return [%]", 0.0)) / 100.0
        sharpe = float(stats.get("Sharpe Ratio", 0.0))
        max_dd = float(abs(stats.get("Max Drawdown [%]", 0.0))) / 100.0
        win_rate = float(stats.get("Win Rate [%]", 0.0)) / 100.0
        pf = float(stats.get("Profit Factor", 0.0))

        trades = portfolio.trades.records_readable
        equity_curve = portfolio.value()
        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=pf,
            trades=trades,
            equity_curve=equity_curve,
            execution_mode=ExecutionMode.VECTORIZED,
        )

    def optimize(
        self,
        strategy: VectorizedStrategy,
        data: pd.DataFrame,
        param_grid: dict[str, list[Any]],
        metric: str = "total_return",
    ) -> OptimizationResult:
        keys = list(param_grid.keys())
        values = [param_grid[key] for key in keys]
        best_score = float("-inf")
        best_params: dict[str, Any] = {}
        trials: list[dict[str, Any]] = []

        for combination in itertools.product(*values):
            params = {key: value for key, value in zip(keys, combination, strict=False)}
            result = self.run(strategy, data, params=params)
            score = getattr(result, metric)
            trial = {"params": params, metric: score}
            trials.append(trial)
            if score > best_score:
                best_score = float(score)
                best_params = params

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            trials=trials,
        )
