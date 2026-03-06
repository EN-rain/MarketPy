"""Application configuration via pydantic-settings."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class SimMode(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"


class FillModelLevel(str, Enum):
    M1_MID = "M1"  # fill at mid + fee (debug)
    M2_BIDASK = "M2"  # fill at bid/ask (realistic)
    M3_DEPTH = "M3"  # orderbook-depth fill model


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


class AppSettings(BaseSettings):
    """Global application settings loaded from .env."""

    # Crypto market data
    binance_api_url: str = "https://api.binance.com"
    binance_ws_url: str = "wss://stream.binance.com:9443/stream"
    exchange_type: str = "binance"
    exchange_enable_rate_limit: bool = True
    exchange_rate_limit: int = 1200
    exchange_timeout_ms: int = 30000

    # Server
    backend_port: int = 8000
    frontend_port: int = 3000
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    backtest_api_key: str = ""
    backtest_rate_limit_per_minute: int = 10

    # Simulation
    bar_size: str = "5m"
    default_fee_rate: float = 0.02
    default_fee_exponent: float = 2.0
    initial_cash: float = 10000.0
    fill_model: FillModelLevel = FillModelLevel.M2_BIDASK
    backtest_execution_mode: str = "event_driven"

    # Risk constraints
    max_position_per_market: float = 1000.0
    max_total_exposure: float = 5000.0
    max_daily_loss: float = 500.0
    cooldown_seconds: int = 60

    # ML
    model_dir: str = "models"
    data_dir: str = "data"
    indicator_library: str = "auto"
    feature_scaler_type: str = "standard"
    feature_importance_method: str = "tree"

    # Strategy
    edge_buffer: float = 0.02
    kelly_fraction: float = 0.1

    # Notifications / monitoring
    discord_webhook_url: str | None = None
    discord_rate_limit_per_minute: int = 10
    discord_enabled_categories: str = "ERROR,WARNING,INFO,TRADE,RISK,SYSTEM"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = AppSettings()
