# Phase 41 Hardening Migration Notes

Date: 2026-03-05
Scope: Hardening updates after roadmap task `40`

## Breaking vs Compatible Changes

### Replay engine cursor handling
- Change: replay now maintains separate internal cursors for orderbooks and trades.
- Compatibility: existing public methods (`seek`, `stream_orderbook`, `stream_trades`) are unchanged.
- Effect: interleaved calls no longer reuse one shared stream pointer.

### Arbitrage metrics key semantics
- Preferred key: `avg_detection_interval_seconds`.
- Compatibility alias: `avg_duration_seconds` is still returned with the same numeric value.
- Action for consumers: migrate dashboards/alerts to the new key.

### Drift detector persistence behavior
- Change: `calculate_drift()` now reloads prediction history from SQLite for the model.
- Compatibility: method signatures remain unchanged.
- Effect: drift calculations survive process restarts.

### Feature importance method naming
- Canonical methods:
  - `heuristic_shap_proxy`
  - `heuristic_permutation_proxy`
  - `heuristic_gain_proxy`
- Compatibility aliases accepted:
  - `shap` -> `heuristic_shap_proxy`
  - `permutation` -> `heuristic_permutation_proxy`
  - `gain` -> `heuristic_gain_proxy`
- Action for consumers: update stored configs/UI labels to canonical names.

### SQL hardening for count helper
- Change: `DriftDetector.count_rows(table_name)` now accepts only:
  - `prediction_tracking`
  - `drift_metrics`
- Effect: raises `ValueError` for any other table name.

## Staging smoke verification
- `scripts/smoke_staging.py` now:
  - checks an expanded endpoint matrix
  - supports optional auth-route verification
  - writes a Markdown report artifact with env, SHA, UTC timestamp, and per-endpoint status
- New CI workflow:
  - `.github/workflows/staging-smoke.yml`
  - manual trigger with `staging_api_url` input
  - uploads `deploy/staging-smoke-report.md` as artifact
