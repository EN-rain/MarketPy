"""Backpressure handling for slow WebSocket clients."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import WebSocket

from backend.app.models.realtime_config import BackpressureConfig


@dataclass
class SlowClientState:
    """Runtime state for a slow client."""

    client_id: str
    is_slow: bool = False
    marked_slow_at: datetime | None = None
    dropped_messages: int = 0
    last_error: str | None = None


class BackpressureHandler:
    """Detect and mitigate slow clients with graceful degradation."""

    def __init__(self, config: BackpressureConfig):
        self.send_buffer_threshold = config.send_buffer_threshold
        self.slow_client_timeout = config.slow_client_timeout
        self.drop_non_critical_for_slow = config.drop_non_critical_for_slow
        self.slow_clients: dict[str, SlowClientState] = {}

    async def send_with_backpressure(
        self,
        client_id: str,
        websocket: WebSocket,
        message: dict[str, Any],
        is_critical: bool,
    ) -> bool:
        """Send a message and track whether client behavior indicates backpressure."""
        state = self._get_or_create_state(client_id)

        if state.is_slow and self.drop_non_critical_for_slow and not is_critical:
            state.dropped_messages += 1
            return False

        send_timeout = max(0.1, min(1.0, self.slow_client_timeout / 10))
        try:
            await asyncio.wait_for(websocket.send_json(message), timeout=send_timeout)
            # Successful send can recover client from slow state.
            if state.is_slow:
                state.is_slow = False
                state.marked_slow_at = None
            return True
        except Exception as exc:  # pragma: no cover - framework-specific branch
            state.last_error = str(exc)
            self.mark_slow_client(client_id)
            if not is_critical:
                state.dropped_messages += 1
            return False

    def mark_slow_client(self, client_id: str) -> None:
        """Mark client as slow and start timeout tracking."""
        state = self._get_or_create_state(client_id)
        if not state.is_slow:
            state.is_slow = True
            state.marked_slow_at = datetime.now(UTC)

    def should_disconnect(self, client_id: str) -> bool:
        """Determine if client exceeded slow timeout and should be disconnected."""
        state = self._get_or_create_state(client_id)
        if not state.is_slow or state.marked_slow_at is None:
            return False
        return datetime.now(UTC) - state.marked_slow_at >= timedelta(
            seconds=self.slow_client_timeout
        )

    def get_slow_client_stats(self) -> dict[str, dict[str, Any]]:
        """Expose slow-client state for APIs."""
        return {
            client_id: {
                "is_slow": state.is_slow,
                "marked_slow_at": state.marked_slow_at.isoformat()
                if state.marked_slow_at
                else None,
                "dropped_messages": state.dropped_messages,
                "last_error": state.last_error,
            }
            for client_id, state in self.slow_clients.items()
        }

    def remove_client(self, client_id: str) -> None:
        self.slow_clients.pop(client_id, None)

    def _get_or_create_state(self, client_id: str) -> SlowClientState:
        if client_id not in self.slow_clients:
            self.slow_clients[client_id] = SlowClientState(client_id=client_id)
        return self.slow_clients[client_id]

