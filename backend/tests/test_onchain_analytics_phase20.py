"""Phase 20 on-chain analytics tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from backend.features.definitions.onchain_features import register_onchain_features
from backend.features.registry import FeatureRegistry
from backend.ingest.alternative_data.exchange_flow import ExchangeFlowAnalyzer
from backend.ingest.alternative_data.miner_behavior import MinerBehaviorAnalyzer
from backend.ingest.alternative_data.whale_tracker import WhaleTracker, WhaleTransfer


def test_whale_tracker_exchange_flow_and_miner_behavior() -> None:
    tracker = WhaleTracker()
    now = datetime(2026, 3, 7, tzinfo=UTC)
    flagged = tracker.monitor_large_movements(
        [
            WhaleTransfer("w1", "BTCUSDT", 2_000_000, "in", now),
            WhaleTransfer("w2", "BTCUSDT", 7_000_000, "out", now + timedelta(minutes=1)),
            WhaleTransfer("w3", "BTCUSDT", 200_000, "in", now + timedelta(minutes=2)),
        ]
    )
    flow = tracker.accumulation_distribution("BTCUSDT")
    alerts = tracker.generate_alerts("BTCUSDT")

    assert len(flagged) == 2
    assert flow["inflow_usd"] == 2_000_000
    assert flow["outflow_usd"] == 7_000_000
    assert alerts

    frame = pd.DataFrame(
        {
            "close": [100, 99, 98, 97, 96],
            "exchange_inflow": [5, 6, 7, 8, 9],
            "exchange_outflow": [3, 3, 3, 3, 3],
            "miner_balance": [1000, 995, 990, 980, 970],
            "hash_rate_eh_s": [200, 198, 197, 195, 194],
        }
    )
    exchange_snapshot = ExchangeFlowAnalyzer().analyze("BTCUSDT", frame)
    miner_snapshot = MinerBehaviorAnalyzer().analyze("BTCUSDT", frame)
    assert exchange_snapshot.netflow > 0
    assert -1.0 <= exchange_snapshot.price_correlation <= 1.0
    assert miner_snapshot.selling_pressure > 0
    assert -1.0 <= miner_snapshot.hashrate_correlation <= 1.0


def test_onchain_features_registered_into_feature_store_registry() -> None:
    registry = FeatureRegistry()
    names = register_onchain_features(registry)

    assert set(names) == {"onchain_whale_flow", "onchain_exchange_netflow", "onchain_miner_pressure"}
    for name in names:
        metadata = registry.metadata(name)
        assert "onchain_metrics" in metadata["data_sources"]
