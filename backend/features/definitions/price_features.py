"""Core price-based feature definitions."""

from __future__ import annotations

from backend.features.registry import FeatureDefinition, FeatureRegistry


def register_price_features(registry: FeatureRegistry) -> None:
    registry.register_feature(
        FeatureDefinition(
            name="return_1",
            version="1.0.0",
            definition={"window": 1},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="Latest percentage return.",
            compute_fn=lambda df: float(df["close"].pct_change().fillna(0.0).iloc[-1]),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="volatility_5",
            version="1.0.0",
            definition={"window": 5},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="Rolling standard deviation of close returns over 5 bars.",
            compute_fn=lambda df: float(df["close"].pct_change().fillna(0.0).tail(5).std(ddof=0)),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="momentum_5",
            version="1.0.0",
            definition={"window": 5},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="Price momentum over 5 bars.",
            compute_fn=lambda df: float(df["close"].iloc[-1] - df["close"].iloc[max(0, len(df) - 5)]),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="mean_reversion_gap",
            version="1.0.0",
            definition={"window": 5},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="Deviation from 5-bar rolling mean.",
            compute_fn=lambda df: float(df["close"].iloc[-1] - df["close"].tail(5).mean()),
        )
    )
