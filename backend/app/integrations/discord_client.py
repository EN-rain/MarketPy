"""Discord webhook notification integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx


class DiscordRateLimitError(RuntimeError):
    """Raised when Discord webhook endpoint returns HTTP 429."""


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy for notification delivery."""

    max_retries: int = 3
    base_delay_seconds: float = 0.25
    multiplier: float = 2.0


@dataclass(frozen=True)
class DiscordMessage:
    """Discord webhook payload structure."""

    content: str
    embeds: list[dict[str, Any]] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"content": self.content}
        if self.embeds:
            payload["embeds"] = self.embeds
        return payload


class DiscordWebhookClient:
    """Client for sending Discord notifications to multiple webhook channels."""

    def __init__(
        self,
        webhook_urls: Mapping[str, str],
        *,
        retry_policy: RetryPolicy | None = None,
        queue_max_size: int = 100,
        timeout_seconds: float = 5.0,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.webhook_urls = dict(webhook_urls)
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep_fn or asyncio.sleep
        self._queue: asyncio.Queue[tuple[str, DiscordMessage]] = asyncio.Queue(
            maxsize=queue_max_size
        )
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def format_trade_notification(trade: Mapping[str, Any]) -> DiscordMessage:
        """Build a complete trade notification message."""
        trade_id = str(trade.get("trade_id", "unknown"))
        symbol = str(trade.get("symbol", "unknown"))
        side = str(trade.get("side", "unknown")).upper()
        quantity = trade.get("quantity", trade.get("qty", "unknown"))
        price = trade.get("price", "unknown")
        timestamp = str(trade.get("timestamp", "unknown"))
        content = (
            f"Trade {trade_id} | {side} {quantity} {symbol} @ {price} | timestamp={timestamp}"
        )
        return DiscordMessage(content=content)

    async def _send_once(self, channel: str, message: DiscordMessage) -> bool:
        webhook_url = self.webhook_urls.get(channel)
        if webhook_url is None:
            raise ValueError(f"Unknown Discord channel: {channel}")
        response = await self._client.post(webhook_url, json=message.to_payload())
        if response.status_code == 429:
            raise DiscordRateLimitError("Discord rate limit reached")
        if response.status_code >= 500:
            raise RuntimeError(f"Discord server error: {response.status_code}")
        if response.status_code >= 400:
            return False
        return True

    async def _enqueue(self, channel: str, message: DiscordMessage) -> bool:
        try:
            self._queue.put_nowait((channel, message))
            return True
        except asyncio.QueueFull:
            return False

    async def send_notification(self, channel: str, message: DiscordMessage) -> bool:
        """Send notification with exponential backoff retry (up to 3 attempts)."""
        delay = self.retry_policy.base_delay_seconds
        attempts = self.retry_policy.max_retries

        for attempt in range(1, attempts + 1):
            try:
                return await self._send_once(channel, message)
            except DiscordRateLimitError:
                return await self._enqueue(channel, message)
            except Exception:
                if attempt == attempts:
                    return False
                await self._sleep(delay)
                delay *= self.retry_policy.multiplier

        return False

    async def process_queue(self, *, max_items: int | None = None) -> int:
        """Attempt to flush queued notifications. Returns count processed."""
        processed = 0
        limit = self._queue.qsize() if max_items is None else max(0, max_items)
        for _ in range(limit):
            if self._queue.empty():
                break
            channel, message = await self._queue.get()
            ok = await self.send_notification(channel, message)
            if ok:
                processed += 1
            self._queue.task_done()
        return processed
