"""Tests for IndicatorPipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.dataset.indicators import IndicatorConfig, IndicatorPipeline


def test_indicator_pipeline_computes_default_columns() -> None:
    rows = 400
    base = np.linspace(100, 120, rows)
    df = pd.DataFrame(
        {
            "open": base,
            "high": base + 1,
            "low": base - 1,
            "close": base + np.sin(np.linspace(0, 10, rows)),
            "volume": np.linspace(1_000, 2_000, rows),
        }
    )
    pipeline = IndicatorPipeline(IndicatorConfig())
    out = pipeline.compute(df)
    for expected in ("sma_20", "ema_12", "rsi_14", "macd", "bbands_upper", "mfi_14"):
        assert expected in out.columns
