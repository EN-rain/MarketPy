# MarketPy API Documentation

## REST Endpoints
- `GET /api/status`
- `GET /api/portfolio`
- `GET /api/health/connections`
- `GET /api/health/processing`
- `GET /api/health/memory`
- `GET /api/health/rate-limits`
- `GET /api/health/config`
- `GET /api/health/exchange-client`
- `GET /api/health/paper-trading`
- `GET /api/metrics/tasks`
- `GET /api/metrics/prometheus`
- `POST /api/backtest/run`
- `GET /api/models/{model_id}/feature_importance`
- `GET /api/paper-trading/risk-status`
- `GET /api/metrics/market/{coin_id}`
- `GET /api/correlation/bpi`

## Execution Quality APIs (Module-Level)
- Slippage tracking: `backend.app.execution.slippage_tracker.SlippageTracker`
- Latency monitoring: `backend.app.execution.latency_monitor.LatencyMonitor`

## Model Governance APIs (Module-Level)
- Model registry: `backend.app.ml.model_registry.ModelRegistry`
- Drift detector: `backend.app.ml.drift_detector.DriftDetector`
- Feature importance: `backend.app.ml.feature_importance.FeatureImportanceTracker`
- Feature importance methods:
  - Canonical: `heuristic_shap_proxy`, `heuristic_permutation_proxy`, `heuristic_gain_proxy`
  - Legacy aliases accepted for compatibility: `shap`, `permutation`, `gain`

## WebSocket Messages
- Endpoint: `ws://<host>/ws/live`
- Message types:
  - `status_update`: `{ mode, is_running, connected_markets, connected_markets_count }`
  - `market_update`: canonical market payload aligned with `MarketUpdate`

## Core Data Models
- `MarketUpdate`, `OrderBookSnapshot`
- `BacktestResult`
- `AlertCondition`, `TriggeredAlert`
- `RiskLimits`, `AutomatedAction`
- `VaRResult`, `StressResult`, `CorrelationMatrix`
- `SlippageRecord`, `LatencyRecord`
- `ModelVersion`, `DriftMetrics`, `FeatureImportance`
- `ArbitrageOpportunity` metrics note:
  - Preferred metric key: `avg_detection_interval_seconds`
  - Backward-compatible alias: `avg_duration_seconds`
