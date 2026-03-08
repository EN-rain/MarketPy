# External Library Rollout Plan

## Success Criteria by Phase

### Phase 1: Exchange + WebSocket + Time Sync
- `ExchangeClient` supports Binance/Coinbase/Kraken interfaces
- Reconnect/backoff and state transitions in `WebSocketManager`
- `TimeSynchronizer` offset is computed and refreshed
- Backward compatibility adapter available for legacy Binance REST calls

### Phase 2: Indicators + Scaling + Importance
- `IndicatorPipeline` computes default multi-category indicator set
- `FeatureScaler` fit/transform/inverse + persistence available
- Feature importance endpoint available: `GET /api/models/{model_id}/feature_importance`

### Phase 3: Paper Trading Strategy + Risk
- Freqtrade-style strategy interface integrated
- Legacy strategy adapter present with deprecation warnings
- Risk limits enforced and exposed via `GET /api/paper-trading/risk-status`

### Phase 4: Vectorized + Fill Quality + Notifications
- Vectorized backtesting available in `/api/backtest/run` via `execution_mode=vectorized`
- `M3_DEPTH` fill model added with `M2` fallback
- Discord notifier supports categories and rate limiting

## Rollback Procedures

### Exchange Layer Rollback
- Keep existing `BinanceClient` and `BinanceRestClient` paths active
- Route ingestion and live feeds back to legacy clients

### Feature Engineering Rollback
- Keep `backend.dataset.features` legacy functions (`compute_rsi`, `compute_macd`)
- Disable `IndicatorPipeline` use in training workflows

### Strategy Rollback
- Disable freqtrade strategy usage and continue legacy `on_bar` only
- Keep `StrategyAdapter` available for compatibility

### Backtesting Rollback
- Set `execution_mode=event_driven`
- Continue using current `SimEngine` path only

### Notification Rollback
- Unset `DISCORD_WEBHOOK_URL` or disable categories via `DISCORD_ENABLED_CATEGORIES`

## Monitoring/Alerting Setup

- Health endpoints:
  - `GET /api/health/exchange-client`
  - `GET /api/health/paper-trading`
  - Existing realtime health endpoints
- Metrics:
  - `GET /api/metrics/tasks`
  - `GET /api/metrics/prometheus`
- Alert recommendations:
  - WebSocket reconnect failures after max attempts
  - Risk limit breach events
  - Discord send failure spikes
