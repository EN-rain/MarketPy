"""Candlestick pattern detection."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class CandlestickSignal:
    pattern_type: str
    confidence: float
    index: int


class CandlestickPatternDetector:
    def detect(self, frame: pd.DataFrame) -> list[CandlestickSignal]:
        patterns: list[CandlestickSignal] = []
        for idx, row in frame.iterrows():
            body = abs(row["close"] - row["open"])
            candle_range = max(row["high"] - row["low"], 1e-9)
            upper_shadow = row["high"] - max(row["open"], row["close"])
            lower_shadow = min(row["open"], row["close"]) - row["low"]
            if body / candle_range < 0.1:
                patterns.append(CandlestickSignal("doji", 0.8, int(idx)))
            if lower_shadow > body * 2 and upper_shadow < body:
                patterns.append(CandlestickSignal("hammer", 0.75, int(idx)))
            if upper_shadow > body * 2 and lower_shadow < body:
                patterns.append(CandlestickSignal("shooting_star", 0.75, int(idx)))
        if len(frame) >= 2:
            prev = frame.iloc[-2]
            curr = frame.iloc[-1]
            if curr["close"] > curr["open"] and prev["close"] < prev["open"] and curr["close"] >= prev["open"] and curr["open"] <= prev["close"]:
                patterns.append(CandlestickSignal("bullish_engulfing", 0.85, len(frame) - 1))
            if curr["close"] < curr["open"] and prev["close"] > prev["open"] and curr["open"] >= prev["close"] and curr["close"] <= prev["open"]:
                patterns.append(CandlestickSignal("bearish_engulfing", 0.85, len(frame) - 1))
        return patterns
