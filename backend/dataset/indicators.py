"""Technical indicator pipeline with pandas-ta/ta compatible interfaces."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover - dependency guard
    raise RuntimeError("pandas is required for IndicatorPipeline") from exc

try:  # pragma: no cover - optional dependency
    import pandas_ta as _pta  # type: ignore
except Exception:  # pragma: no cover
    _pta = None

try:  # pragma: no cover - optional dependency
    import ta as _ta  # type: ignore
except Exception:  # pragma: no cover
    _ta = None

logger = logging.getLogger(__name__)


class IndicatorLibrary(str, Enum):
    PANDAS_TA = "pandas_ta"
    TA = "ta"
    AUTO = "auto"


DEFAULT_INDICATORS: list[str] = [
    "sma_10",
    "sma_20",
    "sma_50",
    "sma_100",
    "sma_200",
    "ema_8",
    "ema_12",
    "ema_21",
    "ema_26",
    "ema_50",
    "ema_100",
    "wma_20",
    "rsi_7",
    "rsi_14",
    "rsi_21",
    "macd",
    "macd_signal",
    "macd_hist",
    "stoch_k",
    "stoch_d",
    "cci_14",
    "cci_20",
    "williams_r_14",
    "roc_5",
    "roc_12",
    "mom_10",
    "mom_20",
    "bbands_upper",
    "bbands_middle",
    "bbands_lower",
    "bbands_width",
    "atr_14",
    "atr_21",
    "keltner_upper",
    "keltner_middle",
    "keltner_lower",
    "donchian_upper",
    "donchian_middle",
    "donchian_lower",
    "obv",
    "ad",
    "adx_14",
    "vwap",
    "mfi_14",
    "price_change_1h",
    "price_change_4h",
    "price_change_24h",
    "volume_change_1h",
    "volume_change_24h",
    "volatility_12",
    "volatility_48",
    "close_to_high",
    "close_to_low",
    "hl_range",
]


@dataclass(slots=True)
class IndicatorConfig:
    library: IndicatorLibrary = IndicatorLibrary.AUTO
    indicators: list[str] = field(default_factory=lambda: DEFAULT_INDICATORS.copy())
    custom_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    forward_fill_limit: int = 5


class IndicatorPipeline:
    """Computes a broad indicator set for OHLCV dataframes."""

    def __init__(self, config: IndicatorConfig | None = None) -> None:
        self.config = config or IndicatorConfig()

    def get_available_indicators(self) -> list[str]:
        return DEFAULT_INDICATORS.copy()

    def _resolve_library(self) -> IndicatorLibrary:
        if self.config.library != IndicatorLibrary.AUTO:
            return self.config.library
        if _pta is not None:
            return IndicatorLibrary.PANDAS_TA
        if _ta is not None:
            return IndicatorLibrary.TA
        return IndicatorLibrary.AUTO

    @staticmethod
    def _require_columns(df: pd.DataFrame) -> None:
        required = {"open", "high", "low", "close", "volume"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"Missing required OHLCV columns: {missing}")

    @staticmethod
    def _rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        gain_ema = pd.Series(gain, index=series.index).ewm(alpha=1 / period, adjust=False).mean()
        loss_ema = pd.Series(loss, index=series.index).ewm(alpha=1 / period, adjust=False).mean()
        rs = gain_ema / loss_ema.replace(0.0, np.nan)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _wma(series: pd.Series, period: int) -> pd.Series:
        weights = np.arange(1, period + 1, dtype=float)
        return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def _adx(df: pd.DataFrame, period: int) -> pd.Series:
        up = df["high"].diff()
        down = -df["low"].diff()
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        atr = IndicatorPipeline._atr(df, period).replace(0.0, np.nan)
        plus_di = 100.0 * pd.Series(plus_dm, index=df.index).rolling(period).sum() / atr
        minus_di = 100.0 * pd.Series(minus_dm, index=df.index).rolling(period).sum() / atr
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)) * 100.0
        return dx.rolling(period).mean()

    def _compute_manual(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Trend indicators
        for period in (10, 20, 50, 100, 200):
            df[f"sma_{period}"] = close.rolling(period).mean()
        for period in (8, 12, 21, 26, 50, 100):
            df[f"ema_{period}"] = close.ewm(span=period, adjust=False).mean()
        df["wma_20"] = self._wma(close, 20)

        # Momentum indicators
        for period in (7, 14, 21):
            df[f"rsi_{period}"] = self._rsi(close, period)

        ema12 = df["ema_12"]
        ema26 = df["ema_26"]
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        lowest_low = low.rolling(14).min()
        highest_high = high.rolling(14).max()
        stoch_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low).replace(0.0, np.nan)
        df["stoch_k"] = stoch_k
        df["stoch_d"] = stoch_k.rolling(3).mean()

        typical_price = (high + low + close) / 3.0
        tp_mean = typical_price.rolling(20).mean()
        tp_dev = (typical_price - tp_mean).abs().rolling(20).mean().replace(0.0, np.nan)
        df["cci_14"] = (typical_price - typical_price.rolling(14).mean()) / (
            0.015 * (typical_price - typical_price.rolling(14).mean()).abs().rolling(14).mean()
        ).replace(0.0, np.nan)
        df["cci_20"] = (typical_price - tp_mean) / (0.015 * tp_dev)
        df["williams_r_14"] = -100.0 * (highest_high - close) / (
            highest_high - lowest_low
        ).replace(0.0, np.nan)

        for period in (5, 12):
            df[f"roc_{period}"] = close.pct_change(periods=period) * 100.0
        for period in (10, 20):
            df[f"mom_{period}"] = close.diff(periods=period)

        # Volatility
        middle = close.rolling(20).mean()
        std = close.rolling(20).std()
        df["bbands_middle"] = middle
        df["bbands_upper"] = middle + 2.0 * std
        df["bbands_lower"] = middle - 2.0 * std
        df["bbands_width"] = (df["bbands_upper"] - df["bbands_lower"]) / middle.replace(0.0, np.nan)

        df["atr_14"] = self._atr(df, 14)
        df["atr_21"] = self._atr(df, 21)

        keltn_mid = close.ewm(span=20, adjust=False).mean()
        keltn_atr = self._atr(df, 10)
        df["keltner_middle"] = keltn_mid
        df["keltner_upper"] = keltn_mid + 2 * keltn_atr
        df["keltner_lower"] = keltn_mid - 2 * keltn_atr

        donchian_high = high.rolling(20).max()
        donchian_low = low.rolling(20).min()
        df["donchian_upper"] = donchian_high
        df["donchian_lower"] = donchian_low
        df["donchian_middle"] = (donchian_high + donchian_low) / 2.0

        # Volume indicators
        direction = np.sign(close.diff().fillna(0.0))
        df["obv"] = (direction * volume).cumsum()
        money_flow_multiplier = ((close - low) - (high - close)) / (high - low).replace(0.0, np.nan)
        money_flow_volume = money_flow_multiplier.fillna(0.0) * volume
        df["ad"] = money_flow_volume.cumsum()
        df["adx_14"] = self._adx(df, 14)
        cum_vol = volume.cumsum().replace(0.0, np.nan)
        df["vwap"] = ((typical_price * volume).cumsum()) / cum_vol

        money_flow = typical_price * volume
        positive_flow = money_flow.where(typical_price.diff() > 0, 0.0).rolling(14).sum()
        negative_flow = money_flow.where(typical_price.diff() < 0, 0.0).rolling(14).sum()
        ratio = positive_flow / negative_flow.replace(0.0, np.nan)
        df["mfi_14"] = 100.0 - (100.0 / (1.0 + ratio))

        # Custom features
        df["price_change_1h"] = close.pct_change(12)
        df["price_change_4h"] = close.pct_change(48)
        df["price_change_24h"] = close.pct_change(288)
        df["volume_change_1h"] = volume.pct_change(12)
        df["volume_change_24h"] = volume.pct_change(288)
        df["volatility_12"] = close.pct_change().rolling(12).std()
        df["volatility_48"] = close.pct_change().rolling(48).std()
        df["close_to_high"] = close / high.replace(0.0, np.nan)
        df["close_to_low"] = close / low.replace(0.0, np.nan)
        df["hl_range"] = (high - low) / close.replace(0.0, np.nan)

        return df

    def _apply_library_specific(self, df: pd.DataFrame, library: IndicatorLibrary) -> pd.DataFrame:
        if library == IndicatorLibrary.PANDAS_TA and _pta is not None:  # pragma: no cover
            try:
                # Keep manual features as baseline and attach a small set from pandas_ta
                df["pta_rsi_14"] = _pta.rsi(df["close"], length=14)
                macd = _pta.macd(df["close"], fast=12, slow=26, signal=9)
                if macd is not None and not macd.empty:
                    df["pta_macd"] = macd.iloc[:, 0]
                return df
            except Exception as exc:
                logger.warning("pandas_ta computation failed, falling back to manual indicators: %s", exc)
                return df
        if library == IndicatorLibrary.TA and _ta is not None:  # pragma: no cover
            try:
                df["ta_rsi_14"] = _ta.momentum.RSIIndicator(df["close"], window=14).rsi()
                return df
            except Exception as exc:
                logger.warning("ta computation failed, falling back to manual indicators: %s", exc)
                return df
        return df

    def validate_output(self, df: pd.DataFrame) -> bool:
        indicator_cols = [name for name in self.config.indicators if name in df.columns]
        if not indicator_cols:
            return True

        numeric = df[indicator_cols].replace([np.inf, -np.inf], np.nan)
        if numeric.isnull().all(axis=None):
            return False
        recent = numeric.tail(10)
        return not recent.isnull().any(axis=None)

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(df)
        enriched = df.copy()
        enriched = enriched.sort_index()
        enriched = enriched.ffill(limit=self.config.forward_fill_limit)
        if enriched[["open", "high", "low", "close", "volume"]].isnull().any(axis=None):
            logger.warning("Input OHLCV still has missing values after forward fill")

        enriched = self._compute_manual(enriched)
        enriched = self._apply_library_specific(enriched, self._resolve_library())
        enriched.replace([np.inf, -np.inf], np.nan, inplace=True)

        # Keep only requested indicators that exist, while preserving source OHLCV columns.
        keep = ["open", "high", "low", "close", "volume"]
        if "timestamp" in enriched.columns:
            keep.insert(0, "timestamp")
        for name in self.config.indicators:
            if name in enriched.columns:
                keep.append(name)
        keep = list(dict.fromkeys(keep))
        out = enriched[keep]

        if not self.validate_output(out):
            logger.warning("Indicator validation failed: NaN/inf found in recent indicator outputs")
        return out
