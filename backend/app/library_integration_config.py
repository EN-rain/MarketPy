"""Centralized configuration schema for external library integrations."""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class ExchangeSettings(BaseModel):
    exchange_type: str = "binance"
    api_key: str | None = None
    api_secret: str | None = None
    passphrase: str | None = None
    enable_rate_limit: bool = True
    timeout_ms: int = 30000
    rate_limit: int = 1200


class BacktestSettings(BaseModel):
    execution_mode: str = "event_driven"
    fill_model: str = "M2"
    network_latency_ms: int = 50
    exchange_latency_ms: int = 20


class FeatureEngineeringSettings(BaseModel):
    indicator_library: str = "auto"
    scaler_type: str = "standard"
    importance_method: str = "tree"


class PaperTradingSettings(BaseModel):
    strategy_interface: str = "mixed"
    max_position_per_market: float = 1000.0
    max_total_exposure: float = 5000.0
    max_daily_loss: float = 500.0


class MonitoringSettings(BaseModel):
    discord_webhook_url: str | None = None
    discord_rate_limit_per_minute: int = 10
    enable_json_logs: bool = True


class LibraryIntegrationConfig(BaseModel):
    environment: str = Field(default="development")
    exchange: ExchangeSettings = Field(default_factory=ExchangeSettings)
    backtesting: BacktestSettings = Field(default_factory=BacktestSettings)
    feature_engineering: FeatureEngineeringSettings = Field(default_factory=FeatureEngineeringSettings)
    paper_trading: PaperTradingSettings = Field(default_factory=PaperTradingSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    @model_validator(mode="after")
    def validate_required_settings(self) -> LibraryIntegrationConfig:
        if self.paper_trading.max_position_per_market <= 0:
            raise ValueError("paper_trading.max_position_per_market must be positive")
        if self.paper_trading.max_total_exposure <= 0:
            raise ValueError("paper_trading.max_total_exposure must be positive")
        if self.paper_trading.max_daily_loss <= 0:
            raise ValueError("paper_trading.max_daily_loss must be positive")
        if self.monitoring.discord_rate_limit_per_minute <= 0:
            raise ValueError("monitoring.discord_rate_limit_per_minute must be positive")
        return self

    def sanitized_for_logging(self) -> dict[str, Any]:
        data = self.model_dump()
        if data["exchange"]["api_key"]:
            data["exchange"]["api_key"] = "***"
        if data["exchange"]["api_secret"]:
            data["exchange"]["api_secret"] = "***"
        if data["exchange"]["passphrase"]:
            data["exchange"]["passphrase"] = "***"
        if data["monitoring"]["discord_webhook_url"]:
            data["monitoring"]["discord_webhook_url"] = "***"
        return data


def load_library_integration_config() -> LibraryIntegrationConfig:
    env = os.getenv("APP_ENV", "development")
    exchange_type = os.getenv("EXCHANGE_TYPE", "binance")
    prefix = exchange_type.upper()
    config = LibraryIntegrationConfig(
        environment=env,
        exchange=ExchangeSettings(
            exchange_type=exchange_type,
            api_key=os.getenv(f"{prefix}_API_KEY"),
            api_secret=os.getenv(f"{prefix}_API_SECRET"),
            passphrase=os.getenv(f"{prefix}_PASSPHRASE"),
            enable_rate_limit=os.getenv("EXCHANGE_ENABLE_RATE_LIMIT", "true").lower() in {
                "1",
                "true",
                "yes",
                "on",
            },
            timeout_ms=int(os.getenv("EXCHANGE_TIMEOUT_MS", "30000")),
            rate_limit=int(os.getenv("EXCHANGE_RATE_LIMIT", "1200")),
        ),
        backtesting=BacktestSettings(
            execution_mode=os.getenv("BACKTEST_EXECUTION_MODE", "event_driven"),
            fill_model=os.getenv("BACKTEST_FILL_MODEL", "M2"),
            network_latency_ms=int(os.getenv("BACKTEST_NETWORK_LATENCY_MS", "50")),
            exchange_latency_ms=int(os.getenv("BACKTEST_EXCHANGE_LATENCY_MS", "20")),
        ),
        feature_engineering=FeatureEngineeringSettings(
            indicator_library=os.getenv("INDICATOR_LIBRARY", "auto"),
            scaler_type=os.getenv("FEATURE_SCALER_TYPE", "standard"),
            importance_method=os.getenv("FEATURE_IMPORTANCE_METHOD", "tree"),
        ),
        paper_trading=PaperTradingSettings(
            strategy_interface=os.getenv("PAPER_STRATEGY_INTERFACE", "mixed"),
            max_position_per_market=float(os.getenv("MAX_POSITION_PER_MARKET", "1000.0")),
            max_total_exposure=float(os.getenv("MAX_TOTAL_EXPOSURE", "5000.0")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "500.0")),
        ),
        monitoring=MonitoringSettings(
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
            discord_rate_limit_per_minute=int(os.getenv("DISCORD_RATE_LIMIT_PER_MINUTE", "10")),
            enable_json_logs=os.getenv("ENABLE_JSON_LOGS", "true").lower()
            in {"1", "true", "yes", "on"},
        ),
    )
    logger.info("Loaded library integration config: %s", config.sanitized_for_logging())
    return config
