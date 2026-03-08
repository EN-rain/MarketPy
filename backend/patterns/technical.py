"""Technical chart pattern detectors."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class DetectedPattern:
    pattern_type: str
    confidence: float
    formation_index: int
    completion_index: int
    key_levels: dict[str, float]


class TechnicalPatternDetector:
    def detect_head_and_shoulders(self, closes: pd.Series) -> list[DetectedPattern]:
        if len(closes) < 7:
            return []
        values = closes.reset_index(drop=True)
        patterns: list[DetectedPattern] = []
        for idx in range(2, len(values) - 2):
            left = values.iloc[idx - 2]
            shoulder_left = values.iloc[idx - 1]
            head = values.iloc[idx]
            shoulder_right = values.iloc[idx + 1]
            right = values.iloc[idx + 2]
            if head > shoulder_left > left and head > shoulder_right > right:
                symmetry = 1.0 - min(abs(shoulder_left - shoulder_right) / max(head, 1e-9), 1.0)
                patterns.append(
                    DetectedPattern(
                        pattern_type="head_and_shoulders",
                        confidence=max(0.0, min(symmetry, 1.0)),
                        formation_index=idx - 2,
                        completion_index=idx + 2,
                        key_levels={"head": float(head), "neckline": float((left + right) / 2)},
                    )
                )
        return patterns

    def detect_triangles(self, highs: pd.Series, lows: pd.Series) -> list[DetectedPattern]:
        if len(highs) < 5 or len(lows) < 5:
            return []
        high_slope = float(highs.iloc[-1] - highs.iloc[0])
        low_slope = float(lows.iloc[-1] - lows.iloc[0])
        pattern_type = None
        if high_slope < 0 < low_slope:
            pattern_type = "symmetrical_triangle"
        elif abs(high_slope) < 1e-9 and low_slope > 0:
            pattern_type = "ascending_triangle"
        elif high_slope < 0 and abs(low_slope) < 1e-9:
            pattern_type = "descending_triangle"
        if pattern_type is None:
            return []
        confidence = 1.0 - min(abs(high_slope + low_slope) / max(abs(high_slope) + abs(low_slope), 1e-9), 1.0)
        return [
            DetectedPattern(
                pattern_type=pattern_type,
                confidence=max(0.0, min(confidence, 1.0)),
                formation_index=0,
                completion_index=len(highs) - 1,
                key_levels={"upper": float(highs.iloc[-1]), "lower": float(lows.iloc[-1])},
            )
        ]

    def detect_double_top_bottom(self, closes: pd.Series) -> list[DetectedPattern]:
        if len(closes) < 5:
            return []
        values = closes.reset_index(drop=True)
        patterns: list[DetectedPattern] = []
        if abs(values.iloc[1] - values.iloc[3]) < max(values.iloc[2] * 0.02, 1e-9) and values.iloc[2] < values.iloc[1]:
            patterns.append(DetectedPattern("double_top", 0.8, 0, 4, {"resistance": float(max(values.iloc[1], values.iloc[3]))}))
        if abs(values.iloc[1] - values.iloc[3]) < max(values.iloc[2] * 0.02, 1e-9) and values.iloc[2] > values.iloc[1]:
            patterns.append(DetectedPattern("double_bottom", 0.8, 0, 4, {"support": float(min(values.iloc[1], values.iloc[3]))}))
        return patterns

    def detect_cup_and_handle(self, closes: pd.Series) -> list[DetectedPattern]:
        if len(closes) < 6:
            return []
        values = closes.reset_index(drop=True)
        if values.iloc[0] > values.iloc[2] < values.iloc[4] and values.iloc[5] < values.iloc[4]:
            return [DetectedPattern("cup_and_handle", 0.75, 0, len(values) - 1, {"breakout": float(values.iloc[4])})]
        return []

    def detect_flags_and_pennants(self, closes: pd.Series) -> list[DetectedPattern]:
        if len(closes) < 5:
            return []
        change = float(closes.iloc[-1] - closes.iloc[0])
        consolidation = float(closes.iloc[-3:].std(ddof=0))
        if abs(change) > max(consolidation * 2, 1e-9):
            pattern_type = "bull_flag" if change > 0 else "bear_flag"
            return [DetectedPattern(pattern_type, 0.7, 0, len(closes) - 1, {"pole_change": change})]
        return []
