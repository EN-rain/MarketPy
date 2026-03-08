# Realtime Deployment Guide

## 1. Baseline

- Use defaults from `config/realtime_updates.json` first.
- Ensure backend runs with persistent logging.

## 2. Throughput Tuning

- Increase `max_messages_per_second` gradually per environment.
- Increase `burst_size` for short spikes.
- Increase `batch_window_ms` to reduce websocket chatter.

## 3. Latency Tuning

- Decrease `batch_window_ms` and `max_batch_size`.
- Keep `critical_bypass=true` in production.
- Monitor p95/p99 via `/api/health/processing`.

## 4. Memory Tuning

- Reduce `max_candles_per_market` for large market universes.
- Lower `retention_seconds` when memory pressure is high.
- Use tier policies for hot vs cold markets.

## 5. Frontend Fallback

- Keep websocket connected polling at slow interval.
- Use faster interval on disconnect.
- Keep exponential backoff enabled for REST retries.

## 6. Operational Checks

- `GET /health` should return 200.
- `GET /api/health/config` should match expected runtime values.
- `GET /api/health/connections` and `/api/health/rate-limits` should be non-error under load.

