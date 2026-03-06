# OpenClaw Quickstart

## 1) Configure environment

1. Copy `.env.example` to `.env`.
2. Set:
   - `OPENCLAW_DISCORD_BOT_TOKEN`
   - `OPENCLAW_KIMI_K2_API_KEY`
   - `OPENCLAW_DISCORD_AUTHORIZED_USERS`
3. Optionally edit `config/openclaw.json`.

## 2) Install dependencies

```powershell
./deploy/openclaw/install_openclaw.ps1
```

## 3) Start OpenClaw service

```powershell
./deploy/openclaw/start_openclaw.ps1
```

The service starts on `http://localhost:8100`.

## 4) Verify health and metrics

```powershell
./deploy/openclaw/health_check_openclaw.ps1
```

## 5) Send test command

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/command" -Body (@{
  user_id = "your-discord-user-id"
  channel_id = "your-channel-id"
  content = "Check BTC price"
} | ConvertTo-Json) -ContentType "application/json"
```
