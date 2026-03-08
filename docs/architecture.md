# Architecture Documentation

## High-Level Components

- Ingestion: exchange adapters, alternative-data collectors, and recorder pipeline.
- Feature Layer: feature registry, computation engine, validation, and cache.
- ML Layer: training, inference, drift detection, retraining, explainability.
- Strategy Layer: momentum, mean reversion, AI strategy, pattern strategy, regime-adaptive strategy.
- Risk and Execution: unified risk manager, order manager, advanced order engine, TCA.
- API Layer: FastAPI routers, websocket stream, monitoring and security middleware.

## Data Flow

1. Market and alternative data are ingested and normalized.
2. Features are computed and validated with point-in-time correctness.
3. Inference produces predictions and confidence.
4. Strategy and risk layers produce and gate orders.
5. Execution records fills, costs, and quality metrics.
6. Monitoring exports health, alerts, and performance dashboards.

## Deployment Architecture

- Backend API deployment with horizontal scaling.
- Worker deployments for training, drift detection, and ingestion.
- Stateful backing services: PostgreSQL, Redis, InfluxDB.
- Ingress with TLS termination and HTTPS enforcement.
- Monitoring stack: Prometheus, Alertmanager, Grafana.
- Logging stack: Elasticsearch, Fluent Bit, Kibana.
