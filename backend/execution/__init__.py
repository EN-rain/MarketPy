"""Execution engine package."""

from backend.execution.arbitrage import (
    ArbitrageDetector,
    ArbitrageExecutionResult,
    ArbitrageExecutor,
    TriangularOpportunity,
)
from backend.execution.analyzer import ExecutionAnalysisRecord, ExecutionAnalyzer
from backend.execution.advanced_orders import (
    AdvancedOrderEngine,
    BracketOrder,
    IcebergOrderState,
    ScheduledSlice,
)
from backend.execution.derivatives import DerivativesEngine, OptionQuote, PerpetualSnapshot
from backend.execution.order_manager import OrderManager, OrderRecord, OrderStatus
from backend.execution.quality_monitor import ExecutionQualityMonitor, ExecutionQualitySummary
from backend.execution.router import RouteDecision, SmartOrderRouter
from backend.execution.tca import TCAAnalyzer, TCAResult

__all__ = [
    "ArbitrageDetector",
    "ArbitrageExecutionResult",
    "ArbitrageExecutor",
    "AdvancedOrderEngine",
    "BracketOrder",
    "DerivativesEngine",
    "ExecutionAnalysisRecord",
    "ExecutionAnalyzer",
    "ExecutionQualityMonitor",
    "ExecutionQualitySummary",
    "IcebergOrderState",
    "OptionQuote",
    "OrderManager",
    "OrderRecord",
    "OrderStatus",
    "PerpetualSnapshot",
    "RouteDecision",
    "ScheduledSlice",
    "SmartOrderRouter",
    "TCAAnalyzer",
    "TCAResult",
    "TriangularOpportunity",
]
