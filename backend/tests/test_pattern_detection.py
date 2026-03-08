from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.features.registry import FeatureRegistry
from backend.patterns.candlestick import CandlestickPatternDetector
from backend.patterns.detector import PatternDetector
from backend.patterns.features import register_pattern_features
from backend.patterns.support_resistance import SupportResistanceDetector
from backend.patterns.technical import TechnicalPatternDetector


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100, 101, 103, 101, 100, 102, 101],
            "high": [101, 104, 108, 104, 102, 103, 102],
            "low": [99, 100, 102, 100, 99, 100, 99],
            "close": [100, 103, 107, 103, 100, 101, 100],
            "volume": [10, 12, 16, 14, 11, 10, 9],
        }
    )


def test_technical_pattern_detector_finds_expected_shapes() -> None:
    detector = TechnicalPatternDetector()
    frame = _frame()

    hs = detector.detect_head_and_shoulders(frame["close"])
    triangle = detector.detect_triangles(pd.Series([10, 10, 10, 10, 10]), pd.Series([1, 2, 3, 4, 5]))
    flags = detector.detect_flags_and_pennants(pd.Series([100, 110, 112, 111, 113]))

    assert hs
    assert triangle and triangle[0].pattern_type == "ascending_triangle"
    assert flags
    assert all(0.0 <= pattern.confidence <= 1.0 for pattern in hs + triangle + flags)


def test_support_resistance_and_candlestick_detectors_work() -> None:
    sr = SupportResistanceDetector().detect_support_resistance(pd.Series([5, 6, 7]), pd.Series([1, 2, 3]), pd.Series([10, 12, 14]))
    candles = CandlestickPatternDetector().detect(
        pd.DataFrame(
            {
                "open": [10, 9],
                "high": [11, 11],
                "low": [8, 8],
                "close": [9, 10.5],
            }
        )
    )

    assert sr.support == 1.0
    assert sr.resistance == 7.0
    assert 0.0 <= sr.confidence <= 1.0
    assert candles


def test_pattern_detector_persists_and_generates_features(tmp_path: Path) -> None:
    frame = _frame()
    path = tmp_path / "patterns.json"
    detector = PatternDetector(storage_path=path)

    results = detector.detect_patterns(frame)

    assert results
    assert path.exists()
    assert any("features" in item for item in results)


def test_pattern_features_can_be_registered() -> None:
    registry = FeatureRegistry()
    register_pattern_features(registry)
    assert registry.get_feature("pattern_confidence").version == "1.0.0"
