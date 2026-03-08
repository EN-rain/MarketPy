"""High-level pattern detection facade."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.patterns.candlestick import CandlestickPatternDetector
from backend.patterns.features import generate_pattern_features
from backend.patterns.support_resistance import SupportResistanceDetector
from backend.patterns.technical import DetectedPattern, TechnicalPatternDetector


class PatternDetector:
    def __init__(
        self,
        technical: TechnicalPatternDetector | None = None,
        support_resistance: SupportResistanceDetector | None = None,
        candlestick: CandlestickPatternDetector | None = None,
        storage_path: str | Path | None = None,
    ) -> None:
        self.technical = technical or TechnicalPatternDetector()
        self.support_resistance = support_resistance or SupportResistanceDetector()
        self.candlestick = candlestick or CandlestickPatternDetector()
        self.storage_path = Path(storage_path) if storage_path else None

    def detect_patterns(self, frame: pd.DataFrame) -> list[dict[str, object]]:
        closes = frame["close"]
        highs = frame["high"]
        lows = frame["low"]
        volumes = frame["volume"] if "volume" in frame else None
        patterns: list[dict[str, object]] = []
        for pattern in self.technical.detect_head_and_shoulders(closes):
            patterns.append({"pattern": pattern, "features": generate_pattern_features(pattern, float(closes.iloc[-1]), len(frame) - 1)})
        for pattern in self.technical.detect_triangles(highs.tail(5), lows.tail(5)):
            patterns.append({"pattern": pattern, "features": generate_pattern_features(pattern, float(closes.iloc[-1]), len(frame) - 1)})
        for pattern in self.technical.detect_double_top_bottom(closes.tail(5)):
            patterns.append({"pattern": pattern, "features": generate_pattern_features(pattern, float(closes.iloc[-1]), len(frame) - 1)})
        for pattern in self.technical.detect_cup_and_handle(closes.tail(6)):
            patterns.append({"pattern": pattern, "features": generate_pattern_features(pattern, float(closes.iloc[-1]), len(frame) - 1)})
        for pattern in self.technical.detect_flags_and_pennants(closes.tail(5)):
            patterns.append({"pattern": pattern, "features": generate_pattern_features(pattern, float(closes.iloc[-1]), len(frame) - 1)})

        sr = self.support_resistance.detect_support_resistance(highs, lows, volumes)
        patterns.append({"pattern": {"pattern_type": "support_resistance", "support": sr.support, "resistance": sr.resistance, "confidence": sr.confidence}, "features": {"pattern_type": "support_resistance", "confidence": sr.confidence}})
        for signal in self.candlestick.detect(frame):
            patterns.append({"pattern": {"pattern_type": signal.pattern_type, "confidence": signal.confidence, "index": signal.index}, "features": {"pattern_type": signal.pattern_type, "confidence": signal.confidence}})

        if self.storage_path is not None:
            serializable = []
            for item in patterns:
                pattern = item["pattern"]
                if isinstance(pattern, DetectedPattern):
                    pattern_payload = {
                        "pattern_type": pattern.pattern_type,
                        "confidence": pattern.confidence,
                        "formation_index": pattern.formation_index,
                        "completion_index": pattern.completion_index,
                        "key_levels": pattern.key_levels,
                    }
                else:
                    pattern_payload = pattern
                serializable.append({"pattern": pattern_payload, "features": item["features"]})
            self.storage_path.write_text(json.dumps(serializable, ensure_ascii=True), encoding="utf-8")
        return patterns
