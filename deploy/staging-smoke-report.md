# Staging Smoke Report

- environment: local-simulation
- base_url: http://localhost:8000
- build_sha: local
- started_at_utc: 2026-03-05T00:00:00+00:00
- total_checks: 8
- passed: 8
- failed: 0
- overall: PASS

## Endpoint Matrix

| Method | Endpoint | Expected | Actual | Duration(ms) | Result | Detail |
|---|---|---:|---:|---:|---|---|
| GET | /api/status | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/portfolio | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/health/connections | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/health/processing | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/health/memory | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/health/rate-limits | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/health/config | 200 | 200 | 0.00 | OK | status_match |
| GET | /api/metrics/tasks | 200 | 200 | 0.00 | OK | status_match |
