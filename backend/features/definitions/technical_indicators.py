"""Technical indicator feature definitions."""

from __future__ import annotations

from backend.features.registry import FeatureDefinition, FeatureRegistry


def _rsi(series, period: int = 14) -> float:
    delta = series.diff().fillna(0.0)
    gains = delta.clip(lower=0).tail(period)
    losses = (-delta.clip(upper=0)).tail(period)
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def register_technical_indicator_features(registry: FeatureRegistry) -> None:
    registry.register_feature(
        FeatureDefinition(
            name="rsi_14",
            version="1.0.0",
            definition={"period": 14},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="14-period RSI.",
            compute_fn=lambda df: _rsi(df["close"], 14),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="macd_line",
            version="1.0.0",
            definition={"fast": 12, "slow": 26},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="EMA(12) - EMA(26).",
            compute_fn=lambda df: float(df["close"].ewm(span=12, adjust=False).mean().iloc[-1] - df["close"].ewm(span=26, adjust=False).mean().iloc[-1]),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="bollinger_band_width",
            version="1.0.0",
            definition={"window": 20},
            dependencies=["close"],
            data_sources=["ohlcv"],
            computation_logic="Normalized Bollinger band width.",
            compute_fn=lambda df: float((4 * df["close"].tail(20).std(ddof=0)) / max(df["close"].tail(20).mean(), 1e-9)),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="atr_14",
            version="1.0.0",
            definition={"period": 14},
            dependencies=["high", "low", "close"],
            data_sources=["ohlcv"],
            computation_logic="Average true range over 14 bars.",
            compute_fn=lambda df: float((df["high"].tail(14) - df["low"].tail(14)).mean()),
        )
    )
