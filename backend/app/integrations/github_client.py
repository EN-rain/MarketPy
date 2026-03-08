"""GitHub API integration for repository activity tracking."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from backend.app.models.market import RepoActivity

from .base_client import ExternalAPIClient, RateLimit


class GitHubRateLimitExceededError(RuntimeError):
    """Raised when client-side GitHub rate limiter is exceeded."""


class GitHubClient(ExternalAPIClient):
    """GitHub client with token auth, one-hour cache, and activity-drift detection."""

    BASE_URL = "https://api.github.com"
    CACHE_TTL_SECONDS = 3600

    def __init__(
        self,
        *,
        github_token: str | None = None,
        timeout_seconds: float = 2.0,
        cache_ttl_seconds: float = CACHE_TTL_SECONDS,
        rate_limit_per_hour: int = 5000,
        transport: httpx.AsyncBaseTransport | None = None,
        now_fn: Callable[[], float] | None = None,
    ):
        headers = {"Accept": "application/vnd.github+json"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout_seconds,
            transport=transport,
            headers=headers,
        )
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, RepoActivity]] = {}
        self._rate_limit_per_hour = rate_limit_per_hour
        self._request_times: deque[float] = deque()
        self._now = now_fn or time.monotonic
        self._last_snapshot: dict[str, RepoActivity] = {}

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=self._rate_limit_per_hour, period_seconds=3600)

    def _enforce_rate_limit(self) -> None:
        now = self._now()
        while self._request_times and now - self._request_times[0] >= 3600:
            self._request_times.popleft()
        if len(self._request_times) >= self._rate_limit_per_hour:
            raise GitHubRateLimitExceededError(
                f"GitHub rate limit exceeded ({self._rate_limit_per_hour} calls/hour)"
            )
        self._request_times.append(now)

    async def health_check(self) -> bool:
        try:
            self._enforce_rate_limit()
            response = await self._client.get("/rate_limit")
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def _fetch_repo_metadata(self, repo: str) -> dict[str, Any]:
        self._enforce_rate_limit()
        response = await self._client.get(f"/repos/{repo}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected GitHub repo metadata response shape")
        return payload

    async def _fetch_contributors_count(self, repo: str) -> int:
        self._enforce_rate_limit()
        response = await self._client.get(f"/repos/{repo}/contributors", params={"per_page": 100})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return 0
        return len(payload)

    async def _fetch_commits_24h_count(self, repo: str) -> int:
        since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        self._enforce_rate_limit()
        response = await self._client.get(
            f"/repos/{repo}/commits",
            params={"since": since, "per_page": 100},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return 0
        return len(payload)

    async def get_repo_activity(self, repo: str) -> RepoActivity:
        cached = self._cache.get(repo)
        now = self._now()
        if cached and cached[0] > now:
            return cached[1]

        metadata = await self._fetch_repo_metadata(repo)
        contributors = await self._fetch_contributors_count(repo)
        commits_24h = await self._fetch_commits_24h_count(repo)
        snapshot = RepoActivity(
            repo=repo,
            commit_count_24h=commits_24h,
            contributor_count=contributors,
            open_issues_count=int(metadata.get("open_issues_count", 0)),
            timestamp=datetime.now(UTC),
        )
        self._cache[repo] = (now + self._cache_ttl_seconds, snapshot)
        return snapshot

    async def detect_activity_change(
        self, repo: str, threshold: float = 0.3
    ) -> dict[str, Any] | None:
        current = await self.get_repo_activity(repo)
        previous = self._last_snapshot.get(repo)
        self._last_snapshot[repo] = current
        if previous is None:
            return None

        def pct_change(new_value: int, old_value: int) -> float:
            if old_value <= 0:
                return 1.0 if new_value > 0 else 0.0
            return abs(new_value - old_value) / old_value

        commit_change = pct_change(current.commit_count_24h, previous.commit_count_24h)
        issue_change = pct_change(current.open_issues_count, previous.open_issues_count)
        contributor_change = pct_change(current.contributor_count, previous.contributor_count)
        max_change = max(commit_change, issue_change, contributor_change)
        if max_change >= threshold:
            return {
                "repo": repo,
                "threshold": threshold,
                "max_change": max_change,
                "commit_change": commit_change,
                "issue_change": issue_change,
                "contributor_change": contributor_change,
            }
        return None

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        repo = str(params.get("repo", "")).strip()
        if not repo:
            raise ValueError("repo is required")
        activity = await self.get_repo_activity(repo)
        return {
            "repo": activity.repo,
            "commit_count_24h": activity.commit_count_24h,
            "contributor_count": activity.contributor_count,
            "open_issues_count": activity.open_issues_count,
            "timestamp": activity.timestamp.isoformat(),
        }
