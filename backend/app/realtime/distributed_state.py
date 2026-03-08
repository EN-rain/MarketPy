"""Distributed websocket subscription state with in-memory fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from threading import Lock


class SubscriptionStateStore:
    def set_channels(self, client_id: str, channels: set[str]) -> None: ...
    def get_channels(self, client_id: str) -> set[str]: ...
    def remove_channels(self, client_id: str, remove: set[str]) -> set[str]: ...
    def clear_client(self, client_id: str) -> None: ...


@dataclass
class InMemorySubscriptionStore(SubscriptionStateStore):
    _store: dict[str, set[str]]
    _lock: Lock

    def __init__(self) -> None:
        self._store = {}
        self._lock = Lock()

    def set_channels(self, client_id: str, channels: set[str]) -> None:
        with self._lock:
            self._store[client_id] = set(channels)

    def get_channels(self, client_id: str) -> set[str]:
        with self._lock:
            return set(self._store.get(client_id, set()))

    def remove_channels(self, client_id: str, remove: set[str]) -> set[str]:
        with self._lock:
            existing = self._store.get(client_id, set())
            remaining = {channel for channel in existing if channel not in remove}
            self._store[client_id] = remaining
            return set(remaining)

    def clear_client(self, client_id: str) -> None:
        with self._lock:
            self._store.pop(client_id, None)


@dataclass
class RedisSubscriptionStore(SubscriptionStateStore):
    """Redis-backed client subscription store.

    Format:
    key = ws:channels:<client_id>
    value = json array of channels
    """

    redis_client: object
    prefix: str = "ws:channels:"
    ttl_seconds: int = 3600

    def _key(self, client_id: str) -> str:
        return f"{self.prefix}{client_id}"

    def set_channels(self, client_id: str, channels: set[str]) -> None:
        key = self._key(client_id)
        payload = json.dumps(sorted(channels))
        self.redis_client.set(key, payload, ex=self.ttl_seconds)

    def get_channels(self, client_id: str) -> set[str]:
        key = self._key(client_id)
        raw = self.redis_client.get(key)
        if raw is None:
            return set()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        values = json.loads(str(raw))
        return {str(value).strip().lower() for value in values}

    def remove_channels(self, client_id: str, remove: set[str]) -> set[str]:
        remaining = {channel for channel in self.get_channels(client_id) if channel not in remove}
        self.set_channels(client_id, remaining)
        return remaining

    def clear_client(self, client_id: str) -> None:
        self.redis_client.delete(self._key(client_id))


def build_subscription_store() -> SubscriptionStateStore:
    backend = os.getenv("WEBSOCKET_STATE_BACKEND", "memory").strip().lower()
    if backend != "redis":
        return InMemorySubscriptionStore()
    try:
        import redis  # type: ignore

        redis_url = os.getenv("WEBSOCKET_STATE_URL", "redis://localhost:6379/2")
        client = redis.from_url(redis_url, decode_responses=False)
        client.ping()
        return RedisSubscriptionStore(redis_client=client)
    except Exception:
        return InMemorySubscriptionStore()
