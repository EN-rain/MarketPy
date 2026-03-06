"""Configuration manager for enhanced realtime updates system.

This module provides centralized configuration management with:
- Loading from JSON file with optional path parameter
- Environment variable overrides (e.g., REALTIME_BATCH_WINDOW_MS)
- Comprehensive validation with range checks
- Default values for optional fields
- Configuration logging at startup
- Fail-fast behavior with clear error messages
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from backend.app.models.realtime_config import (
    BackpressureConfig,
    BatcherConfig,
    MemoryConfig,
    PrioritizerConfig,
    RateLimiterConfig,
    RetentionPolicy,
    SystemConfig,
)

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


class ConfigManager:
    """Manages configuration loading, validation, and access for the realtime system.
    
    The ConfigManager:
    - Loads configuration from JSON file (optional path parameter)
    - Applies environment variable overrides (e.g., REALTIME_BATCH_WINDOW_MS)
    - Validates all numeric ranges (e.g., min_cooldown < max_cooldown)
    - Validates required fields
    - Provides default values for optional fields
    - Logs all active configuration values at startup
    - Fails fast at startup with clear error messages for invalid config
    - Never crashes due to configuration issues after startup
    """

    def __init__(self, config_path: str | None = None):
        """Initialize ConfigManager and load configuration.
        
        Args:
            config_path: Optional path to JSON configuration file.
                        If None, uses default config with env var overrides.
        
        Raises:
            ConfigurationError: If configuration is invalid or cannot be loaded.
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self._validate_config()
        self._log_configuration()

    def _load_config(self, path: str | None) -> SystemConfig:
        """Load configuration from file and apply environment variable overrides.
        
        Args:
            path: Optional path to JSON configuration file.
        
        Returns:
            SystemConfig with loaded and overridden values.
        
        Raises:
            ConfigurationError: If file cannot be read or parsed.
        """
        # Start with default configuration
        config_dict: dict[str, Any] = {}

        # Load from file if provided
        if path:
            try:
                config_file = Path(path)
                if not config_file.exists():
                    raise ConfigurationError(f"Configuration file not found: {path}")

                with open(config_file) as f:
                    config_dict = json.load(f)
                    logger.info(f"Loaded configuration from {path}")
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in configuration file {path}: {e}")
            except Exception as e:
                raise ConfigurationError(f"Failed to read configuration file {path}: {e}")

        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(config_dict)

        # Build SystemConfig from dictionary
        try:
            return self._build_system_config(config_dict)
        except Exception as e:
            raise ConfigurationError(f"Failed to build configuration: {e}")

    def _apply_env_overrides(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to configuration.
        
        Environment variables follow the pattern: REALTIME_<PARAM_NAME>
        For example: REALTIME_BATCH_WINDOW_MS, REALTIME_MAX_BATCH_SIZE
        
        Args:
            config_dict: Base configuration dictionary.
        
        Returns:
            Configuration dictionary with environment overrides applied.
        """
        env_mappings = {
            # Batching
            'REALTIME_BATCH_WINDOW_MS': ('batch_window_ms', int),
            'REALTIME_MAX_BATCH_SIZE': ('max_batch_size', int),
            'REALTIME_ENABLE_BATCHING': ('enable_batching', self._parse_bool),

            # Rate Limiting
            'REALTIME_MAX_MESSAGES_PER_SECOND': ('max_messages_per_second', int),
            'REALTIME_BURST_SIZE': ('burst_size', int),
            'REALTIME_CRITICAL_BYPASS': ('critical_bypass', self._parse_bool),

            # Prioritization
            'REALTIME_PRICE_CHANGE_THRESHOLD': ('price_change_threshold', float),
            'REALTIME_VOLUME_SPIKE_MULTIPLIER': ('volume_spike_multiplier', float),

            # Memory Management
            'REALTIME_MAX_CANDLES_PER_MARKET': ('max_candles_per_market', int),
            'REALTIME_RETENTION_SECONDS': ('retention_seconds', int),

            # Backpressure
            'REALTIME_SEND_BUFFER_THRESHOLD': ('send_buffer_threshold', int),
            'REALTIME_SLOW_CLIENT_TIMEOUT': ('slow_client_timeout', int),
            'REALTIME_DROP_NON_CRITICAL_FOR_SLOW': ('drop_non_critical_for_slow', self._parse_bool),

            # Concurrency
            'REALTIME_WORKER_POOL_SIZE': ('worker_pool_size', int),
            'REALTIME_MAX_CONCURRENT_MARKETS': ('max_concurrent_markets', int),

            # Signal Cooldown
            'REALTIME_MIN_SIGNAL_COOLDOWN_SECONDS': ('min_signal_cooldown_seconds', float),
            'REALTIME_MAX_SIGNAL_COOLDOWN_SECONDS': ('max_signal_cooldown_seconds', float),
            'REALTIME_VOLATILITY_WINDOW_SECONDS': ('volatility_window_seconds', int),
            'REALTIME_VOLATILITY_THRESHOLD_LOW': ('volatility_threshold_low', float),
            'REALTIME_VOLATILITY_THRESHOLD_HIGH': ('volatility_threshold_high', float),

            # Frontend Polling
            'REALTIME_WS_CONNECTED_POLL_INTERVAL_MS': ('ws_connected_poll_interval_ms', int),
            'REALTIME_WS_DISCONNECTED_POLL_INTERVAL_MS': ('ws_disconnected_poll_interval_ms', int),
            'REALTIME_REST_BACKOFF_MULTIPLIER': ('rest_backoff_multiplier', float),
            'REALTIME_REST_MAX_BACKOFF_MS': ('rest_max_backoff_ms', int),
        }

        for env_var, (config_key, converter) in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value is not None:
                try:
                    config_dict[config_key] = converter(env_value)
                    logger.info(f"Applied environment override: {env_var}={env_value}")
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid value for environment variable {env_var}={env_value}: {e}. "
                        f"Using file or default value."
                    )

        return config_dict

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse boolean from string value.
        
        Args:
            value: String value to parse.
        
        Returns:
            Boolean value.
        
        Raises:
            ValueError: If value cannot be parsed as boolean.
        """
        if isinstance(value, bool):
            return value

        value_lower = value.lower()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        elif value_lower in ('false', '0', 'no', 'off'):
            return False
        else:
            raise ValueError(f"Cannot parse '{value}' as boolean")

    def _build_system_config(self, config_dict: dict[str, Any]) -> SystemConfig:
        """Build SystemConfig from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary.
        
        Returns:
            SystemConfig instance.
        """
        # Handle tier_policies if present - they should be nested under memory config
        if 'tier_policies' in config_dict:
            tier_policies = {}
            for tier_name, policy_dict in config_dict['tier_policies'].items():
                tier_policies[tier_name] = RetentionPolicy(
                    max_candles=policy_dict.get('max_candles', 1000),
                    retention_seconds=policy_dict.get('retention_seconds', 86400)
                )
            # Remove from top level and will be handled by SystemConfig's __post_init__
            # Store it temporarily for validation
            config_dict['_tier_policies_temp'] = tier_policies
            del config_dict['tier_policies']

        # Handle critical_event_types if present
        if 'critical_event_types' in config_dict:
            if isinstance(config_dict['critical_event_types'], str):
                config_dict['critical_event_types'] = [
                    t.strip() for t in config_dict['critical_event_types'].split(',')
                ]

        # Create SystemConfig with provided values
        system_config = SystemConfig(**{k: v for k, v in config_dict.items() if v is not None and not k.startswith('_')})

        # Apply tier policies to memory config if present
        if '_tier_policies_temp' in config_dict:
            system_config.memory.tier_policies = config_dict['_tier_policies_temp']

        return system_config

    def _validate_config(self) -> None:
        """Validate all configuration parameters.
        
        Raises:
            ConfigurationError: If any validation check fails.
        """
        errors = []

        # Validate batching parameters
        if self.config.batch_window_ms <= 0:
            errors.append("batch_window_ms must be positive")
        if self.config.batch_window_ms > 10000:
            errors.append("batch_window_ms must not exceed 10000ms (10 seconds)")

        if self.config.max_batch_size <= 0:
            errors.append("max_batch_size must be positive")
        if self.config.max_batch_size > 1000:
            errors.append("max_batch_size must not exceed 1000")

        # Validate rate limiting parameters
        if self.config.max_messages_per_second <= 0:
            errors.append("max_messages_per_second must be positive")
        if self.config.max_messages_per_second > 1000:
            errors.append("max_messages_per_second must not exceed 1000")

        if self.config.burst_size <= 0:
            errors.append("burst_size must be positive")
        if self.config.burst_size < self.config.max_messages_per_second:
            errors.append("burst_size must be >= max_messages_per_second")

        # Validate prioritization parameters
        if self.config.price_change_threshold < 0:
            errors.append("price_change_threshold must be non-negative")
        if self.config.price_change_threshold > 1.0:
            errors.append("price_change_threshold must not exceed 1.0 (100%)")

        if self.config.volume_spike_multiplier < 1.0:
            errors.append("volume_spike_multiplier must be >= 1.0")

        # Validate memory management parameters
        if self.config.max_candles_per_market <= 0:
            errors.append("max_candles_per_market must be positive")

        if self.config.retention_seconds <= 0:
            errors.append("retention_seconds must be positive")

        # Validate backpressure parameters
        if self.config.send_buffer_threshold <= 0:
            errors.append("send_buffer_threshold must be positive")

        if self.config.slow_client_timeout <= 0:
            errors.append("slow_client_timeout must be positive")

        # Validate concurrency parameters
        if self.config.worker_pool_size <= 0:
            errors.append("worker_pool_size must be positive")
        if self.config.worker_pool_size > 100:
            errors.append("worker_pool_size must not exceed 100")

        if self.config.max_concurrent_markets <= 0:
            errors.append("max_concurrent_markets must be positive")

        # Validate signal cooldown parameters (CRITICAL: min < max)
        if self.config.min_signal_cooldown_seconds <= 0:
            errors.append("min_signal_cooldown_seconds must be positive")

        if self.config.max_signal_cooldown_seconds <= 0:
            errors.append("max_signal_cooldown_seconds must be positive")

        if self.config.min_signal_cooldown_seconds >= self.config.max_signal_cooldown_seconds:
            errors.append(
                f"min_signal_cooldown_seconds ({self.config.min_signal_cooldown_seconds}) "
                f"must be less than max_signal_cooldown_seconds ({self.config.max_signal_cooldown_seconds})"
            )

        if self.config.volatility_window_seconds <= 0:
            errors.append("volatility_window_seconds must be positive")

        if self.config.volatility_threshold_low < 0:
            errors.append("volatility_threshold_low must be non-negative")

        if self.config.volatility_threshold_high < 0:
            errors.append("volatility_threshold_high must be non-negative")

        if self.config.volatility_threshold_low >= self.config.volatility_threshold_high:
            errors.append(
                f"volatility_threshold_low ({self.config.volatility_threshold_low}) "
                f"must be less than volatility_threshold_high ({self.config.volatility_threshold_high})"
            )

        # Validate frontend polling parameters
        if self.config.ws_connected_poll_interval_ms <= 0:
            errors.append("ws_connected_poll_interval_ms must be positive")

        if self.config.ws_disconnected_poll_interval_ms <= 0:
            errors.append("ws_disconnected_poll_interval_ms must be positive")

        if self.config.rest_backoff_multiplier < 1.0:
            errors.append("rest_backoff_multiplier must be >= 1.0")

        if self.config.rest_max_backoff_ms <= 0:
            errors.append("rest_max_backoff_ms must be positive")

        # Validate tier policies
        for tier_name, policy in self.config.memory.tier_policies.items():
            if policy.max_candles <= 0:
                errors.append(f"tier_policies[{tier_name}].max_candles must be positive")
            if policy.retention_seconds <= 0:
                errors.append(f"tier_policies[{tier_name}].retention_seconds must be positive")

        # If any errors, raise with all error messages
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ConfigurationError(error_msg)

    def _log_configuration(self) -> None:
        """Log all active configuration values at startup."""
        logger.info("=" * 60)
        logger.info("Realtime Updates System Configuration")
        logger.info("=" * 60)

        if self.config_path:
            logger.info(f"Configuration file: {self.config_path}")
        else:
            logger.info("Configuration: Using defaults with environment overrides")

        logger.info("")
        logger.info("Batching Configuration:")
        logger.info(f"  batch_window_ms: {self.config.batch_window_ms}")
        logger.info(f"  max_batch_size: {self.config.max_batch_size}")
        logger.info(f"  enable_batching: {self.config.enable_batching}")

        logger.info("")
        logger.info("Rate Limiting Configuration:")
        logger.info(f"  max_messages_per_second: {self.config.max_messages_per_second}")
        logger.info(f"  burst_size: {self.config.burst_size}")
        logger.info(f"  critical_bypass: {self.config.critical_bypass}")

        logger.info("")
        logger.info("Prioritization Configuration:")
        logger.info(f"  price_change_threshold: {self.config.price_change_threshold}")
        logger.info(f"  volume_spike_multiplier: {self.config.volume_spike_multiplier}")
        logger.info(f"  critical_event_types: {self.config.critical_event_types}")

        logger.info("")
        logger.info("Memory Management Configuration:")
        logger.info(f"  max_candles_per_market: {self.config.max_candles_per_market}")
        logger.info(f"  retention_seconds: {self.config.retention_seconds}")
        if self.config.memory.tier_policies:
            logger.info("  tier_policies:")
            for tier, policy in self.config.memory.tier_policies.items():
                logger.info(f"    {tier}: max_candles={policy.max_candles}, "
                          f"retention_seconds={policy.retention_seconds}")

        logger.info("")
        logger.info("Backpressure Configuration:")
        logger.info(f"  send_buffer_threshold: {self.config.send_buffer_threshold}")
        logger.info(f"  slow_client_timeout: {self.config.slow_client_timeout}")
        logger.info(f"  drop_non_critical_for_slow: {self.config.drop_non_critical_for_slow}")

        logger.info("")
        logger.info("Concurrency Configuration:")
        logger.info(f"  worker_pool_size: {self.config.worker_pool_size}")
        logger.info(f"  max_concurrent_markets: {self.config.max_concurrent_markets}")

        logger.info("")
        logger.info("Signal Cooldown Configuration:")
        logger.info(f"  min_signal_cooldown_seconds: {self.config.min_signal_cooldown_seconds}")
        logger.info(f"  max_signal_cooldown_seconds: {self.config.max_signal_cooldown_seconds}")
        logger.info(f"  volatility_window_seconds: {self.config.volatility_window_seconds}")
        logger.info(f"  volatility_threshold_low: {self.config.volatility_threshold_low}")
        logger.info(f"  volatility_threshold_high: {self.config.volatility_threshold_high}")

        logger.info("")
        logger.info("Frontend Polling Configuration:")
        logger.info(f"  ws_connected_poll_interval_ms: {self.config.ws_connected_poll_interval_ms}")
        logger.info(f"  ws_disconnected_poll_interval_ms: {self.config.ws_disconnected_poll_interval_ms}")
        logger.info(f"  rest_backoff_multiplier: {self.config.rest_backoff_multiplier}")
        logger.info(f"  rest_max_backoff_ms: {self.config.rest_max_backoff_ms}")

        logger.info("=" * 60)

    # Getter methods for component configs

    def get_batcher_config(self) -> BatcherConfig:
        """Get configuration for MessageBatcher component.
        
        Returns:
            BatcherConfig instance.
        """
        return self.config.batcher

    def get_rate_limiter_config(self) -> RateLimiterConfig:
        """Get configuration for RateLimiter component.
        
        Returns:
            RateLimiterConfig instance.
        """
        return self.config.rate_limiter

    def get_memory_config(self) -> MemoryConfig:
        """Get configuration for MemoryManager component.
        
        Returns:
            MemoryConfig instance.
        """
        return self.config.memory

    def get_prioritizer_config(self) -> PrioritizerConfig:
        """Get configuration for UpdatePrioritizer component.
        
        Returns:
            PrioritizerConfig instance.
        """
        return self.config.prioritizer

    def get_backpressure_config(self) -> BackpressureConfig:
        """Get configuration for BackpressureHandler component.
        
        Returns:
            BackpressureConfig instance.
        """
        return self.config.backpressure

    def get_system_config(self) -> SystemConfig:
        """Get complete system configuration.
        
        Returns:
            SystemConfig instance.
        """
        return self.config
