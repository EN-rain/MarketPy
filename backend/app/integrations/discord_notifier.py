"""Discord notification integration for system/trade/risk events."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NotificationCategory(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    TRADE = "TRADE"
    RISK = "RISK"
    SYSTEM = "SYSTEM"


_COLOR_BY_CATEGORY: dict[NotificationCategory, int] = {
    NotificationCategory.ERROR: 0xE74C3C,
    NotificationCategory.WARNING: 0xF39C12,
    NotificationCategory.INFO: 0x3498DB,
    NotificationCategory.TRADE: 0x2ECC71,
    NotificationCategory.RISK: 0xE67E22,
    NotificationCategory.SYSTEM: 0x9B59B6,
}


@dataclass(slots=True)
class DiscordNotifierConfig:
    webhook_url: str | None = None
    enabled_categories: set[NotificationCategory] = field(
        default_factory=lambda: {
            NotificationCategory.ERROR,
            NotificationCategory.WARNING,
            NotificationCategory.INFO,
            NotificationCategory.TRADE,
            NotificationCategory.RISK,
            NotificationCategory.SYSTEM,
        }
    )
    rate_limit_per_minute: int = 10
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> DiscordNotifierConfig:
        categories_raw = os.getenv("DISCORD_ENABLED_CATEGORIES", "")
        if categories_raw.strip():
            parsed = {
                NotificationCategory[item.strip().upper()]
                for item in categories_raw.split(",")
                if item.strip().upper() in NotificationCategory.__members__
            }
        else:
            parsed = {
                NotificationCategory.ERROR,
                NotificationCategory.WARNING,
                NotificationCategory.INFO,
                NotificationCategory.TRADE,
                NotificationCategory.RISK,
                NotificationCategory.SYSTEM,
            }
        return cls(
            webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
            enabled_categories=parsed,
            rate_limit_per_minute=int(os.getenv("DISCORD_RATE_LIMIT_PER_MINUTE", "10")),
            timeout_seconds=float(os.getenv("DISCORD_TIMEOUT_SECONDS", "5")),
        )


class DiscordNotifier:
    """Sends structured Discord webhook notifications with local rate limiting."""

    def __init__(
        self,
        config: DiscordNotifierConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or DiscordNotifierConfig.from_env()
        self._client = httpx.AsyncClient(timeout=self.config.timeout_seconds, transport=transport)
        self._sent_timestamps: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    async def send(
        self,
        category: NotificationCategory,
        component: str,
        message: str,
        metrics: dict[str, Any] | None = None,
    ) -> bool:
        if not self.config.webhook_url:
            logger.debug("Discord webhook is not configured; dropping notification")
            return False
        if category not in self.config.enabled_categories:
            return False

        async with self._lock:
            if not self._check_rate_limit():
                logger.warning("Discord rate limit exceeded locally; notification dropped")
                return False

            payload = self._build_payload(
                category=category,
                component=component,
                message=message,
                metrics=metrics or {},
            )
            try:
                response = await self._client.post(self.config.webhook_url, json=payload)
                if response.status_code >= 400:
                    logger.error(
                        "Discord notification failed status=%s body=%s",
                        response.status_code,
                        response.text[:200],
                    )
                    return False
                self._sent_timestamps.append(datetime.now(UTC))
                return True
            except Exception as exc:  # pragma: no cover - network dependent
                logger.error("Discord notification send error: %s", exc, exc_info=True)
                return False

    def _check_rate_limit(self) -> bool:
        now = datetime.now(UTC)
        while self._sent_timestamps and (now - self._sent_timestamps[0]).total_seconds() >= 60:
            self._sent_timestamps.popleft()
        return len(self._sent_timestamps) < self.config.rate_limit_per_minute

    @staticmethod
    def _build_payload(
        category: NotificationCategory,
        component: str,
        message: str,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        fields = [{"name": key, "value": str(value), "inline": True} for key, value in metrics.items()]
        embed = {
            "title": f"{category.value} | {component}",
            "description": message,
            "color": _COLOR_BY_CATEGORY[category],
            "timestamp": datetime.now(UTC).isoformat(),
            "fields": fields,
        }
        return {"embeds": [embed]}
