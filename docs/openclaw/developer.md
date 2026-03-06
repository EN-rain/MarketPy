# OpenClaw Developer Notes

## Kimi K2 integration

- Module: `backend/app/openclaw/kimi_k2_client.py`
- Authentication: `Authorization: Bearer <OPENCLAW_KIMI_K2_API_KEY>`
- Retry policy:
  - Up to 3 attempts
  - Exponential backoff with jitter
  - Retries on HTTP 429, HTTP 5xx, timeout/network failures
- Rate limiting:
  - Minute window limiter (`OPENCLAW_KIMI_K2_RATE_LIMIT`)
  - Queue-based waiting on saturation

## Component composition

- Main orchestrator: `backend/app/openclaw/autonomous_agent.py`
- Service entrypoint: `backend/app/openclaw/main.py`
- Data models: `backend/app/openclaw/models.py`
- Context persistence/encryption: `backend/app/openclaw/context_manager.py`

## Security best practices

1. Keep all secrets in env vars, never in source.
2. Set `OPENCLAW_CONTEXT_ENCRYPTION_KEY` for encrypted context files.
3. Enable request signing with:
   - `OPENCLAW_SECURITY_ENABLE_REQUEST_SIGNING=true`
   - `OPENCLAW_SECURITY_SIGNING_SECRET=<secret>`
4. Restrict command access with `OPENCLAW_DISCORD_AUTHORIZED_USERS`.
5. Review logs for leaked user input and keep `mask_secrets()` patterns updated.

## Local development workflow

1. Run unit/property tests:
   ```powershell
   python -m pytest backend/tests/openclaw -v
   ```
2. Start OpenClaw service:
   ```powershell
   ./deploy/openclaw/start_openclaw.ps1
   ```
3. Check health/metrics:
   ```powershell
   ./deploy/openclaw/health_check_openclaw.ps1
   ```
