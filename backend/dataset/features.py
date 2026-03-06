"""Feature engineering pipeline for ML models.

Computes features from candle data using Polars:
- Lag returns (1m, 5m, 15m, 60m)
- Rolling volatility (1h, 4h)
- Spread features
- Time features (time_to_close, hour_of_day)
- Labels: future log returns at 1h, 6h, 1d horizons
"""

from __future__ import annotations

import logging
import warnings

import polars as pl

EPSILON = 1e-6
logger = logging.getLogger(__name__)


def _safe_price_expr(col: str) -> pl.Expr:
    return pl.col(col).clip(EPSILON, None)


def add_lag_returns(df: pl.DataFrame, lags: list[int] | None = None) -> pl.DataFrame:
    """Add lagged return columns.

    Args:
        df: DataFrame with 'mid' column.
        lags: List of bar lags (e.g., [1, 5, 15, 60]).
    """
    if lags is None:
        lags = [1, 5, 15, 60]

    for lag in lags:
        col_name = f"ret_{lag}"
        df = df.with_columns(
            (_safe_price_expr("mid").log() - _safe_price_expr("mid").shift(lag).log()).alias(
                col_name
            )
        )
    return df


def add_rolling_volatility(df: pl.DataFrame, windows: list[int] | None = None) -> pl.DataFrame:
    """Add rolling volatility (std of log returns) columns.

    Args:
        df: DataFrame with 'mid' column.
        windows: Rolling window sizes in bars.
    """
    if windows is None:
        windows = [12, 48]  # 1h and 4h at 5m bars

    # First ensure we have 1-bar returns
    if "ret_1" not in df.columns:
        df = df.with_columns(
            (_safe_price_expr("mid").log() - _safe_price_expr("mid").shift(1).log()).alias(
                "ret_1"
            )
        )

    for window in windows:
        col_name = f"vol_{window}"
        df = df.with_columns(pl.col("ret_1").rolling_std(window_size=window).alias(col_name))
    return df


def add_spread_features(df: pl.DataFrame, window: int = 12) -> pl.DataFrame:
    """Add spread-related features.

    Args:
        df: DataFrame with 'spread' column.
        window: Rolling window for average spread.
    """
    df = df.with_columns(
        [
            pl.col("spread").alias("spread_current"),
            pl.col("spread").rolling_mean(window_size=window).alias(f"spread_avg_{window}"),
            (pl.col("spread") / pl.col("mid")).alias("spread_pct"),
        ]
    )
    return df


def add_time_features(df: pl.DataFrame, end_timestamp: str | None = None) -> pl.DataFrame:
    """Add time-based features.

    Args:
        df: DataFrame with 'timestamp' column.
        end_timestamp: Market close timestamp (ISO format).
    """
    df = df.with_columns(
        [
            pl.col("timestamp").dt.hour().alias("hour_of_day"),
            pl.col("timestamp").dt.weekday().alias("day_of_week"),
        ]
    )

    if end_timestamp:
        end_dt = pl.lit(end_timestamp).str.to_datetime()
        df = df.with_columns(
            (end_dt - pl.col("timestamp")).dt.total_seconds().alias("time_to_close")
        )
    return df


def add_labels(
    df: pl.DataFrame,
    horizons: dict[str, int] | None = None,
    embargo_bars: int | None = None,
) -> pl.DataFrame:
    """Add future log-return labels.

    Args:
        df: DataFrame with 'mid' column.
        horizons: Dict of {label_name: bars_ahead}.
            Default: 1h=12, 6h=72, 1d=288 (at 5m bars).
    """
    if horizons is None:
        horizons = {"y_1h": 12, "y_6h": 72, "y_1d": 288}

    if embargo_bars is None:
        embargo_bars = max(horizons.values())

    for name, bars in horizons.items():
        df = df.with_columns(
            (
                _safe_price_expr("mid").shift(-(bars + embargo_bars)).log()
                - _safe_price_expr("mid").shift(-embargo_bars).log()
            ).alias(name)
        )
    return df


def build_feature_matrix(
    df: pl.DataFrame,
    end_timestamp: str | None = None,
    lags: list[int] | None = None,
    vol_windows: list[int] | None = None,
    spread_window: int = 12,
    horizons: dict[str, int] | None = None,
    embargo_bars: int | None = None,
) -> pl.DataFrame:
    """Build the complete feature matrix for ML training.

    Applies all feature engineering steps and removes rows with NaN
    (from lookback/lookahead requirements).

    Returns:
        DataFrame with features and labels, ready for train/test split.
    """
    df = add_lag_returns(df, lags)
    df = add_rolling_volatility(df, vol_windows)
    df = add_spread_features(df, spread_window)
    df = add_time_features(df, end_timestamp)
    df = add_labels(df, horizons, embargo_bars=embargo_bars)

    # Drop rows with any nulls (from lookback/lookahead)
    before = len(df)
    df = df.drop_nulls()
    dropped = before - len(df)
    if before > 0 and dropped > 0:
        dropped_pct = (dropped / before) * 100
        if dropped_pct > 10:
            logger.warning(
                f"[feature-build] dropped {dropped}/{before} rows ({dropped_pct:.1f}%) due to nulls"
            )

    return df


def get_feature_columns(df: pl.DataFrame) -> list[str]:
    """Return the list of feature column names (excludes labels and metadata)."""
    exclude = {
        "timestamp",
        "token_id",
        "open",
        "high",
        "low",
        "close",
        "mid",
        "bid",
        "ask",
        "spread",
        "volume",
        "trade_count",
        "y_1h",
        "y_6h",
        "y_1d",
        "spread_current",
    }
    return [c for c in df.columns if c not in exclude]


def compute_rsi(close: pl.Series, period: int = 14) -> pl.Series:
    """Deprecated RSI helper kept for backward compatibility."""
    warnings.warn(
        "compute_rsi is deprecated; migrate to backend.dataset.indicators.IndicatorPipeline",
        DeprecationWarning,
        stacklevel=2,
    )
    values = [float(v) for v in close.to_list()]
    if len(values) < 2:
        return pl.Series(f"rsi_{period}", [50.0] * len(values))

    gains: list[float] = [0.0]
    losses: list[float] = [0.0]
    for prev, cur in zip(values, values[1:], strict=False):
        diff = cur - prev
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    rsi_values: list[float] = []
    for idx in range(len(values)):
        start = max(0, idx - period + 1)
        avg_gain = sum(gains[start : idx + 1]) / (idx - start + 1)
        avg_loss = sum(losses[start : idx + 1]) / (idx - start + 1)
        if avg_loss == 0:
            rsi_values.append(100.0)
            continue
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))
    return pl.Series(f"rsi_{period}", rsi_values)


def compute_macd(
    close: pl.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Deprecated MACD helper kept for backward compatibility."""
    warnings.warn(
        "compute_macd is deprecated; migrate to backend.dataset.indicators.IndicatorPipeline",
        DeprecationWarning,
        stacklevel=2,
    )
    values = close.to_list()
    alpha_fast = 2 / (fast_period + 1)
    alpha_slow = 2 / (slow_period + 1)
    alpha_signal = 2 / (signal_period + 1)

    fast_ema: list[float] = []
    slow_ema: list[float] = []
    macd_values: list[float] = []
    signal_values: list[float] = []

    for i, value in enumerate(values):
        if i == 0:
            fast_ema.append(float(value))
            slow_ema.append(float(value))
            macd_values.append(0.0)
            signal_values.append(0.0)
            continue
        fast_ema.append(alpha_fast * float(value) + (1 - alpha_fast) * fast_ema[-1])
        slow_ema.append(alpha_slow * float(value) + (1 - alpha_slow) * slow_ema[-1])
        macd_now = fast_ema[-1] - slow_ema[-1]
        macd_values.append(macd_now)
        signal_now = alpha_signal * macd_now + (1 - alpha_signal) * signal_values[-1]
        signal_values.append(signal_now)

    hist_values = [m - s for m, s in zip(macd_values, signal_values, strict=False)]
    return (
        pl.Series("macd", macd_values),
        pl.Series("macd_signal", signal_values),
        pl.Series("macd_hist", hist_values),
    )
