"""Feature computation for market regime classification."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class RegimeFeatureComputer:
    history_window: int = 90

    def compute(self, frame: pd.DataFrame) -> dict[str, float]:
        ordered = frame.sort_values("timestamp").reset_index(drop=True)
        close = ordered["close"].to_numpy(dtype=float)
        volume = ordered["volume"].to_numpy(dtype=float)
        spread = ordered.get("spread", pd.Series(np.zeros(len(ordered)))).to_numpy(dtype=float)
        depth = ordered.get("order_book_depth", pd.Series(np.ones(len(ordered)))).to_numpy(dtype=float)

        returns = np.diff(np.log(np.clip(close, 1e-9, None)))
        x = np.arange(len(close), dtype=float)
        slope = float(np.polyfit(x, close, 1)[0]) if len(close) >= 2 else 0.0
        adx_proxy = float(min(100.0, abs(slope) / max(np.mean(close), 1e-9) * 10_000))
        volatility = float(np.std(returns[-24:])) if len(returns) >= 2 else 0.0
        vol_history = [float(np.std(returns[max(0, i - 24): i + 1])) for i in range(len(returns)) if i >= 1]
        vol_percentile = 0.0
        if vol_history:
            vol_percentile = float(sum(value <= volatility for value in vol_history) / len(vol_history))
        volume_profile = float(volume[-24:].mean() / max(volume.mean(), 1e-9))
        correlation_feature = float(np.corrcoef(close[-30:], volume[-30:])[0, 1]) if len(close) >= 30 else 0.0
        if not math.isfinite(correlation_feature):
            correlation_feature = 0.0
        liquidity = float((1.0 / max(spread[-1], 1e-6)) * depth[-1])

        return {
            "trend_strength": adx_proxy,
            "linear_regression_slope": slope,
            "volatility_percentile": vol_percentile,
            "volume_profile": volume_profile,
            "average_correlation": correlation_feature,
            "liquidity_score": liquidity,
            "spread": float(spread[-1]) if len(spread) else 0.0,
            "order_book_depth": float(depth[-1]) if len(depth) else 0.0,
        }
