# Configuration

## Active Environment

MarketPy loads one of these files based on `MARKETPY_ENV`:

- `config/dev.yaml`
- `config/staging.yaml`
- `config/prod.yaml`

If `MARKETPY_ENV` is not set, the default is `dev`.

## Exchange Defaults

Shared exchange endpoints live in `config/exchanges.yaml`. They are merged into the active environment config under the `exchanges` key.

## Environment Overrides

Top-level application settings can be overridden with uppercase environment variables matching the field name:

- `BACKEND_PORT`
- `FRONTEND_PORT`
- `MODEL_DIR`
- `DATA_DIR`
- `CORS_ORIGINS`

List values support JSON arrays such as:

```bash
set CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]
```

## Compatibility Files

These component-specific files remain in place for existing subsystems:

- `config/realtime_updates.json`
- `config/openclaw.json`

They are not yet merged into the shared YAML application settings.
