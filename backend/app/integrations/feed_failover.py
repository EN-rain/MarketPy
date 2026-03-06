"""Primary/secondary feed failover with recovery detection."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from .gateway import APIGateway

logger = logging.getLogger(__name__)


class FeedFailoverManager:
    """Stateful failover manager for primary -> secondary feed switching."""

    def __init__(
        self,
        *,
        gateway: APIGateway,
        primary_feed: str,
        secondary_feed: str,
        recovery_window_seconds: float = 30.0,
        now_fn: Callable[[], float] | None = None,
    ):
        self.gateway = gateway
        self.primary_feed = primary_feed
        self.secondary_feed = secondary_feed
        self.recovery_window_seconds = recovery_window_seconds
        self._now = now_fn or time.monotonic
        self.active_feed = primary_feed
        self._last_primary_failure_at: float | None = None

        # Register fallback chain as baseline behavior.
        self.gateway.register_fallback_chain(primary_feed, [secondary_feed])

    async def fetch(self, params: dict[str, Any]) -> dict[str, Any]:
        primary = self.gateway.get_client(self.primary_feed)
        secondary = self.gateway.get_client(self.secondary_feed)
        if primary is None or secondary is None:
            raise ValueError("Both primary and secondary feeds must be registered in gateway")

        if self.active_feed == self.primary_feed:
            try:
                return await primary.fetch_data(params)
            except Exception:
                self.active_feed = self.secondary_feed
                self._last_primary_failure_at = self._now()
                logger.warning(
                    "feed_switch primary=%s secondary=%s reason=primary_failure",
                    self.primary_feed,
                    self.secondary_feed,
                )
                return await secondary.fetch_data(params)

        # Secondary mode: check for primary recovery after cooldown.
        if self._last_primary_failure_at is not None:
            elapsed = self._now() - self._last_primary_failure_at
            if elapsed >= self.recovery_window_seconds:
                if await primary.health_check():
                    self.active_feed = self.primary_feed
                    self._last_primary_failure_at = None
                    logger.info(
                        "feed_recovery restored=%s previous=%s",
                        self.primary_feed,
                        self.secondary_feed,
                    )
                    return await primary.fetch_data(params)

        return await secondary.fetch_data(params)

