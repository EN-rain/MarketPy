"""Unit tests for ConfigManager.

Tests cover:
- Configuration loading from file
- Environment variable overrides
- Validation of all parameters
- Range checks (e.g., min < max)
- Error handling for invalid configurations
- Default value handling
- Getter methods for component configs
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from backend.app.config_manager import ConfigManager, ConfigurationError
from backend.app.models.realtime_config import (
    BackpressureConfig,
    BatcherConfig,
    MemoryConfig,
    PrioritizerConfig,
    RateLimiterConfig,
    SystemConfig,
)


class TestConfigManagerLoading:
    """Test configuration loading from files and environment variables."""

    def test_load_default_config_no_file(self):
        """Test loading default configuration when no file is provided."""
        config_manager = ConfigManager()

        assert config_manager.config is not None
        assert isinstance(config_manager.config, SystemConfig)
        assert config_manager.config.batch_window_ms == 100  # default value
        assert config_manager.config.max_batch_size == 50  # default value

    def test_load_config_from_file(self):
        """Test loading configuration from a JSON file."""
        config_data = {
            "batch_window_ms": 200,
            "max_batch_size": 100,
            "max_messages_per_second": 20,
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config_manager = ConfigManager(config_path=temp_path)

            assert config_manager.config.batch_window_ms == 200
            assert config_manager.config.max_batch_size == 100
            assert config_manager.config.max_messages_per_second == 20
        finally:
            os.unlink(temp_path)

    def test_load_config_file_not_found(self):
        """Test error handling when configuration file doesn't exist."""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            ConfigManager(config_path="/nonexistent/config.json")

    def test_load_config_invalid_json(self):
        """Test error handling for invalid JSON in configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="Invalid JSON"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_env_var_override_int(self):
        """Test environment variable override for integer parameter."""
        with patch.dict(os.environ, {'REALTIME_BATCH_WINDOW_MS': '500'}):
            config_manager = ConfigManager()
            assert config_manager.config.batch_window_ms == 500

    def test_env_var_override_float(self):
        """Test environment variable override for float parameter."""
        with patch.dict(os.environ, {'REALTIME_PRICE_CHANGE_THRESHOLD': '0.05'}):
            config_manager = ConfigManager()
            assert config_manager.config.price_change_threshold == 0.05

    def test_env_var_override_bool_true(self):
        """Test environment variable override for boolean parameter (true values)."""
        for true_value in ['true', 'True', '1', 'yes', 'YES', 'on']:
            with patch.dict(os.environ, {'REALTIME_ENABLE_BATCHING': true_value}):
                config_manager = ConfigManager()
                assert config_manager.config.enable_batching is True

    def test_env_var_override_bool_false(self):
        """Test environment variable override for boolean parameter (false values)."""
        for false_value in ['false', 'False', '0', 'no', 'NO', 'off']:
            with patch.dict(os.environ, {'REALTIME_ENABLE_BATCHING': false_value}):
                config_manager = ConfigManager()
                assert config_manager.config.enable_batching is False

    def test_env_var_override_invalid_value(self):
        """Test that invalid environment variable values are ignored with warning."""
        with patch.dict(os.environ, {'REALTIME_BATCH_WINDOW_MS': 'invalid'}):
            # Should not raise, but use default value
            config_manager = ConfigManager()
            assert config_manager.config.batch_window_ms == 100  # default

    def test_env_var_precedence_over_file(self):
        """Test that environment variables take precedence over file values."""
        config_data = {"batch_window_ms": 200}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {'REALTIME_BATCH_WINDOW_MS': '300'}):
                config_manager = ConfigManager(config_path=temp_path)
                assert config_manager.config.batch_window_ms == 300  # env var wins
        finally:
            os.unlink(temp_path)

    def test_load_config_with_tier_policies(self):
        """Test loading configuration with tier-based retention policies."""
        config_data = {
            "tier_policies": {
                "high_volume": {
                    "max_candles": 2000,
                    "retention_seconds": 172800
                },
                "low_volume": {
                    "max_candles": 500,
                    "retention_seconds": 43200
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config_manager = ConfigManager(config_path=temp_path)

            assert "high_volume" in config_manager.config.memory.tier_policies
            assert "low_volume" in config_manager.config.memory.tier_policies

            high_vol = config_manager.config.memory.tier_policies["high_volume"]
            assert high_vol.max_candles == 2000
            assert high_vol.retention_seconds == 172800

            low_vol = config_manager.config.memory.tier_policies["low_volume"]
            assert low_vol.max_candles == 500
            assert low_vol.retention_seconds == 43200
        finally:
            os.unlink(temp_path)

    def test_load_config_with_critical_event_types_string(self):
        """Test loading critical_event_types as comma-separated string."""
        config_data = {
            "critical_event_types": "order_fill, trade_execution, liquidation"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config_manager = ConfigManager(config_path=temp_path)

            assert config_manager.config.critical_event_types == [
                "order_fill", "trade_execution", "liquidation"
            ]
        finally:
            os.unlink(temp_path)


class TestConfigManagerValidation:
    """Test configuration validation and range checks."""

    def test_validation_batch_window_negative(self):
        """Test validation fails for negative batch_window_ms."""
        config_data = {"batch_window_ms": -100}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="batch_window_ms must be positive"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_batch_window_too_large(self):
        """Test validation fails for batch_window_ms exceeding maximum."""
        config_data = {"batch_window_ms": 15000}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="batch_window_ms must not exceed 10000ms"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_max_batch_size_negative(self):
        """Test validation fails for negative max_batch_size."""
        config_data = {"max_batch_size": -10}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="max_batch_size must be positive"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_burst_size_less_than_rate(self):
        """Test validation fails when burst_size < max_messages_per_second."""
        config_data = {
            "max_messages_per_second": 20,
            "burst_size": 10
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="burst_size must be >= max_messages_per_second"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_price_change_threshold_negative(self):
        """Test validation fails for negative price_change_threshold."""
        config_data = {"price_change_threshold": -0.1}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="price_change_threshold must be non-negative"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_price_change_threshold_too_large(self):
        """Test validation fails for price_change_threshold > 1.0."""
        config_data = {"price_change_threshold": 1.5}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="price_change_threshold must not exceed 1.0"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_volume_spike_multiplier_less_than_one(self):
        """Test validation fails for volume_spike_multiplier < 1.0."""
        config_data = {"volume_spike_multiplier": 0.5}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="volume_spike_multiplier must be >= 1.0"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_min_cooldown_greater_than_max(self):
        """Test validation fails when min_signal_cooldown >= max_signal_cooldown."""
        config_data = {
            "min_signal_cooldown_seconds": 30.0,
            "max_signal_cooldown_seconds": 10.0
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="min_signal_cooldown_seconds.*must be less than max_signal_cooldown_seconds"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_min_cooldown_equal_to_max(self):
        """Test validation fails when min_signal_cooldown == max_signal_cooldown."""
        config_data = {
            "min_signal_cooldown_seconds": 10.0,
            "max_signal_cooldown_seconds": 10.0
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="min_signal_cooldown_seconds.*must be less than max_signal_cooldown_seconds"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_volatility_threshold_low_greater_than_high(self):
        """Test validation fails when volatility_threshold_low >= volatility_threshold_high."""
        config_data = {
            "volatility_threshold_low": 0.05,
            "volatility_threshold_high": 0.02
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="volatility_threshold_low.*must be less than volatility_threshold_high"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_worker_pool_size_negative(self):
        """Test validation fails for negative worker_pool_size."""
        config_data = {"worker_pool_size": -5}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="worker_pool_size must be positive"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_worker_pool_size_too_large(self):
        """Test validation fails for worker_pool_size > 100."""
        config_data = {"worker_pool_size": 150}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="worker_pool_size must not exceed 100"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_tier_policy_invalid_max_candles(self):
        """Test validation fails for tier policy with invalid max_candles."""
        config_data = {
            "tier_policies": {
                "test_tier": {
                    "max_candles": -100,
                    "retention_seconds": 3600
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="tier_policies.*max_candles must be positive"):
                ConfigManager(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_validation_multiple_errors(self):
        """Test that multiple validation errors are reported together."""
        config_data = {
            "batch_window_ms": -100,
            "max_batch_size": -50,
            "min_signal_cooldown_seconds": 30.0,
            "max_signal_cooldown_seconds": 10.0
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigManager(config_path=temp_path)

            error_msg = str(exc_info.value)
            assert "batch_window_ms must be positive" in error_msg
            assert "max_batch_size must be positive" in error_msg
            assert "min_signal_cooldown_seconds" in error_msg
            assert "max_signal_cooldown_seconds" in error_msg
        finally:
            os.unlink(temp_path)

    def test_validation_passes_with_valid_config(self):
        """Test that validation passes with all valid parameters."""
        config_data = {
            "batch_window_ms": 150,
            "max_batch_size": 75,
            "max_messages_per_second": 15,
            "burst_size": 30,
            "price_change_threshold": 0.03,
            "volume_spike_multiplier": 2.5,
            "min_signal_cooldown_seconds": 2.0,
            "max_signal_cooldown_seconds": 20.0,
            "volatility_threshold_low": 0.01,
            "volatility_threshold_high": 0.05,
            "worker_pool_size": 15,
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            # Should not raise
            config_manager = ConfigManager(config_path=temp_path)
            assert config_manager.config is not None
        finally:
            os.unlink(temp_path)


class TestConfigManagerGetters:
    """Test getter methods for component configurations."""

    def test_get_batcher_config(self):
        """Test get_batcher_config returns correct BatcherConfig."""
        config_manager = ConfigManager()
        batcher_config = config_manager.get_batcher_config()

        assert isinstance(batcher_config, BatcherConfig)
        assert batcher_config.batch_window_ms == config_manager.config.batch_window_ms
        assert batcher_config.max_batch_size == config_manager.config.max_batch_size
        assert batcher_config.enable_batching == config_manager.config.enable_batching

    def test_get_rate_limiter_config(self):
        """Test get_rate_limiter_config returns correct RateLimiterConfig."""
        config_manager = ConfigManager()
        rate_limiter_config = config_manager.get_rate_limiter_config()

        assert isinstance(rate_limiter_config, RateLimiterConfig)
        assert rate_limiter_config.max_messages_per_second == config_manager.config.max_messages_per_second
        assert rate_limiter_config.burst_size == config_manager.config.burst_size
        assert rate_limiter_config.critical_bypass == config_manager.config.critical_bypass

    def test_get_memory_config(self):
        """Test get_memory_config returns correct MemoryConfig."""
        config_manager = ConfigManager()
        memory_config = config_manager.get_memory_config()

        assert isinstance(memory_config, MemoryConfig)
        assert memory_config.max_candles_per_market == config_manager.config.max_candles_per_market
        assert memory_config.retention_seconds == config_manager.config.retention_seconds

    def test_get_prioritizer_config(self):
        """Test get_prioritizer_config returns correct PrioritizerConfig."""
        config_manager = ConfigManager()
        prioritizer_config = config_manager.get_prioritizer_config()

        assert isinstance(prioritizer_config, PrioritizerConfig)
        assert prioritizer_config.price_change_threshold == config_manager.config.price_change_threshold
        assert prioritizer_config.volume_spike_multiplier == config_manager.config.volume_spike_multiplier
        assert prioritizer_config.critical_event_types == config_manager.config.critical_event_types

    def test_get_backpressure_config(self):
        """Test get_backpressure_config returns correct BackpressureConfig."""
        config_manager = ConfigManager()
        backpressure_config = config_manager.get_backpressure_config()

        assert isinstance(backpressure_config, BackpressureConfig)
        assert backpressure_config.send_buffer_threshold == config_manager.config.send_buffer_threshold
        assert backpressure_config.slow_client_timeout == config_manager.config.slow_client_timeout
        assert backpressure_config.drop_non_critical_for_slow == config_manager.config.drop_non_critical_for_slow

    def test_get_system_config(self):
        """Test get_system_config returns complete SystemConfig."""
        config_manager = ConfigManager()
        system_config = config_manager.get_system_config()

        assert isinstance(system_config, SystemConfig)
        assert system_config is config_manager.config


class TestConfigManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_config_file(self):
        """Test loading from empty configuration file uses defaults."""
        config_data = {}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config_manager = ConfigManager(config_path=temp_path)

            # Should use all default values
            assert config_manager.config.batch_window_ms == 100
            assert config_manager.config.max_batch_size == 50
        finally:
            os.unlink(temp_path)

    def test_partial_config_file(self):
        """Test loading partial configuration merges with defaults."""
        config_data = {
            "batch_window_ms": 250,
            # Other fields should use defaults
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config_manager = ConfigManager(config_path=temp_path)

            assert config_manager.config.batch_window_ms == 250  # from file
            assert config_manager.config.max_batch_size == 50  # default
        finally:
            os.unlink(temp_path)

    def test_config_at_boundary_values(self):
        """Test configuration with values at exact boundaries."""
        config_data = {
            "batch_window_ms": 1,  # minimum positive
            "max_batch_size": 1,  # minimum positive
            "price_change_threshold": 0.0,  # minimum
            "volume_spike_multiplier": 1.0,  # minimum
            "min_signal_cooldown_seconds": 0.1,
            "max_signal_cooldown_seconds": 0.2,  # just above min
            "volatility_threshold_low": 0.0,
            "volatility_threshold_high": 0.001,  # just above low
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            # Should not raise
            config_manager = ConfigManager(config_path=temp_path)
            assert config_manager.config.batch_window_ms == 1
        finally:
            os.unlink(temp_path)

    def test_parse_bool_invalid_value(self):
        """Test _parse_bool raises ValueError for invalid boolean string."""
        with pytest.raises(ValueError, match="Cannot parse"):
            ConfigManager._parse_bool("maybe")
