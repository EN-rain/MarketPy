"""Market microstructure feature definitions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.features.registry import FeatureDefinition, FeatureRegistry


def order_book_imbalance(best_bid_size: float, best_ask_size: float) -> float:
    denom = max(best_bid_size + best_ask_size, 1e-9)
    return float((best_bid_size - best_ask_size) / denom)


def spread_bps(best_bid: float, best_ask: float) -> float:
    mid = (best_bid + best_ask) / 2.0
    if mid <= 0:
        return 0.0
    return float(((best_ask - best_bid) / mid) * 10_000.0)


def depth_ratio(bid_depth: float, ask_depth: float) -> float:
    denom = max(ask_depth, 1e-9)
    return float(bid_depth / denom)


def vpin(volume_buckets: pd.Series, signed_volume: pd.Series) -> float:
    if volume_buckets.empty:
        return 0.0
    total_volume = float(np.sum(np.abs(volume_buckets.to_numpy(dtype=float))))
    if total_volume <= 0:
        return 0.0
    imbalance = float(np.sum(np.abs(signed_volume.to_numpy(dtype=float))))
    return float(min(max(imbalance / total_volume, 0.0), 1.0))


def register_microstructure_features(registry: FeatureRegistry) -> None:
    registry.register_feature(
        FeatureDefinition(
            name="order_book_imbalance",
            version="1.0.0",
            definition={"source": "order_book"},
            dependencies=[],
            data_sources=["order_book"],
            computation_logic="(bid_size - ask_size)/(bid_size + ask_size)",
            compute_fn=lambda frame: order_book_imbalance(
                float(frame["bid_size"].iloc[-1]),
                float(frame["ask_size"].iloc[-1]),
            ),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="spread_bps",
            version="1.0.0",
            definition={"source": "order_book"},
            dependencies=[],
            data_sources=["order_book"],
            computation_logic="((ask-bid)/mid)*10000",
            compute_fn=lambda frame: spread_bps(float(frame["bid"].iloc[-1]), float(frame["ask"].iloc[-1])),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="depth_ratio",
            version="1.0.0",
            definition={"source": "order_book_depth"},
            dependencies=[],
            data_sources=["order_book_depth"],
            computation_logic="bid_depth / ask_depth",
            compute_fn=lambda frame: depth_ratio(float(frame["bid_depth"].iloc[-1]), float(frame["ask_depth"].iloc[-1])),
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="vpin",
            version="1.0.0",
            definition={"source": "trades"},
            dependencies=[],
            data_sources=["trades"],
            computation_logic="|signed_volume|/volume bucket sum",
            compute_fn=lambda frame: vpin(frame["volume"], frame["signed_volume"]),
        )
    )
