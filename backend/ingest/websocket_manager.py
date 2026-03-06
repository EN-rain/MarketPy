"""WebSocket connection manager with reconnection and buffering."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import websockets

from backend.ingest.exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass(slots=True)
class ReconnectPolicy:
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_factor: float = 2.0
    max_attempts: int = 10


class WebSocketManager:
    """Manages exchange websocket lifecycle and subscription recovery."""

    def __init__(
        self,
        exchange_client: ExchangeClient,
        reconnect_policy: ReconnectPolicy | None = None,
        message_buffer_size: int = 100,
        on_critical_failure: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> None:
        self.exchange_client = exchange_client
        self.reconnect_policy = reconnect_policy or ReconnectPolicy()
        self._buffer = deque(maxlen=message_buffer_size)
        self._handlers: list[Callable[[dict[str, Any]], Awaitable[None] | None]] = []
        self._state_handlers: list[Callable[[ConnectionState], None]] = []
        self._state = ConnectionState.DISCONNECTED
        self._channels: list[str] = []
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._on_critical_failure = on_critical_failure
        self._metrics = {
            "reconnection_count": 0,
            "messages_received": 0,
            "uptime_seconds": 0.0,
            "connected_since": None,
        }

    def add_handler(self, handler: Callable[[dict[str, Any]], Awaitable[None] | None]) -> None:
        self._handlers.append(handler)

    def add_state_handler(self, handler: Callable[[ConnectionState], None]) -> None:
        self._state_handlers.append(handler)

    def get_state(self) -> ConnectionState:
        return self._state

    def get_metrics(self) -> dict[str, Any]:
        snapshot = dict(self._metrics)
        connected_since = snapshot.get("connected_since")
        if connected_since is not None and self._state == ConnectionState.CONNECTED:
            snapshot["uptime_seconds"] = max(0.0, time.monotonic() - float(connected_since))
        snapshot.pop("connected_since", None)
        return snapshot

    async def connect(self, channels: list[str]) -> None:
        self._channels = channels[:]
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def disconnect(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._set_state(ConnectionState.DISCONNECTED)

    def buffer_message(self, message: dict[str, Any]) -> None:
        self._buffer.append(message)

    async def _emit_message(self, payload: dict[str, Any]) -> None:
        for handler in self._handlers:
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # pragma: no cover - handler dependent
                logger.warning("WebSocket handler failed: %s", exc)

    async def _flush_buffer(self) -> None:
        while self._buffer:
            buffered = self._buffer.popleft()
            await self._emit_message(buffered)

    def _set_state(self, state: ConnectionState) -> None:
        if self._state == state:
            return
        self._state = state
        for handler in self._state_handlers:
            try:
                handler(state)
            except Exception:
                pass

    async def _run(self) -> None:
        attempts = 0
        delay = self.reconnect_policy.initial_delay_seconds
        while self._running:
            try:
                self._set_state(
                    ConnectionState.CONNECTING if attempts == 0 else ConnectionState.RECONNECTING
                )
                ws_url = self.exchange_client.get_websocket_url(self._channels)
                async with websockets.connect(ws_url) as ws:
                    attempts = 0
                    delay = self.reconnect_policy.initial_delay_seconds
                    self._metrics["connected_since"] = time.monotonic()
                    self._set_state(ConnectionState.CONNECTED)
                    await self._flush_buffer()

                    async for raw_message in ws:
                        payload = json.loads(raw_message)
                        self._metrics["messages_received"] += 1
                        await self._emit_message(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - network dependent
                attempts += 1
                self._metrics["reconnection_count"] += 1
                logger.warning("WebSocket disconnected (%s), attempt=%s", exc, attempts)
                if attempts >= self.reconnect_policy.max_attempts:
                    self._set_state(ConnectionState.FAILED)
                    message = (
                        f"WebSocket reconnection failed after {attempts} attempts "
                        f"for exchange={self.exchange_client.exchange_id}"
                    )
                    logger.critical(message)
                    if self._on_critical_failure is not None:
                        try:
                            outcome = self._on_critical_failure(message)
                            if asyncio.iscoroutine(outcome):
                                await outcome
                        except Exception:
                            pass
                    if not self._running:
                        break
                    attempts = 0
                    delay = self.reconnect_policy.initial_delay_seconds
                    await asyncio.sleep(delay)
                    continue

                self._set_state(ConnectionState.RECONNECTING)
                await asyncio.sleep(delay)
                delay = min(
                    self.reconnect_policy.max_delay_seconds,
                    delay * self.reconnect_policy.backoff_factor,
                )

        self._set_state(ConnectionState.DISCONNECTED)
