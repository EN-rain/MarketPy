"""On-chain feature definitions integrated into the feature store."""

from __future__ import annotations

import pandas as pd

from backend.features.registry import FeatureDefinition, FeatureRegistry


def _latest(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").fillna(0.0).iloc[-1])


def register_onchain_features(registry: FeatureRegistry) -> list[str]:
    definitions = [
        FeatureDefinition(
            name="onchain_whale_flow",
            version="1.0.0",
            definition={"description": "Net whale transfer pressure"},
            dependencies=[],
            data_sources=["onchain_metrics"],
            computation_logic="whale_transfers - exchange_inflow",
            compute_fn=lambda frame: _latest(frame.get("whale_transfers", pd.Series(dtype=float)))
            - _latest(frame.get("exchange_inflow", pd.Series(dtype=float))),
        ),
        FeatureDefinition(
            name="onchain_exchange_netflow",
            version="1.0.0",
            definition={"description": "Exchange inflow minus outflow"},
            dependencies=[],
            data_sources=["onchain_metrics"],
            computation_logic="exchange_inflow - exchange_outflow",
            compute_fn=lambda frame: _latest(frame.get("exchange_inflow", pd.Series(dtype=float)))
            - _latest(frame.get("exchange_outflow", pd.Series(dtype=float))),
        ),
        FeatureDefinition(
            name="onchain_miner_pressure",
            version="1.0.0",
            definition={"description": "Negative miner reserve change"},
            dependencies=[],
            data_sources=["onchain_metrics"],
            computation_logic="abs(min(0, miner_reserve_change))",
            compute_fn=lambda frame: abs(
                min(_latest(frame.get("miner_reserve_change", pd.Series(dtype=float))), 0.0)
            ),
        ),
    ]
    for definition in definitions:
        registry.register_feature(definition)
    return [item.name for item in definitions]


def onchain_feature_names_for_ml() -> list[str]:
    return [
        "onchain_whale_flow",
        "onchain_exchange_netflow",
        "onchain_miner_pressure",
    ]
