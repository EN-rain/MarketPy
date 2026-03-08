"""Unit tests for RateLimiter."""

import asyncio

import pytest

from backend.app.models.realtime_config import RateLimiterConfig
from backend.app.realtime.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_burst_allowance_then_drop():
    limiter = RateLimiter(
        RateLimiterConfig(max_messages_per_second=5, burst_size=3, critical_bypass=True)
    )
    client = "c1"

    assert await limiter.check_rate_limit(client) is True
    assert await limiter.check_rate_limit(client) is True
    assert await limiter.check_rate_limit(client) is True
    assert await limiter.check_rate_limit(client) is False


@pytest.mark.asyncio
async def test_token_refill_timing():
    limiter = RateLimiter(
        RateLimiterConfig(max_messages_per_second=2, burst_size=2, critical_bypass=True)
    )
    client = "c2"
    assert await limiter.check_rate_limit(client) is True
    assert await limiter.check_rate_limit(client) is True
    assert await limiter.check_rate_limit(client) is False

    await asyncio.sleep(0.55)
    assert await limiter.check_rate_limit(client) is True


@pytest.mark.asyncio
async def test_critical_bypass():
    limiter = RateLimiter(
        RateLimiterConfig(max_messages_per_second=1, burst_size=1, critical_bypass=True)
    )
    client = "c3"
    assert await limiter.check_rate_limit(client, is_critical=False) is True
    assert await limiter.check_rate_limit(client, is_critical=False) is False
    assert await limiter.check_rate_limit(client, is_critical=True) is True


@pytest.mark.asyncio
async def test_multi_client_isolation():
    limiter = RateLimiter(
        RateLimiterConfig(max_messages_per_second=1, burst_size=1, critical_bypass=False)
    )
    assert await limiter.check_rate_limit("a") is True
    assert await limiter.check_rate_limit("b") is True
    assert await limiter.check_rate_limit("a") is False
    assert await limiter.check_rate_limit("b") is False


def test_record_drop_tracks_type():
    limiter = RateLimiter(
        RateLimiterConfig(max_messages_per_second=1, burst_size=1, critical_bypass=False)
    )
    limiter.record_drop("x", "batch")
    limiter.record_drop("x", "batch")
    stats = limiter.get_stats("x")
    assert stats.dropped_by_type["batch"] == 2
