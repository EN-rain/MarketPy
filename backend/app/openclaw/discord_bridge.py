"""Discord bridge with authorization, routing, and response formatting."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any, Protocol
from uuid import uuid4

from .config import DiscordSettings
from .logging import StructuredLogger, correlation_context


class PermissionLevel(IntEnum):
    VIEWER = 1
    TRADER = 2
    ADMIN = 3


@dataclass(slots=True)
class DiscordMessage:
    user_id: str
    channel_id: str
    content: str
    message_id: str = field(default_factory=lambda: f"msg-{uuid4().hex[:12]}")
    username: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuthorizationResult:
    allowed: bool
    reason: str | None = None
    level: PermissionLevel = PermissionLevel.VIEWER


class BotAdapter(Protocol):
    async def connect(self, token: str) -> None: ...

    async def disconnect(self) -> None: ...

    async def send(
        self,
        channel_id: str,
        content: str,
        embeds: list[dict[str, Any]] | None = None,
        reactions: list[str] | None = None,
    ) -> None: ...


class InMemoryBotAdapter:
    """Test-friendly adapter that stores outgoing messages in-memory."""

    def __init__(self) -> None:
        self.connected: bool = False
        self.sent_messages: list[dict[str, Any]] = []

    async def connect(self, token: str) -> None:
        if not token:
            raise ValueError("Discord token is required")
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def send(
        self,
        channel_id: str,
        content: str,
        embeds: list[dict[str, Any]] | None = None,
        reactions: list[str] | None = None,
    ) -> None:
        self.sent_messages.append(
            {
                "channel_id": channel_id,
                "content": content,
                "embeds": embeds or [],
                "reactions": reactions or [],
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )


class AuthorizationManager:
    """Permission model for Discord user access control."""

    def __init__(self, authorized_users: list[str] | None = None):
        self._users: dict[str, PermissionLevel] = {
            user_id: PermissionLevel.TRADER for user_id in (authorized_users or [])
        }

    def set_permission(self, user_id: str, level: PermissionLevel) -> None:
        self._users[user_id] = level

    def remove_user(self, user_id: str) -> None:
        self._users.pop(user_id, None)

    def check(
        self, user_id: str, minimum: PermissionLevel = PermissionLevel.VIEWER
    ) -> AuthorizationResult:
        level = self._users.get(user_id)
        if level is None:
            return AuthorizationResult(allowed=False, reason="User is not authorized")
        if level < minimum:
            return AuthorizationResult(
                allowed=False,
                reason=f"Permission denied, requires {minimum.name.lower()}",
                level=level,
            )
        return AuthorizationResult(allowed=True, level=level)

    def list_users(self) -> dict[str, str]:
        return {user_id: level.name.lower() for user_id, level in self._users.items()}


class ErrorMessageFormatter:
    """Formats user-facing OpenClaw errors with hints and references."""

    @staticmethod
    def format_error(error_type: str, brief: str, details: str, suggestion: str) -> str:
        ref = f"ERR-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
        return (
            f"❌ {error_type}: {brief}\n\n"
            f"Details: {details}\n"
            f"Suggestion: {suggestion}\n"
            f"Reference: {ref}"
        )

    @classmethod
    def parsing_error(cls, details: str) -> str:
        return cls.format_error(
            error_type="Parsing Error",
            brief="Could not parse your command",
            details=details,
            suggestion="Try examples like: `Check BTC price` or `Buy 0.1 BTC`.",
        )

    @classmethod
    def api_error(cls, details: str) -> str:
        return cls.format_error(
            error_type="API Error",
            brief="Upstream service failed",
            details=details,
            suggestion="Retry in a few seconds; if persistent, check `/health`.",
        )

    @classmethod
    def risk_violation(cls, details: str) -> str:
        return cls.format_error(
            error_type="Risk Violation",
            brief="Command blocked by risk limits",
            details=details,
            suggestion="Reduce size, lower leverage, or close existing positions first.",
        )


class DiscordBridge:
    """Connects Discord message flow to OpenClaw command handling."""

    def __init__(
        self,
        settings: DiscordSettings,
        *,
        logger: StructuredLogger | None = None,
        authorization_manager: AuthorizationManager | None = None,
        bot_adapter: BotAdapter | None = None,
        error_formatter: ErrorMessageFormatter | None = None,
    ):
        self._settings = settings
        self._logger = logger or StructuredLogger("openclaw.discord_bridge")
        self._authorization = authorization_manager or AuthorizationManager(
            settings.authorized_users
        )
        self._bot = bot_adapter or InMemoryBotAdapter()
        self._error_formatter = error_formatter or ErrorMessageFormatter()
        self._handler: Callable[[DiscordMessage], Awaitable[str | dict[str, Any]]] | None = None
        self._lock = asyncio.Lock()

    def register_command_handler(
        self,
        handler: Callable[[DiscordMessage], Awaitable[str | dict[str, Any]]],
    ) -> None:
        self._handler = handler

    @property
    def authorization_manager(self) -> AuthorizationManager:
        return self._authorization

    async def start(self) -> None:
        await self._bot.connect(self._settings.bot_token)
        self._logger.info("Discord bridge connected")

    async def stop(self) -> None:
        await self._bot.disconnect()
        self._logger.info("Discord bridge disconnected")

    async def handle_message(self, message: DiscordMessage) -> None:
        async with self._lock:
            with correlation_context():
                if (
                    self._settings.command_channels
                    and message.channel_id not in self._settings.command_channels
                ):
                    self._logger.debug(
                        "Ignoring message outside configured channels",
                        {"channel_id": message.channel_id},
                    )
                    return

                auth = self._authorization.check(message.user_id, minimum=PermissionLevel.VIEWER)
                self._logger.info(
                    "Authorization check completed",
                    {"user_id": message.user_id, "allowed": auth.allowed, "reason": auth.reason},
                )
                if not auth.allowed:
                    await self.send_message(
                        message.channel_id,
                        self._error_formatter.format_error(
                            "Authorization",
                            "Permission denied",
                            auth.reason or "User is not authorized.",
                            "Request access from an admin user.",
                        ),
                    )
                    return

                if self._handler is None:
                    await self.send_message(
                        message.channel_id,
                        self._error_formatter.api_error("No command handler registered."),
                    )
                    return

                try:
                    result = await self._handler(message)
                    if isinstance(result, dict):
                        await self.send_message(
                            message.channel_id,
                            str(result.get("content", "")),
                            embeds=result.get("embeds"),
                            reactions=result.get("reactions"),
                        )
                    else:
                        await self.send_message(message.channel_id, str(result))
                except Exception as exc:
                    self._logger.exception("Discord message handling failed", {"error": str(exc)})
                    await self.send_message(
                        message.channel_id,
                        self._error_formatter.api_error(str(exc)),
                    )

    async def send_message(
        self,
        channel_id: str,
        content: str,
        *,
        embeds: list[dict[str, Any]] | None = None,
        reactions: list[str] | None = None,
    ) -> None:
        await self._bot.send(channel_id, content, embeds=embeds, reactions=reactions)

    @staticmethod
    def create_embed(
        title: str, description: str, fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "title": title,
            "description": description,
            "fields": [
                {"name": key, "value": str(value), "inline": True}
                for key, value in (fields or {}).items()
            ],
            "timestamp": datetime.now(UTC).isoformat(),
        }
