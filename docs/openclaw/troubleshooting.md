# OpenClaw Troubleshooting

## Service not starting

- Confirm required env vars are set:
  - `OPENCLAW_DISCORD_BOT_TOKEN`
  - `OPENCLAW_KIMI_K2_API_KEY`
- Validate `config/openclaw.json` JSON syntax.
- Check logs in `data/openclaw/openclaw.log`.

## Commands are queued but not executed

- Check `/health` queue depth.
- Verify Kimi API key and rate limit settings.
- Ensure worker count (`OPENCLAW_PERF_MAX_CONCURRENT_USERS`) is > 0.

## Discord permissions denied

- Add your user ID to `OPENCLAW_DISCORD_AUTHORIZED_USERS`.
- Confirm channel ID is included in `OPENCLAW_DISCORD_COMMAND_CHANNELS` if set.

## Context encryption/decryption errors

- Keep `OPENCLAW_CONTEXT_ENCRYPTION_KEY` stable across restarts.
- If key rotates, old encrypted context files become unreadable.

## Market monitor not triggering

- Verify conditions are enabled and symbols match exchange symbol format.
- Check monitor interval (`OPENCLAW_MARKET_MONITOR_INTERVAL`).
- Ensure exchange client credentials/connectivity are valid.
