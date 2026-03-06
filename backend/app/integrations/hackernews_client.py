"""Hacker News sentiment integration for crypto-related posts."""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from backend.app.models.market import SentimentScore
from backend.app.storage.metrics_store import MetricsStore

from .base_client import ExternalAPIClient, RateLimit

POSITIVE_WORDS = {"bull", "bullish", "adoption", "breakout", "upgrade", "growth", "rally"}
NEGATIVE_WORDS = {"bear", "bearish", "crash", "hack", "scam", "selloff", "downtrend"}


class HackerNewsClient(ExternalAPIClient):
    """Client for pulling HN posts and deriving keyword-based sentiment."""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    UPDATE_INTERVAL_SECONDS = 1800

    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
        store: MetricsStore | None = None,
    ):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout_seconds,
            transport=transport,
        )
        self.store = store
        self._history: list[SentimentScore] = []

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=300, period_seconds=60)

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/maxitem.json")
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def fetch_crypto_posts(
        self, keywords: list[str], *, limit: int = 30
    ) -> list[dict[str, Any]]:
        response = await self._client.get("/topstories.json")
        response.raise_for_status()
        ids = response.json()
        if not isinstance(ids, list):
            return []
        lowered_keywords = [kw.lower() for kw in keywords]
        posts: list[dict[str, Any]] = []
        for item_id in ids[: limit * 3]:
            item_resp = await self._client.get(f"/item/{int(item_id)}.json")
            item_resp.raise_for_status()
            item = item_resp.json()
            if not isinstance(item, dict):
                continue
            text = f"{item.get('title', '')} {item.get('text', '')}".lower()
            if any(keyword in text for keyword in lowered_keywords):
                posts.append(item)
            if len(posts) >= limit:
                break
        return posts

    @staticmethod
    def analyze_sentiment(posts: list[dict[str, Any]]) -> SentimentScore:
        pos = 0
        neg = 0
        neutral = 0
        for post in posts:
            text = f"{post.get('title', '')} {post.get('text', '')}".lower()
            p_hits = sum(1 for w in POSITIVE_WORDS if w in text)
            n_hits = sum(1 for w in NEGATIVE_WORDS if w in text)
            if p_hits > n_hits:
                pos += 1
            elif n_hits > p_hits:
                neg += 1
            else:
                neutral += 1

        total = max(1, pos + neg + neutral)
        score = (pos - neg) / total
        # Clamp to required range.
        score = max(-1.0, min(1.0, score))
        return SentimentScore(
            source="hackernews",
            score=score,
            positive_count=pos,
            negative_count=neg,
            neutral_count=neutral,
            timestamp=datetime.now(UTC),
        )

    async def get_daily_trend(self) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=1)
        daily_scores = [item.score for item in self._history if item.timestamp >= since]
        if not daily_scores:
            return {"mean_score": 0.0, "count": 0}
        return {
            "mean_score": statistics.fmean(daily_scores),
            "count": len(daily_scores),
        }

    def detect_sentiment_shift(self, threshold_stddev: float = 0.5) -> dict[str, Any] | None:
        if len(self._history) < 5:
            return None
        scores = [item.score for item in self._history]
        mean = statistics.fmean(scores)
        std = statistics.pstdev(scores) or 1e-9
        latest = scores[-1]
        z_score = abs((latest - mean) / std)
        if z_score > threshold_stddev:
            return {"latest_score": latest, "mean": mean, "stddev": std, "z_score": z_score}
        return None

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        keywords_value = params.get("keywords", ["bitcoin", "crypto", "ethereum"])
        if isinstance(keywords_value, str):
            keywords = [kw.strip() for kw in keywords_value.split(",") if kw.strip()]
        elif isinstance(keywords_value, list):
            keywords = [str(kw) for kw in keywords_value]
        else:
            keywords = ["bitcoin", "crypto", "ethereum"]
        posts = await self.fetch_crypto_posts(keywords)
        score = self.analyze_sentiment(posts)
        self._history.append(score)
        if self.store is not None:
            self.store.insert_sentiment_score(score)
        return {
            "score": score.score,
            "positive_count": score.positive_count,
            "negative_count": score.negative_count,
            "neutral_count": score.neutral_count,
            "timestamp": score.timestamp.isoformat(),
        }
