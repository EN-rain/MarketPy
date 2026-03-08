"""System integration wiring for end-to-end runtime composition."""

from __future__ import annotations

from dataclasses import dataclass

from backend.execution.advanced_orders import AdvancedOrderEngine
from backend.execution.order_manager import OrderManager
from backend.features.computer import FeatureComputer
from backend.features.registry import FeatureRegistry
from backend.features.store import FeatureStore
from backend.features.validator import FeatureValidator
from backend.ingest.exchanges.manager import ConnectionManager
from backend.ml.inference import Inferencer
from backend.patterns.detector import PatternDetector
from backend.regime.classifier import RegimeClassifier
from backend.risk.manager import RiskManager
from backend.strategies.ai_strategy import AIStrategy


@dataclass(slots=True)
class IntegratedSystem:
    exchange_manager: ConnectionManager
    feature_store: FeatureStore
    inferencer: Inferencer
    pattern_detector: PatternDetector
    regime_classifier: RegimeClassifier
    risk_manager: RiskManager
    order_manager: OrderManager
    advanced_orders: AdvancedOrderEngine
    strategy: AIStrategy


def build_integrated_system() -> IntegratedSystem:
    registry = FeatureRegistry()
    computer = FeatureComputer(registry=registry)
    feature_store = FeatureStore(registry=registry, computer=computer, validator=FeatureValidator())
    order_manager = OrderManager()
    return IntegratedSystem(
        exchange_manager=ConnectionManager(),
        feature_store=feature_store,
        inferencer=Inferencer(),
        pattern_detector=PatternDetector(),
        regime_classifier=RegimeClassifier(),
        risk_manager=RiskManager(),
        order_manager=order_manager,
        advanced_orders=AdvancedOrderEngine(order_manager),
        strategy=AIStrategy(),
    )
