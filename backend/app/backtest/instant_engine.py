"""Instant backtesting engine optimized for sub-5s strategy iteration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import polars as pl


@dataclass(frozen=True)
class BacktestTrade:
    timestamp: datetime
    symbol: str
    side: str
    price: float
    size: float


@dataclass
class BacktestResult:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trades: list[BacktestTrade]
    equity_curve: list[dict[str, Any]]
    execution_ms: float


class HistoricalDataCache:
    """Simple in-memory cache for historical bars."""

    def __init__(self):
        self._cache: dict[tuple[str, str], pl.DataFrame] = {}

    def get_or_load(self, data_dir: str, symbol: str) -> pl.DataFrame:
        key = (data_dir, symbol)
        if key in self._cache:
            return self._cache[key]
        parquet_path = Path(data_dir) / "parquet" / f"market_id={symbol}" / "bars.parquet"
        if not parquet_path.exists():
            raise FileNotFoundError(f"No bar data for symbol={symbol}")
        df = pl.read_parquet(parquet_path)
        self._cache[key] = df
        return df


class VectorizedExecutor:
    """Vectorized strategy execution on DataFrame series."""

    @staticmethod
    def execute_momentum(
        df: pl.DataFrame, *, lookback_bars: int = 12, threshold: float = 0.01
    ) -> pl.DataFrame:
        if "close" not in df.columns:
            close = pl.col("mid")
        else:
            close = pl.col("close")
        out = df.with_columns(
            close.alias("price"),
            ((close / close.shift(lookback_bars)) - 1.0).fill_null(0.0).alias("momentum"),
        ).with_columns(
            pl.when(pl.col("momentum") > threshold)
            .then(1)
            .when(pl.col("momentum") < -threshold)
            .then(-1)
            .otherwise(0)
            .alias("position")
        )
        return out


class InstantBacktestEngine:
    """Run vectorized backtests with cached historical data."""

    def __init__(self, *, data_dir: str):
        self.data_dir = data_dir
        self.cache = HistoricalDataCache()
        self.executor = VectorizedExecutor()

    def run_backtest(
        self,
        *,
        strategy: str,
        symbols: list[str],
        timeframe: str = "5m",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        lookback_bars: int = 12,
        momentum_threshold: float = 0.01,
    ) -> BacktestResult:
        start = perf_counter()
        _ = timeframe  # reserved for future resampling support.

        all_equity: list[dict[str, Any]] = []
        all_trades: list[BacktestTrade] = []
        total_pnl = 0.0
        wins = 0
        losses = 0

        for symbol in symbols:
            df = self.cache.get_or_load(self.data_dir, symbol)
            df = self._resample_timeframe(df, timeframe)
            if start_date is not None:
                df = df.filter(pl.col("timestamp") >= pl.lit(start_date))
            if end_date is not None:
                df = df.filter(pl.col("timestamp") <= pl.lit(end_date))
            if df.is_empty():
                continue

            if strategy != "momentum":
                raise ValueError(f"Unsupported instant strategy: {strategy}")
            out = self.executor.execute_momentum(
                df, lookback_bars=lookback_bars, threshold=momentum_threshold
            )
            out = out.with_columns(pl.col("price").pct_change().fill_null(0.0).alias("ret"))
            out = out.with_columns(
                (pl.col("position").shift(1).fill_null(0) * pl.col("ret")).alias("strat_ret")
            )
            out = out.with_columns((1.0 + pl.col("strat_ret")).cum_prod().alias("equity"))

            price = out["price"].to_list()
            position = out["position"].to_list()
            timestamp = out["timestamp"].to_list()
            for idx in range(1, len(position)):
                if position[idx] != position[idx - 1]:
                    side = "BUY" if position[idx] > position[idx - 1] else "SELL"
                    all_trades.append(
                        BacktestTrade(
                            timestamp=timestamp[idx],
                            symbol=symbol,
                            side=side,
                            price=float(price[idx]),
                            size=1.0,
                        )
                    )

            equity_series = out["equity"].to_list()
            for ts, eq in zip(timestamp, equity_series, strict=False):
                all_equity.append(
                    {"timestamp": ts.isoformat(), "equity": float(eq), "symbol": symbol}
                )

            symbol_return = float(equity_series[-1] - 1.0) if equity_series else 0.0
            total_pnl += symbol_return
            if symbol_return >= 0:
                wins += 1
            else:
                losses += 1

        if not all_equity:
            return BacktestResult(
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                trades=[],
                equity_curve=[],
                execution_ms=(perf_counter() - start) * 1000.0,
            )

        equity_values = [item["equity"] for item in all_equity]
        peak = equity_values[0]
        max_drawdown = 0.0
        for value in equity_values:
            peak = max(peak, value)
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)

        returns = []
        for idx in range(1, len(equity_values)):
            prev = equity_values[idx - 1]
            curr = equity_values[idx]
            if prev > 0:
                returns.append((curr - prev) / prev)
        if returns:
            mean = sum(returns) / len(returns)
            var = sum((r - mean) ** 2 for r in returns) / len(returns)
            std = var**0.5
            sharpe = mean / std if std > 0 else 0.0
        else:
            sharpe = 0.0

        completed = wins + losses
        win_rate = wins / completed if completed > 0 else 0.0
        return BacktestResult(
            total_return=total_pnl,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trades=all_trades,
            equity_curve=all_equity,
            execution_ms=(perf_counter() - start) * 1000.0,
        )

    @staticmethod
    def _resample_timeframe(df: pl.DataFrame, timeframe: str) -> pl.DataFrame:
        if timeframe in {"1m", "5m"}:
            return df.sort("timestamp")
        if timeframe not in {"1h", "1d"}:
            return df.sort("timestamp")

        every = timeframe
        price_col = "close" if "close" in df.columns else "mid"
        return (
            df.sort("timestamp")
            .group_by_dynamic("timestamp", every=every, closed="right")
            .agg(
                pl.col(price_col).first().alias("open"),
                pl.col(price_col).max().alias("high"),
                pl.col(price_col).min().alias("low"),
                pl.col(price_col).last().alias("close"),
                pl.col("mid").last().alias("mid"),
                pl.col("bid").last().alias("bid"),
                pl.col("ask").last().alias("ask"),
                pl.col("spread").mean().alias("spread"),
                pl.col("volume").sum().alias("volume"),
                pl.col("trade_count").sum().alias("trade_count"),
            )
            .drop_nulls("close")
        )
