from __future__ import annotations

from backend.system.integration import build_integrated_system


def test_system_component_integration_smoke() -> None:
    system = build_integrated_system()
    assert system.exchange_manager is not None
    assert system.feature_store is not None
    assert system.inferencer is not None
    assert system.pattern_detector is not None
    assert system.regime_classifier is not None
    assert system.risk_manager is not None
    assert system.order_manager is not None
    assert system.advanced_orders is not None
    assert system.strategy is not None
