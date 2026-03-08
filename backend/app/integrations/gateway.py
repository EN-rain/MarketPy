"""API gateway with TTL cache and automatic fallback chains."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .base_client import ExternalAPIClient


@dataclass(frozen=True)
class CacheItem:
    """Stored cache value with expiration epoch."""

    value: dict[str, Any]
    expires_at: float


class TTLCache:
    """Small TTL + LRU cache implementation for API responses."""

    def __init__(
        self,
        maxsize: int = 1024,
        ttl: float = 10.0,
        now_fn: Callable[[], float] | None = None,
    ):
        self._maxsize = maxsize
        self._default_ttl = ttl
        self._now = now_fn or time.monotonic
        self._store: OrderedDict[str, CacheItem] = OrderedDict()

    def _evict_expired(self) -> None:
        now = self._now()
        expired_keys = [key for key, item in self._store.items() if item.expires_at <= now]
        for key in expired_keys:
            self._store.pop(key, None)

    def get(self, key: str) -> dict[str, Any] | None:
        self._evict_expired()
        item = self._store.get(key)
        if item is None:
            return None
        self._store.move_to_end(key)
        return item.value

    def set(self, key: str, value: dict[str, Any], ttl: float | None = None) -> None:
        self._evict_expired()
        effective_ttl = self._default_ttl if ttl is None else ttl
        self._store[key] = CacheItem(value=value, expires_at=self._now() + max(0.0, effective_ttl))
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._store)


class APIGateway:
    """Gateway that routes requests through primary/fallback clients."""

    def __init__(
        self,
        cache_maxsize: int = 1024,
        default_ttl_seconds: float = 10.0,
        now_fn: Callable[[], float] | None = None,
    ):
        self._clients: dict[str, ExternalAPIClient] = {}
        self._fallback_chains: dict[str, list[str]] = {}
        self.cache = TTLCache(maxsize=cache_maxsize, ttl=default_ttl_seconds, now_fn=now_fn)

    def register_client(self, name: str, client: ExternalAPIClient) -> None:
        self._clients[name] = client

    def get_client(self, name: str) -> ExternalAPIClient | None:
        return self._clients.get(name)

    def register_fallback_chain(self, primary: str, fallbacks: list[str]) -> None:
        self._fallback_chains[primary] = [primary, *fallbacks]

    def _get_chain(self, service: str) -> list[str]:
        return self._fallback_chains.get(service, [service])

    @staticmethod
    def _cache_key(service: str, params: dict[str, Any]) -> str:
        return f"{service}:{json.dumps(params, sort_keys=True, default=str)}"

    async def fetch_with_fallback(
        self,
        service: str,
        params: dict[str, Any],
        *,
        cache_ttl_seconds: float | None = None,
    ) -> dict[str, Any]:
        cache_key = self._cache_key(service, params)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        chain = self._get_chain(service)
        last_error: Exception | None = None
        for client_name in chain:
            client = self._clients.get(client_name)
            if client is None:
                continue
            try:
                payload = await client.fetch_data(params)
                self.cache.set(cache_key, payload, ttl=cache_ttl_seconds)
                return payload
            except Exception as exc:  # pragma: no cover - exercised in fallback tests
                last_error = exc
                continue

        if last_error is not None:
            raise RuntimeError(f"All providers failed for service '{service}'") from last_error
        raise ValueError(f"No registered clients found for service '{service}'")
