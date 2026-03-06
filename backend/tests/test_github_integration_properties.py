"""Property tests for GitHub integration.

Validates:
- Property 5: Rate Limit Compliance
- Property 6: Cache TTL Expiration
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.github_client import GitHubClient, GitHubRateLimitExceededError


@dataclass
class MutableClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


# Property 5: Rate Limit Compliance
@given(request_count=st.integers(min_value=2, max_value=20))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_github_rate_limit_compliance(request_count: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/contributors"):
            return httpx.Response(200, json=[{"login": "a"}])
        if path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "1"}])
        return httpx.Response(200, json={"open_issues_count": 5})

    clock = MutableClock()
    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        now_fn=clock.now,
        cache_ttl_seconds=0.0,
        rate_limit_per_hour=(request_count * 3) - 1,
    )
    accepted = 0
    rejected = 0
    try:
        for _ in range(request_count):
            try:
                await client.get_repo_activity("org/repo")
                accepted += 1
            except GitHubRateLimitExceededError:
                rejected += 1
                break
    finally:
        await client.close()

    assert accepted >= 1
    assert rejected >= 1


# Property 6: Cache TTL Expiration
@given(
    ttl_seconds=st.floats(min_value=10.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
    first_advance=st.floats(min_value=0.0, max_value=3599.0, allow_nan=False, allow_infinity=False),
    second_advance=st.floats(
        min_value=10.0, max_value=3600.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_github_cache_ttl_expiration(
    ttl_seconds: float, first_advance: float, second_advance: float
) -> None:
    calls = {"meta": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/contributors"):
            return httpx.Response(200, json=[{"login": "a"}, {"login": "b"}])
        if path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "1"}, {"sha": "2"}])
        calls["meta"] += 1
        return httpx.Response(200, json={"open_issues_count": calls["meta"]})

    clock = MutableClock()
    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        now_fn=clock.now,
        cache_ttl_seconds=ttl_seconds,
        rate_limit_per_hour=10000,
    )
    try:
        first = await client.get_repo_activity("org/repo")
        clock.advance(min(first_advance, ttl_seconds * 0.8))
        second = await client.get_repo_activity("org/repo")
        assert first.open_issues_count == second.open_issues_count

        clock.advance(max(second_advance, ttl_seconds + 1.0))
        third = await client.get_repo_activity("org/repo")
    finally:
        await client.close()

    assert third.open_issues_count >= second.open_issues_count
    assert calls["meta"] >= 2


@pytest.mark.asyncio
async def test_detect_activity_change_generates_signal_when_threshold_crossed() -> None:
    snapshots = [
        {"open_issues_count": 10, "contributors": 3, "commits": 2},
        {"open_issues_count": 20, "contributors": 6, "commits": 5},
    ]
    idx = {"value": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        current = snapshots[min(idx["value"], len(snapshots) - 1)]
        path = request.url.path
        if path.endswith("/contributors"):
            return httpx.Response(
                200, json=[{"login": str(i)} for i in range(current["contributors"])]
            )
        if path.endswith("/commits"):
            return httpx.Response(
                200, json=[{"sha": str(i)} for i in range(current["commits"])]
            )
        idx["value"] += 1
        return httpx.Response(200, json={"open_issues_count": current["open_issues_count"]})

    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        cache_ttl_seconds=0.0,
        rate_limit_per_hour=1000,
    )
    try:
        first = await client.detect_activity_change("org/repo", threshold=0.3)
        second = await client.detect_activity_change("org/repo", threshold=0.3)
    finally:
        await client.close()

    assert first is None
    assert second is not None
    assert second["max_change"] >= 0.3
