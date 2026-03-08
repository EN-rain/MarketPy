"""Support and resistance detection."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class SupportResistanceLevels:
    support: float
    resistance: float
    confidence: float


class SupportResistanceDetector:
    def detect_support_resistance(self, highs: pd.Series, lows: pd.Series, volumes: pd.Series | None = None) -> SupportResistanceLevels:
        support = float(lows.min())
        resistance = float(highs.max())
        confidence = 0.5
        if volumes is not None and not volumes.empty:
            confidence = min(float(volumes.iloc[-5:].mean() / max(volumes.mean(), 1e-9)), 1.0)
        return SupportResistanceLevels(support=support, resistance=resistance, confidence=max(0.0, min(confidence, 1.0)))
