from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.openclaw.autonomous_agent import AutonomousAgent
from backend.app.openclaw.config import OpenClawConfigManager
from backend.app.openclaw.discord_bridge import DiscordMessage
from backend.app.openclaw.models import CommandType, ExecutionResult, TradingCommand


@pytest.mark.asyncio
async def test_autonomous_agent_start_health_stop(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "data_dir": str(tmp_path / "data"),
                "log_file": str(tmp_path / "openclaw.log"),
                "discord": {"bot_token": "token", "authorized_users": ["u1"]},
                "kimi_k2": {"api_key": "key"},
            }
        ),
        encoding="utf-8",
    )
    manager = OpenClawConfigManager(config_path=config_path)
    agent = AutonomousAgent(config_manager=manager, exchange_client=None)
    await agent.start()
    health = agent.health_check()
    assert health["status"] == "healthy"
    await agent.stop()
    assert agent.health_check()["status"] == "stopped"


@pytest.mark.asyncio
async def test_autonomous_agent_processes_queued_commands(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "data_dir": str(tmp_path / "data"),
                "log_file": str(tmp_path / "openclaw.log"),
                "discord": {"bot_token": "token", "authorized_users": ["u1"]},
                "kimi_k2": {"api_key": "key"},
                "performance": {"max_concurrent_users": 2, "max_queue_size": 10},
            }
        ),
        encoding="utf-8",
    )
    manager = OpenClawConfigManager(config_path=config_path)
    agent = AutonomousAgent(config_manager=manager, exchange_client=None)

    async def fake_parse(message: str, user_id: str):  # type: ignore[override]
        return TradingCommand(
            command_type=CommandType.POSITION_QUERY,
            user_id=user_id,
        )

    async def fake_execute(command, **kwargs):  # type: ignore[override]
        return ExecutionResult(success=True, data={"ok": True}, execution_time_ms=1.0)

    agent.nlp.parse_command = fake_parse  # type: ignore[assignment]
    agent.command_executor.execute = fake_execute  # type: ignore[assignment]

    await agent.start()
    await agent.enqueue_message(DiscordMessage(user_id="u1", channel_id="c1", content="positions"))
    await agent.enqueue_message(DiscordMessage(user_id="u1", channel_id="c1", content="positions"))
    await agent._command_queue.join()  # noqa: SLF001
    metrics = agent.metrics.snapshot()
    assert metrics["counters"]["openclaw_commands_total"] >= 2
    await agent.stop()
