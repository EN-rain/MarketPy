from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.openclaw.config import OpenClawConfigManager, OpenClawConfigurationError


def test_config_manager_loads_from_file_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "discord": {"bot_token": "file-token", "authorized_users": ["u1"]},
                "kimi_k2": {"api_key": "file-key"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLAW_DISCORD_BOT_TOKEN", "env-token")
    manager = OpenClawConfigManager(config_path=config_path)
    assert manager.config.discord.bot_token == "env-token"
    assert manager.config.kimi_k2.api_key == "file-key"


def test_config_manager_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(OpenClawConfigurationError):
        OpenClawConfigManager(config_path=config_path)


def test_runtime_update_allows_only_non_critical(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "discord": {"bot_token": "t", "authorized_users": ["u1"]},
                "kimi_k2": {"api_key": "k"},
            }
        ),
        encoding="utf-8",
    )
    manager = OpenClawConfigManager(config_path=config_path)
    manager.update_runtime({"monitoring.market_monitor_interval_seconds": 15})
    assert manager.config.monitoring.market_monitor_interval_seconds == 15
    with pytest.raises(OpenClawConfigurationError):
        manager.update_runtime({"discord.bot_token": "x"})
