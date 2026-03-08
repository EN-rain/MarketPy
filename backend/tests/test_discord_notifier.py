"""Tests for DiscordNotifier."""

from __future__ import annotations

import pytest
from httpx import AsyncBaseTransport, Request, Response

from backend.app.integrations.discord_notifier import (
    DiscordNotifier,
    DiscordNotifierConfig,
    NotificationCategory,
)


class _OkTransport(AsyncBaseTransport):
    async def handle_async_request(self, request: Request) -> Response:
        return Response(status_code=204)


@pytest.mark.asyncio
async def test_discord_notifier_sends_message() -> None:
    notifier = DiscordNotifier(
        DiscordNotifierConfig(
            webhook_url="https://discord.example/webhook",
            rate_limit_per_minute=10,
        ),
        transport=_OkTransport(),
    )
    ok = await notifier.send(
        category=NotificationCategory.INFO,
        component="test",
        message="hello",
        metrics={"a": 1},
    )
    await notifier.close()
    assert ok is True


@pytest.mark.asyncio
async def test_discord_notifier_rate_limit() -> None:
    notifier = DiscordNotifier(
        DiscordNotifierConfig(
            webhook_url="https://discord.example/webhook",
            rate_limit_per_minute=1,
        ),
        transport=_OkTransport(),
    )
    first = await notifier.send(NotificationCategory.INFO, "test", "one")
    second = await notifier.send(NotificationCategory.INFO, "test", "two")
    await notifier.close()
    assert first is True
    assert second is False
