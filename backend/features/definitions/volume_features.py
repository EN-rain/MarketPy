"""Core volume-based feature definitions."""

from __future__ import annotations

from backend.features.registry import FeatureDefinition, FeatureRegistry


def register_volume_features(registry: FeatureRegistry) -> None:
    registry.register_feature(
        FeatureDefinition(
            name="volume_ratio_5",
            version="1.0.0",
            definition={"window": 5},
            dependencies=["volume"],
            data_sources=["ohlcv"],
            computation_logic="Current volume divided by rolling mean volume.",
            compute_fn=lambda df: float(df["volume"].iloc[-1] / max(df["volume"].tail(5).mean(), 1e-9)),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="volume_momentum_5",
            version="1.0.0",
            definition={"window": 5},
            dependencies=["volume"],
            data_sources=["ohlcv"],
            computation_logic="Volume change over 5 bars.",
            compute_fn=lambda df: float(df["volume"].iloc[-1] - df["volume"].iloc[max(0, len(df) - 5)]),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="vwap_deviation",
            version="1.0.0",
            definition={},
            dependencies=["close", "volume"],
            data_sources=["ohlcv"],
            computation_logic="Distance from session VWAP.",
            compute_fn=lambda df: float(df["close"].iloc[-1] - ((df["close"] * df["volume"]).sum() / max(df["volume"].sum(), 1e-9))),
        )
    )
