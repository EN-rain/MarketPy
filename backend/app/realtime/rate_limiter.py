"""Rate limiter for WebSocket broadcasts using token bucket algorithm."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from backend.app.models.realtime_config import RateLimiterConfig


@dataclass
class TokenBucket:
    """Token bucket for rate limiting a single client."""
    capacity: float  # Maximum tokens (burst size)
    tokens: float  # Current available tokens
    refill_rate: float  # Tokens added per second
    last_refill: float  # Timestamp of last refill

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


@dataclass
class RateLimitStats:
    """Statistics for rate limiting a client."""
    client_id: str
    messages_allowed: int = 0
    messages_dropped: int = 0
    dropped_by_type: dict[str, int] = field(default_factory=dict)
    current_tokens: float = 0.0
    max_tokens: float = 0.0


class RateLimiter:
    """Enforces per-client broadcast rate limits using token bucket algorithm.
    
    The token bucket algorithm allows for burst traffic while maintaining
    an average rate limit. Each client has a bucket that:
    - Holds up to `burst_size` tokens
    - Refills at `max_messages_per_second` tokens per second
    - Consumes 1 token per message
    
    Critical messages can bypass rate limits if configured.
    """

    def __init__(self, config: RateLimiterConfig):
        """Initialize rate limiter with configuration.
        
        Args:
            config: Rate limiter configuration with max_messages_per_second,
                   burst_size, and critical_bypass settings
        """
        self.max_messages_per_second = config.max_messages_per_second
        self.burst_size = config.burst_size
        self.critical_bypass = config.critical_bypass

        # Per-client token buckets
        self.client_buckets: dict[str, TokenBucket] = {}

        # Per-client statistics
        self.client_stats: dict[str, RateLimitStats] = {}

    def _get_or_create_bucket(self, client_id: str) -> TokenBucket:
        """Get existing bucket or create new one for client."""
        if client_id not in self.client_buckets:
            self.client_buckets[client_id] = TokenBucket(
                capacity=float(self.burst_size),
                tokens=float(self.burst_size),  # Start with full bucket
                refill_rate=float(self.max_messages_per_second),
                last_refill=time.time()
            )
        return self.client_buckets[client_id]

    def _get_or_create_stats(self, client_id: str) -> RateLimitStats:
        """Get existing stats or create new ones for client."""
        if client_id not in self.client_stats:
            self.client_stats[client_id] = RateLimitStats(
                client_id=client_id,
                max_tokens=float(self.burst_size)
            )
        return self.client_stats[client_id]

    async def check_rate_limit(self, client_id: str, is_critical: bool = False) -> bool:
        """Check if client can receive a message based on rate limits.
        
        Args:
            client_id: Unique identifier for the client
            is_critical: Whether this is a critical message
            
        Returns:
            True if message should be sent, False if it should be dropped
        """
        # Critical messages always bypass rate limits if configured
        if is_critical and self.critical_bypass:
            stats = self._get_or_create_stats(client_id)
            stats.messages_allowed += 1
            return True

        # Check token bucket
        bucket = self._get_or_create_bucket(client_id)
        stats = self._get_or_create_stats(client_id)

        if bucket.consume():
            stats.messages_allowed += 1
            stats.current_tokens = bucket.tokens
            return True
        else:
            stats.messages_dropped += 1
            stats.current_tokens = bucket.tokens
            return False

    def record_drop(self, client_id: str, message_type: str) -> None:
        """Record a dropped message for statistics.
        
        Args:
            client_id: Unique identifier for the client
            message_type: Type of message that was dropped
        """
        stats = self._get_or_create_stats(client_id)
        stats.messages_dropped += 1

        if message_type not in stats.dropped_by_type:
            stats.dropped_by_type[message_type] = 0
        stats.dropped_by_type[message_type] += 1

    def get_stats(self, client_id: str) -> RateLimitStats:
        """Get rate limit statistics for a client.
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            RateLimitStats object with current statistics
        """
        stats = self._get_or_create_stats(client_id)

        # Update current token count if bucket exists
        if client_id in self.client_buckets:
            bucket = self.client_buckets[client_id]
            bucket.refill()  # Ensure tokens are up to date
            stats.current_tokens = bucket.tokens

        return stats

    def remove_client(self, client_id: str) -> None:
        """Remove client's bucket and stats (cleanup on disconnect).
        
        Args:
            client_id: Unique identifier for the client
        """
        self.client_buckets.pop(client_id, None)
        self.client_stats.pop(client_id, None)

    def get_all_stats(self) -> dict[str, RateLimitStats]:
        """Get rate limit statistics for all clients.
        
        Returns:
            Dictionary mapping client_id to RateLimitStats
        """
        # Update all token counts before returning
        for client_id in self.client_buckets:
            bucket = self.client_buckets[client_id]
            bucket.refill()
            stats = self.client_stats[client_id]
            stats.current_tokens = bucket.tokens

        return dict(self.client_stats)
