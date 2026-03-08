"""Application configuration loaded from YAML with environment overrides."""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.app.config_loader import load_environment_config, resolve_environment_name


class SimMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"


class FillModelLevel(str, Enum):
    M1_MID = "M1"
    M2_BIDASK = "M2"
    M3_DEPTH = "M3"


class FeeConfig(BaseModel):
    """Fee model parameters."""

    fee_rate: float = 0.02
    exponent: float = 2.0


class StrategyConfig(BaseModel):
    """Strategy-specific parameters."""

    name: str = "momentum"
    lookback_bars: int = 12
    z_entry: float = 2.0
    z_exit: float = 0.5
    momentum_threshold: float = 0.01
    horizons: list[str] = Field(default=["1h", "6h", "1d"])


class AppSettings(BaseModel):
    """Global application settings."""

    environment: str = "dev"

    binance_api_url: str = "https://api.binance.com"
    binance_ws_url: str = "wss://stream.binance.com:9443/stream"
    exchange_type: str = "binance"
    exchange_enable_rate_limit: bool = True
    exchange_rate_limit: int = 1200
    exchange_timeout_ms: int = 30000

    backend_port: int = 8000
    frontend_port: int = 3000
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    backtest_api_key: str = ""
    backtest_rate_limit_per_minute: int = 10
    security_enable_auth: bool = False
    security_require_https: bool = False
    security_enable_rate_limit: bool = True
    security_jwt_secret: str = "change-me-in-prod"
    security_jwt_exp_minutes: int = 60
    security_rate_limit_rps: float = 20.0
    security_rate_limit_burst: int = 40
    security_failed_auth_block_threshold: int = 10
    security_block_duration_seconds: int = 600
    security_api_key_encryption_key: str = "change-me-in-prod"
    security_bootstrap_token: str = ""

    bar_size: str = "5m"
    default_fee_rate: float = 0.02
    default_fee_exponent: float = 2.0
    initial_cash: float = 10000.0
    fill_model: FillModelLevel = FillModelLevel.M2_BIDASK
    backtest_execution_mode: str = "event_driven"

    max_position_per_market: float = 1000.0
    max_total_exposure: float = 5000.0
    max_daily_loss: float = 500.0
    cooldown_seconds: int = 60

    model_dir: str = "models"
    data_dir: str = "data"
    indicator_library: str = "auto"
    feature_scaler_type: str = "standard"
    feature_importance_method: str = "tree"

    edge_buffer: float = 0.02
    kelly_fraction: float = 0.1

    discord_webhook_url: str | None = None
    discord_rate_limit_per_minute: int = 10
    discord_enabled_categories: str = "ERROR,WARNING,INFO,TRADE,RISK,SYSTEM"

    exchanges: dict[str, Any] = Field(default_factory=dict)


def _parse_env_value(raw_value: str, current_value: Any) -> Any:
    if isinstance(current_value, bool):
        return raw_value.lower() in {"1", "true", "yes", "on"}
    if isinstance(current_value, int) and not isinstance(current_value, bool):
        return int(raw_value)
    if isinstance(current_value, float):
        return float(raw_value)
    if isinstance(current_value, list):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    return raw_value


def load_settings(environment: str | None = None) -> AppSettings:
    """Load settings from YAML and override with environment variables."""
    config_data = load_environment_config(environment)
    settings = AppSettings(**config_data)

    for field_name in AppSettings.model_fields:
        env_var = field_name.upper()
        raw_value = os.getenv(env_var)
        if raw_value is None:
            continue
        current_value = getattr(settings, field_name)
        setattr(settings, field_name, _parse_env_value(raw_value, current_value))

    settings.environment = resolve_environment_name(environment)
    return settings


settings = load_settings()
