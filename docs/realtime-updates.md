# Enhanced Realtime Updates

## Overview

This project now includes:

- Update prioritization (`CRITICAL` vs `NON_CRITICAL`)
- Message batching for non-critical updates
- Per-client token-bucket rate limiting
- Slow-client backpressure handling
- Health/metrics endpoints
- Adaptive per-market signal cooldown in paper trading
- Bounded candle-memory management with retention policies

## API Endpoints

- `GET /api/health/connections`
- `GET /api/health/processing`
- `GET /api/health/memory`
- `GET /api/health/rate-limits`
- `GET /api/health/config`
- `GET /api/cooldown/{market_id}`

## Configuration

Default config file: `config/realtime_updates.json`.

You can override values via environment variables:

- `REALTIME_BATCH_WINDOW_MS`
- `REALTIME_MAX_BATCH_SIZE`
- `REALTIME_MAX_MESSAGES_PER_SECOND`
- `REALTIME_BURST_SIZE`
- `REALTIME_PRICE_CHANGE_THRESHOLD`
- `REALTIME_VOLUME_SPIKE_MULTIPLIER`
- `REALTIME_MAX_CANDLES_PER_MARKET`
- `REALTIME_RETENTION_SECONDS`
- `REALTIME_SEND_BUFFER_THRESHOLD`
- `REALTIME_SLOW_CLIENT_TIMEOUT`
- `REALTIME_WORKER_POOL_SIZE`
- `REALTIME_MIN_SIGNAL_COOLDOWN_SECONDS`
- `REALTIME_MAX_SIGNAL_COOLDOWN_SECONDS`
- `REALTIME_WS_CONNECTED_POLL_INTERVAL_MS`
- `REALTIME_WS_DISCONNECTED_POLL_INTERVAL_MS`
- `REALTIME_REST_BACKOFF_MULTIPLIER`
- `REALTIME_REST_MAX_BACKOFF_MS`

