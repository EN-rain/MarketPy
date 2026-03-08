"""Pattern-derived feature generation."""

from __future__ import annotations

from datetime import datetime

from backend.features.registry import FeatureDefinition, FeatureRegistry
from backend.patterns.technical import DetectedPattern


def generate_pattern_features(pattern: DetectedPattern, current_price: float, now_index: int) -> dict[str, float | str]:
    price_anchor = next(iter(pattern.key_levels.values())) if pattern.key_levels else current_price
    return {
        "pattern_type": pattern.pattern_type,
        "confidence": pattern.confidence,
        "time_since_formation": float(max(now_index - pattern.completion_index, 0)),
        "price_distance_from_key_levels": float(current_price - price_anchor),
    }


def register_pattern_features(registry: FeatureRegistry) -> None:
    registry.register_feature(
        FeatureDefinition(
            name="pattern_confidence",
            version="1.0.0",
            definition={"source": "patterns"},
            dependencies=["pattern_detection"],
            data_sources=["patterns"],
            computation_logic="Confidence score of most recent detected pattern.",
        )
    )
