"""Base interfaces and shared dataclasses for external API clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RateLimit:
    """Simple rate-limit definition for an external API."""

    calls: int
    period_seconds: int


class ExternalAPIClient(ABC):
    """Abstract interface implemented by all external API clients."""

    @abstractmethod
    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Fetch data from the external API."""

    @abstractmethod
    def get_rate_limit(self) -> RateLimit:
        """Return configured rate limits for this client."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True when the upstream API is healthy."""
