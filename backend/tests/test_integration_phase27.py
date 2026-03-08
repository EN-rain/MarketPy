"""Phase 27 integration tests for end-to-end flows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app
from backend.features.computer import FeatureComputer
from backend.features.registry import FeatureDefinition, FeatureRegistry
from backend.features.store import FeatureStore
from backend.features.validator import FeatureValidator
from backend.risk.manager import RiskManager


def test_prediction_and_execution_api_flow() -> None:
    app = create_app(AppConfig(enable_binance_stream=False))
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        status = client.get("/api/status")
        assert status.status_code == 200

        models = client.get("/api/models/registry")
        assert models.status_code == 200
        assert "items" in models.json()


def test_risk_management_integration_flow() -> None:
    manager = RiskManager()
    decision = manager.evaluate_all(
        portfolio_value=100_000.0,
        returns=[0.001, -0.002, 0.0005, 0.0015],
        returns_by_asset={"BTC": [0.001, -0.002], "ETH": [0.0005, 0.0015]},
        position_values={"BTC": 30_000.0, "ETH": 20_000.0},
        maintenance_margin_ratio=0.4,
        current_equity=98_500.0,
        regime="ranging",
        stablecoin_price=1.0,
        contract_metadata={"type": "perpetual"},
        exchange_metadata={"name": "binance"},
        current_price=100.0,
        liquidation_price=70.0,
        price_move_pct_1m=0.01,
        liquidation_volume=1_000_000.0,
        average_liquidation_volume=800_000.0,
        outage_seconds=0.0,
        base_position_size=1000.0,
    )
    assert decision.adjusted_position_size >= 0.0
    assert isinstance(decision.positions.allowed, bool)
    assert decision.portfolio.var_result.var_dollar >= 0.0


def test_feature_store_integration_flow() -> None:
    registry = FeatureRegistry()
    registry.register_feature(
        FeatureDefinition(
            name="close_mean",
            version="1.0.0",
            definition={"source": "market"},
            dependencies=[],
            data_sources=["market"],
            computation_logic="Rolling mean of close",
            compute_fn=lambda frame: float(frame["close"].mean()),
        )
    )
    computer = FeatureComputer(registry=registry)
    store = FeatureStore(registry=registry, computer=computer, validator=FeatureValidator())
    now = datetime.now(UTC)
    market_data = pd.DataFrame(
        {
            "timestamp": [now - timedelta(minutes=2), now - timedelta(minutes=1), now],
            "close": [100.0, 101.0, 102.0],
        }
    )
    features = store.compute_features(now, market_data, ["close_mean"])
    assert features["close_mean"] == 101.0
