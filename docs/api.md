# API Documentation

## REST Endpoints

- `GET /health` and `GET /api/health`: liveness checks.
- `GET /api/status`: runtime mode and service state.
- `POST /api/backtest/run`: execute backtests.
- `GET /api/models/registry`: model registry data.
- `GET /api/models/analytics`: prediction analytics.
- `GET /api/monitoring/dashboard`: monitoring dashboard payload.

## WebSocket

- `GET /ws/live`
  - `subscribe_channels`: subscribes to `predictions`, `risk`, `execution`, `alerts`.
  - `unsubscribe_channels`: unsubscribe by channel.
  - `ping`: heartbeat.

## Authentication and Authorization

- Token endpoint: `POST /api/security/token`.
- Bearer token format: `Authorization: Bearer <token>`.
- RBAC roles: `viewer`, `trader`, `admin`.
  - API key management endpoints require `admin`.

## API Key Management

- `POST /api/security/api-keys`: store exchange API keys encrypted at rest.
- `GET /api/security/api-keys`: list masked key records.

## OpenAPI / Swagger

- OpenAPI JSON: `GET /openapi.json`.
- Swagger UI: `GET /docs`.
- ReDoc: `GET /redoc`.
