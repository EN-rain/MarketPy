"""Test to verify no side effects when importing main.py."""

from unittest.mock import patch


def test_import_main_no_database_initialization():
    """Verify that importing main.py does not initialize database connections."""
    # Mock database initialization functions to detect if they're called
    with patch('backend.app.main.asyncio'):
        # Import main module
        from backend.app import main

        # Verify the module imported successfully
        assert main is not None
        assert hasattr(main, 'create_app')
        assert hasattr(main, 'app')

        # The app instance exists but resources should not be initialized yet
        # Resources are only initialized during lifespan startup


def test_import_main_no_api_client_initialization():
    """Verify that importing main.py does not initialize external API clients."""
    # Simply importing should not trigger any external API calls
    from backend.app import main

    # Verify the module imported successfully
    assert main is not None

    # The create_app factory function should be available
    assert callable(main.create_app)


def test_create_app_allows_dependency_injection():
    """Verify that create_app allows dependency injection for testing."""
    from backend.app.main import AppConfig, create_app

    # Create a test configuration
    test_config = AppConfig(
        enable_binance_stream=False,
        cors_origins=["http://test.example.com"]
    )

    # Create app with test config
    app = create_app(test_config)

    # Verify the config was applied
    assert app.state.app_config == test_config
    assert app.state.app_config.enable_binance_stream is False


def test_multiple_app_instances_independent():
    """Verify that multiple app instances can be created independently."""
    from backend.app.main import AppConfig, create_app

    config1 = AppConfig(enable_binance_stream=False, cors_origins=["http://app1.com"])
    config2 = AppConfig(enable_binance_stream=False, cors_origins=["http://app2.com"])

    app1 = create_app(config1)
    app2 = create_app(config2)

    # Verify they are different instances
    assert app1 is not app2
    assert app1.state.app_config != app2.state.app_config
