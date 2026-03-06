"""Connection manager with rate limiting, backpressure, and health metrics."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.realtime.backpressure_handler import BackpressureHandler
from backend.app.realtime.health_monitor import HealthMonitor
from backend.app.realtime.rate_limiter import RateLimiter


class ConnectionManager:
    """Manage WebSocket clients and broadcast with safeguards."""

    def __init__(
        self,
        rate_limiter: RateLimiter,
        backpressure_handler: BackpressureHandler,
        health_monitor: HealthMonitor,
    ):
        self._connections: dict[str, WebSocket] = {}
        self._websocket_to_client: dict[int, str] = {}
        self._connected_at: dict[str, datetime] = {}
        self._rate_limiter = rate_limiter
        self._backpressure = backpressure_handler
        self._health = health_monitor
        self._lock = asyncio.Lock()

    @property
    def active_connections(self) -> list[WebSocket]:
        return list(self._connections.values())

    @property
    def active_client_ids(self) -> list[str]:
        return list(self._connections.keys())

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[client_id] = websocket
            self._websocket_to_client[id(websocket)] = client_id
            self._connected_at[client_id] = datetime.now(UTC)
        self._health.on_client_connected(client_id)

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            ws = self._connections.pop(client_id, None)
            self._connected_at.pop(client_id, None)
            if ws is not None:
                self._websocket_to_client.pop(id(ws), None)
        self._rate_limiter.remove_client(client_id)
        self._backpressure.remove_client(client_id)
        self._health.on_client_disconnected(client_id)

    async def disconnect_websocket(self, websocket: WebSocket) -> None:
        client_id = self.get_client_id(websocket)
        if client_id:
            await self.disconnect(client_id)

    def get_client_id(self, websocket: WebSocket) -> str | None:
        return self._websocket_to_client.get(id(websocket))

    async def send_to_client(
        self,
        client_id: str,
        message: dict[str, Any],
        is_critical: bool = False,
        message_type: str = "generic",
    ) -> bool:
        websocket = self._connections.get(client_id)
        if websocket is None:
            return False

        allowed = await self._rate_limiter.check_rate_limit(client_id, is_critical=is_critical)
        if not allowed:
            self._rate_limiter.record_drop(client_id, message_type)
            self._health.record_message_dropped(client_id)
            return False

        start = time.perf_counter()
        sent = await self._backpressure.send_with_backpressure(
            client_id=client_id,
            websocket=websocket,
            message=message,
            is_critical=is_critical,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        self._health.record_message_sent(client_id, sent, latency_ms)
        self._health.mark_client_slow(
            client_id,
            self._backpressure.slow_clients.get(client_id).is_slow
            if client_id in self._backpressure.slow_clients
            else False,
        )
        if self._backpressure.should_disconnect(client_id):
            await self.disconnect(client_id)
            return False
        return sent

    async def broadcast(
        self,
        message: dict[str, Any],
        is_critical: bool = False,
        message_type: str = "generic",
    ) -> None:
        for client_id in list(self._connections.keys()):
            try:
                await self.send_to_client(
                    client_id=client_id,
                    message=message,
                    is_critical=is_critical,
                    message_type=message_type,
                )
            except (RuntimeError, WebSocketDisconnect):
                await self.disconnect(client_id)

    def get_connection_durations(self) -> dict[str, float]:
        now = datetime.now(UTC)
        return {
            client_id: (now - connected_at).total_seconds()
            for client_id, connected_at in self._connected_at.items()
        }

    def get_health_snapshot(self) -> dict[str, Any]:
        return self._health.get_all_metrics()
