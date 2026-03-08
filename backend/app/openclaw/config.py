"""Configuration models and manager for OpenClaw."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .logging import StructuredLogger


class OpenClawConfigurationError(ValueError):
    """Raised when OpenClaw configuration is invalid."""


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class DiscordSettings:
    bot_token: str = ""
    command_prefix: str = "!"
    authorized_users: list[str] = field(default_factory=list)
    admin_channel: str = ""
    command_channels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KimiK2Settings:
    api_key: str = ""
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "moonshot-v1-8k"
    max_tokens: int = 4096
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 60
    max_concurrent_calls: int = 5


@dataclass(slots=True)
class MonitoringSettings:
    market_monitor_interval_seconds: int = 60
    risk_monitor_interval_seconds: int = 60
    context_backup_interval_seconds: int = 300


@dataclass(slots=True)
class RiskLimitSettings:
    max_position_size_pct: float = 20.0
    max_daily_loss_pct: float = 5.0
    max_open_positions: int = 10
    min_trade_interval_seconds: int = 60
    max_order_size: float = 100_000.0


@dataclass(slots=True)
class PerformanceSettings:
    max_concurrent_users: int = 10
    command_timeout_seconds: int = 30
    max_queue_size: int = 100
    simple_command_sla_seconds: float = 2.0
    complex_command_sla_seconds: float = 10.0


@dataclass(slots=True)
class SecuritySettings:
    context_encryption_key: str = ""
    per_user_rate_limit_per_minute: int = 30
    enable_request_signing: bool = False
    signing_secret: str = ""


@dataclass(slots=True)
class OpenClawConfig:
    environment: str = "development"
    data_dir: str = "data/openclaw"
    log_level: str = "INFO"
    log_file: str = "data/openclaw/openclaw.log"
    marketpy_base_url: str = "http://localhost:8000"
    skills_dir: str = "backend/app/openclaw/skills"
    discord: DiscordSettings = field(default_factory=DiscordSettings)
    kimi_k2: KimiK2Settings = field(default_factory=KimiK2Settings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    risk_limits: RiskLimitSettings = field(default_factory=RiskLimitSettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.discord.bot_token:
            errors.append("OPENCLAW_DISCORD_BOT_TOKEN is required")
        if not self.kimi_k2.api_key:
            errors.append("OPENCLAW_KIMI_K2_API_KEY is required")
        if self.kimi_k2.max_tokens <= 0:
            errors.append("kimi_k2.max_tokens must be positive")
        if self.kimi_k2.rate_limit_per_minute <= 0:
            errors.append("kimi_k2.rate_limit_per_minute must be positive")
        if self.monitoring.market_monitor_interval_seconds <= 0:
            errors.append("monitoring.market_monitor_interval_seconds must be positive")
        if self.monitoring.risk_monitor_interval_seconds <= 0:
            errors.append("monitoring.risk_monitor_interval_seconds must be positive")
        if self.monitoring.context_backup_interval_seconds <= 0:
            errors.append("monitoring.context_backup_interval_seconds must be positive")
        if not 0 < self.risk_limits.max_position_size_pct <= 100:
            errors.append("risk_limits.max_position_size_pct must be in (0, 100]")
        if not 0 < self.risk_limits.max_daily_loss_pct <= 100:
            errors.append("risk_limits.max_daily_loss_pct must be in (0, 100]")
        if self.risk_limits.max_open_positions <= 0:
            errors.append("risk_limits.max_open_positions must be positive")
        if self.performance.max_concurrent_users <= 0:
            errors.append("performance.max_concurrent_users must be positive")
        if self.performance.command_timeout_seconds <= 0:
            errors.append("performance.command_timeout_seconds must be positive")
        if self.performance.max_queue_size <= 0:
            errors.append("performance.max_queue_size must be positive")
        if self.security.per_user_rate_limit_per_minute <= 0:
            errors.append("security.per_user_rate_limit_per_minute must be positive")
        return errors

    def to_safe_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["discord"]["bot_token"] = "***" if self.discord.bot_token else ""
        payload["kimi_k2"]["api_key"] = "***" if self.kimi_k2.api_key else ""
        payload["security"]["context_encryption_key"] = (
            "***" if self.security.context_encryption_key else ""
        )
        payload["security"]["signing_secret"] = "***" if self.security.signing_secret else ""
        return payload


class OpenClawConfigManager:
    """Loads and validates OpenClaw configuration from JSON + environment."""

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        logger: StructuredLogger | None = None,
    ):
        self._logger = logger or StructuredLogger("openclaw.config")
        self._config_path = Path(config_path) if config_path else Path("config/openclaw.json")
        self._config = self._load()

    def _load(self) -> OpenClawConfig:
        payload: dict[str, Any] = {}
        if self._config_path.exists():
            payload = json.loads(self._config_path.read_text(encoding="utf-8"))

        config = OpenClawConfig(
            environment=str(
                os.getenv("OPENCLAW_ENVIRONMENT", payload.get("environment", "development"))
            ),
            data_dir=str(os.getenv("OPENCLAW_DATA_DIR", payload.get("data_dir", "data/openclaw"))),
            log_level=str(os.getenv("OPENCLAW_LOG_LEVEL", payload.get("log_level", "INFO"))),
            log_file=str(
                os.getenv(
                    "OPENCLAW_LOG_FILE", payload.get("log_file", "data/openclaw/openclaw.log")
                )
            ),
            marketpy_base_url=str(
                os.getenv(
                    "OPENCLAW_MARKETPY_BASE_URL",
                    payload.get("marketpy_base_url", "http://localhost:8000"),
                )
            ),
            skills_dir=str(
                os.getenv(
                    "OPENCLAW_SKILLS_DIR", payload.get("skills_dir", "backend/app/openclaw/skills")
                )
            ),
            discord=DiscordSettings(
                bot_token=os.getenv(
                    "OPENCLAW_DISCORD_BOT_TOKEN",
                    payload.get("discord", {}).get("bot_token", ""),
                ),
                command_prefix=os.getenv(
                    "OPENCLAW_DISCORD_COMMAND_PREFIX",
                    payload.get("discord", {}).get("command_prefix", "!"),
                ),
                authorized_users=_parse_list(
                    os.getenv(
                        "OPENCLAW_DISCORD_AUTHORIZED_USERS",
                        ",".join(payload.get("discord", {}).get("authorized_users", [])),
                    )
                ),
                admin_channel=os.getenv(
                    "OPENCLAW_DISCORD_ADMIN_CHANNEL",
                    payload.get("discord", {}).get("admin_channel", ""),
                ),
                command_channels=_parse_list(
                    os.getenv(
                        "OPENCLAW_DISCORD_COMMAND_CHANNELS",
                        ",".join(payload.get("discord", {}).get("command_channels", [])),
                    )
                ),
            ),
            kimi_k2=KimiK2Settings(
                api_key=os.getenv(
                    "OPENCLAW_KIMI_K2_API_KEY",
                    payload.get("kimi_k2", {}).get("api_key", ""),
                ),
                base_url=str(
                    os.getenv(
                        "OPENCLAW_KIMI_K2_BASE_URL",
                        payload.get("kimi_k2", {}).get("base_url", "https://api.moonshot.cn/v1"),
                    )
                ),
                model=str(
                    os.getenv(
                        "OPENCLAW_KIMI_K2_MODEL",
                        payload.get("kimi_k2", {}).get("model", "moonshot-v1-8k"),
                    )
                ),
                max_tokens=int(
                    os.getenv(
                        "OPENCLAW_KIMI_K2_MAX_TOKENS",
                        payload.get("kimi_k2", {}).get("max_tokens", 4096),
                    )
                ),
                timeout_seconds=int(
                    os.getenv(
                        "OPENCLAW_KIMI_K2_TIMEOUT",
                        payload.get("kimi_k2", {}).get("timeout_seconds", 30),
                    )
                ),
                rate_limit_per_minute=int(
                    os.getenv(
                        "OPENCLAW_KIMI_K2_RATE_LIMIT",
                        payload.get("kimi_k2", {}).get("rate_limit_per_minute", 60),
                    )
                ),
                max_concurrent_calls=int(
                    os.getenv(
                        "OPENCLAW_KIMI_K2_MAX_CONCURRENT",
                        payload.get("kimi_k2", {}).get("max_concurrent_calls", 5),
                    )
                ),
            ),
            monitoring=MonitoringSettings(
                market_monitor_interval_seconds=int(
                    os.getenv(
                        "OPENCLAW_MARKET_MONITOR_INTERVAL",
                        payload.get("monitoring", {}).get("market_monitor_interval_seconds", 60),
                    )
                ),
                risk_monitor_interval_seconds=int(
                    os.getenv(
                        "OPENCLAW_RISK_MONITOR_INTERVAL",
                        payload.get("monitoring", {}).get("risk_monitor_interval_seconds", 60),
                    )
                ),
                context_backup_interval_seconds=int(
                    os.getenv(
                        "OPENCLAW_CONTEXT_BACKUP_INTERVAL",
                        payload.get("monitoring", {}).get("context_backup_interval_seconds", 300),
                    )
                ),
            ),
            risk_limits=RiskLimitSettings(
                max_position_size_pct=float(
                    os.getenv(
                        "OPENCLAW_RISK_MAX_POSITION_SIZE_PCT",
                        payload.get("risk_limits", {}).get("max_position_size_pct", 20.0),
                    )
                ),
                max_daily_loss_pct=float(
                    os.getenv(
                        "OPENCLAW_RISK_MAX_DAILY_LOSS_PCT",
                        payload.get("risk_limits", {}).get("max_daily_loss_pct", 5.0),
                    )
                ),
                max_open_positions=int(
                    os.getenv(
                        "OPENCLAW_RISK_MAX_OPEN_POSITIONS",
                        payload.get("risk_limits", {}).get("max_open_positions", 10),
                    )
                ),
                min_trade_interval_seconds=int(
                    os.getenv(
                        "OPENCLAW_RISK_MIN_TRADE_INTERVAL",
                        payload.get("risk_limits", {}).get("min_trade_interval_seconds", 60),
                    )
                ),
                max_order_size=float(
                    os.getenv(
                        "OPENCLAW_RISK_MAX_ORDER_SIZE",
                        payload.get("risk_limits", {}).get("max_order_size", 100_000.0),
                    )
                ),
            ),
            performance=PerformanceSettings(
                max_concurrent_users=int(
                    os.getenv(
                        "OPENCLAW_PERF_MAX_CONCURRENT_USERS",
                        payload.get("performance", {}).get("max_concurrent_users", 10),
                    )
                ),
                command_timeout_seconds=int(
                    os.getenv(
                        "OPENCLAW_PERF_COMMAND_TIMEOUT",
                        payload.get("performance", {}).get("command_timeout_seconds", 30),
                    )
                ),
                max_queue_size=int(
                    os.getenv(
                        "OPENCLAW_PERF_MAX_QUEUE_SIZE",
                        payload.get("performance", {}).get("max_queue_size", 100),
                    )
                ),
                simple_command_sla_seconds=float(
                    os.getenv(
                        "OPENCLAW_PERF_SIMPLE_SLA",
                        payload.get("performance", {}).get("simple_command_sla_seconds", 2.0),
                    )
                ),
                complex_command_sla_seconds=float(
                    os.getenv(
                        "OPENCLAW_PERF_COMPLEX_SLA",
                        payload.get("performance", {}).get("complex_command_sla_seconds", 10.0),
                    )
                ),
            ),
            security=SecuritySettings(
                context_encryption_key=os.getenv(
                    "OPENCLAW_CONTEXT_ENCRYPTION_KEY",
                    payload.get("security", {}).get("context_encryption_key", ""),
                ),
                per_user_rate_limit_per_minute=int(
                    os.getenv(
                        "OPENCLAW_SECURITY_PER_USER_RATE_LIMIT",
                        payload.get("security", {}).get("per_user_rate_limit_per_minute", 30),
                    )
                ),
                enable_request_signing=str(
                    os.getenv(
                        "OPENCLAW_SECURITY_ENABLE_REQUEST_SIGNING",
                        payload.get("security", {}).get("enable_request_signing", False),
                    )
                ).lower()
                in {"1", "true", "yes", "on"},
                signing_secret=os.getenv(
                    "OPENCLAW_SECURITY_SIGNING_SECRET",
                    payload.get("security", {}).get("signing_secret", ""),
                ),
            ),
        )

        errors = config.validate()
        if errors:
            raise OpenClawConfigurationError(
                "OpenClaw configuration validation failed:\n- " + "\n- ".join(errors)
            )

        self._logger.info("OpenClaw configuration loaded", config.to_safe_dict())
        self._ensure_directories(config)
        return config

    @staticmethod
    def _ensure_directories(config: OpenClawConfig) -> None:
        data_dir = Path(config.data_dir)
        for directory in [
            data_dir / "contexts",
            data_dir / "preferences",
            data_dir / "conditions",
            data_dir / "backups",
            Path(config.skills_dir),
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> OpenClawConfig:
        return self._config

    def reload(self) -> OpenClawConfig:
        self._config = self._load()
        return self._config

    def update_runtime(self, updates: dict[str, Any]) -> OpenClawConfig:
        """
        Update non-critical runtime settings only.

        Supported keys:
        - monitoring.market_monitor_interval_seconds
        - monitoring.risk_monitor_interval_seconds
        - monitoring.context_backup_interval_seconds
        - performance.max_queue_size
        """
        allowed = {
            "monitoring.market_monitor_interval_seconds",
            "monitoring.risk_monitor_interval_seconds",
            "monitoring.context_backup_interval_seconds",
            "performance.max_queue_size",
        }
        for key, value in updates.items():
            if key not in allowed:
                message = (
                    f"Runtime update not allowed for '{key}'. "
                    "Only non-critical settings are mutable."
                )
                raise OpenClawConfigurationError(
                    message
                )

            section, field_name = key.split(".", maxsplit=1)
            section_obj = getattr(self._config, section)
            setattr(section_obj, field_name, value)

        errors = self._config.validate()
        if errors:
            raise OpenClawConfigurationError(
                "Runtime configuration validation failed:\n- " + "\n- ".join(errors)
            )
        return self._config
