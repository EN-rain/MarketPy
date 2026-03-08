from __future__ import annotations

from backend.app.models.config import FillModelLevel, load_settings


def test_load_settings_uses_dev_yaml_by_default(monkeypatch) -> None:
    monkeypatch.delenv("MARKETPY_ENV", raising=False)
    settings = load_settings()

    assert settings.environment == "dev"
    assert settings.backend_port == 8000
    assert settings.fill_model == FillModelLevel.M2_BIDASK
    assert settings.exchanges["binance"]["api_url"] == "https://api.binance.com"


def test_load_settings_reads_environment_specific_yaml(monkeypatch) -> None:
    monkeypatch.setenv("MARKETPY_ENV", "prod")
    settings = load_settings()

    assert settings.environment == "prod"
    assert settings.cors_origins == ["https://marketpy.example.com"]


def test_load_settings_allows_env_override(monkeypatch) -> None:
    monkeypatch.setenv("MARKETPY_ENV", "dev")
    monkeypatch.setenv("BACKEND_PORT", "9000")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3100"]')
    settings = load_settings()

    assert settings.backend_port == 9000
    assert settings.cors_origins == ["http://localhost:3100"]
