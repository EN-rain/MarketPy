"""Tests for the application factory pattern."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app


def test_create_app_with_default_config():
    """Test creating app with default configuration."""
    app = create_app()

    assert app is not None
    assert app.title == "MarketPy - Crypto Trading Simulator"
    assert hasattr(app.state, 'app_config')
    assert isinstance(app.state.app_config, AppConfig)


def test_create_app_with_custom_config():
    """Test creating app with custom configuration."""
    custom_config = AppConfig(
        enable_binance_stream=False,
        cors_origins=["http://test.example.com"]
    )
    app = create_app(custom_config)

    assert app is not None
    assert app.state.app_config == custom_config
    assert app.state.app_config.enable_binance_stream is False
    assert app.state.app_config.cors_origins == ["http://test.example.com"]


def test_app_initialization_deferred():
    """Test that resources are not initialized at import time."""
    # Simply importing main should not initialize resources
    from backend.app import main

    # The app is created but resources are initialized in lifespan
    assert main.app is not None


def test_app_can_be_tested_without_binance():
    """Test that app can be created for testing without Binance stream."""
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)

    # Create test client - this will trigger lifespan startup
    with TestClient(app):
        # Verify app state is initialized
        assert hasattr(app.state, 'app_state')
        assert hasattr(app.state, 'ws_manager')
        assert hasattr(app.state, 'realtime_services')

        # Verify binance client is None when disabled
        assert app.state.binance_client is None


def test_dependency_injection_for_config_manager():
    """Test that ConfigManager can be injected for testing."""
    from backend.app.config_manager import ConfigManager

    custom_config_manager = ConfigManager()
    test_config = AppConfig(
        config_manager=custom_config_manager,
        enable_binance_stream=False
    )
    app = create_app(test_config)

    with TestClient(app):
        # Verify the custom config manager is used
        assert app.state.realtime_services['config_manager'] == custom_config_manager


def test_multiple_app_instances():
    """Test that multiple app instances can be created independently."""
    config1 = AppConfig(enable_binance_stream=False, cors_origins=["http://app1.com"])
    config2 = AppConfig(enable_binance_stream=False, cors_origins=["http://app2.com"])

    app1 = create_app(config1)
    app2 = create_app(config2)

    assert app1 is not app2
    assert app1.state.app_config != app2.state.app_config
    assert app1.state.app_config.cors_origins == ["http://app1.com"]
    assert app2.state.app_config.cors_origins == ["http://app2.com"]
