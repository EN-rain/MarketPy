from __future__ import annotations

import pytest

from backend.app.openclaw.config import DiscordSettings
from backend.app.openclaw.discord_bridge import (
    AuthorizationManager,
    DiscordBridge,
    DiscordMessage,
    InMemoryBotAdapter,
    PermissionLevel,
)


@pytest.mark.asyncio
async def test_discord_bridge_routes_authorized_message() -> None:
    bot = InMemoryBotAdapter()
    settings = DiscordSettings(bot_token="token", authorized_users=["u1"], command_channels=["c1"])
    bridge = DiscordBridge(settings, bot_adapter=bot)

    async def handler(message: DiscordMessage) -> str:
        return f"ok:{message.content}"

    bridge.register_command_handler(handler)
    await bridge.start()
    await bridge.handle_message(DiscordMessage(user_id="u1", channel_id="c1", content="hello"))
    await bridge.stop()

    assert bot.sent_messages
    assert "ok:hello" in bot.sent_messages[-1]["content"]


@pytest.mark.asyncio
async def test_discord_bridge_blocks_unauthorized_user() -> None:
    bot = InMemoryBotAdapter()
    settings = DiscordSettings(bot_token="token", authorized_users=["u1"], command_channels=["c1"])
    bridge = DiscordBridge(settings, bot_adapter=bot)
    await bridge.start()
    await bridge.handle_message(DiscordMessage(user_id="u2", channel_id="c1", content="buy btc"))
    await bridge.stop()
    assert "Permission denied" in bot.sent_messages[-1]["content"]


def test_authorization_permission_levels() -> None:
    manager = AuthorizationManager(["u1"])
    manager.set_permission("admin", PermissionLevel.ADMIN)
    assert manager.check("u1", PermissionLevel.VIEWER).allowed is True
    assert manager.check("u1", PermissionLevel.ADMIN).allowed is False
    assert manager.check("admin", PermissionLevel.ADMIN).allowed is True
