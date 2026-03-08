"""Phase 27 performance tests for latency targets."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pandas as pd

from backend.execution.order_manager import OrderManager
from backend.features.computer import FeatureComputer
from backend.features.registry import FeatureDefinition, FeatureRegistry
from backend.ml.inference import Inferencer
from backend.risk.manager import RiskManager


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return ordered[index]


def test_feature_computation_latency_target() -> None:
    registry = FeatureRegistry()
    registry.register_feature(
        FeatureDefinition(
            name="feature_close_mean",
            version="1.0.0",
            definition={},
            dependencies=[],
            data_sources=["market"],
            computation_logic="mean close",
            compute_fn=lambda frame: float(frame["close"].mean()),
        )
    )
    computer = FeatureComputer(registry)
    now = datetime.now(UTC)
    data = pd.DataFrame(
        {
            "timestamp": [now - timedelta(seconds=index) for index in range(120)],
            "close": [100.0 + index * 0.01 for index in range(120)],
        }
    )
    latencies_ms: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        computer.compute_features(now, data, ["feature_close_mean"])
        latencies_ms.append((time.perf_counter() - start) * 1000)
    assert _p95(latencies_ms) < 50.0


def test_inference_and_order_risk_latency_targets() -> None:
    inferencer = Inferencer()
    manager = OrderManager()
    risk = RiskManager()

    inference_latencies: list[float] = []
    order_latencies: list[float] = []
    risk_latencies: list[float] = []

    # Warm-up to avoid model initialization skew in latency samples.
    inferencer.predict(
        {
            "mid": 100.0,
            "spread": 0.1,
            "ret_1": 0.001,
            "vol_12": 0.01,
            "hour_of_day": 10.0,
            "day_of_week": 2.0,
        },
        current_mid=100.0,
    )

    for _ in range(20):
        start = time.perf_counter()
        _ = inferencer.predict(
            {
                "mid": 100.0,
                "spread": 0.1,
                "ret_1": 0.001,
                "vol_12": 0.01,
                "hour_of_day": 10.0,
                "day_of_week": 2.0,
            },
            current_mid=100.0,
        )
        inference_latencies.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = manager.place_order(market_id="BTCUSDT", side="buy", size=1.0, order_type="market")
        order_latencies.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = risk.adjust_position_size(
            base_position_size=100.0,
            regime="ranging",
            margin_ratio=0.5,
            drawdown=0.01,
            portfolio_value=10000.0,
            edge=0.01,
            volatility=0.02,
            confidence=0.8,
        )
        risk_latencies.append((time.perf_counter() - start) * 1000)

    # Keep this threshold practical across CI hosts while still catching regressions.
    assert _p95(inference_latencies) < 1000.0
    assert _p95(order_latencies) < 200.0
    assert _p95(risk_latencies) < 10.0
