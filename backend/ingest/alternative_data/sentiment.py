"""Social sentiment data source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .base import AlternativeDataPoint, AlternativeDataSource


POSITIVE_WORDS = {"bull", "breakout", "moon", "surge", "gain"}
NEGATIVE_WORDS = {"bear", "crash", "dump", "loss", "fear"}


@dataclass(slots=True)
class SocialSentimentSource(AlternativeDataSource):
    twitter_posts: list[str]
    reddit_posts: list[str]

    def _score_posts(self, posts: list[str]) -> float:
        score = 0
        words = 0
        for post in posts:
            tokens = {token.strip(".,!?").lower() for token in post.split()}
            score += len(tokens & POSITIVE_WORDS)
            score -= len(tokens & NEGATIVE_WORDS)
            words += max(len(tokens), 1)
        if words == 0:
            return 0.0
        raw = score / words * 10
        return max(-1.0, min(raw, 1.0))

    def get_data(self, symbol: str) -> AlternativeDataPoint:
        observed_at = datetime.now(UTC)
        payload = {
            "twitter_sentiment": self._score_posts(self.twitter_posts),
            "reddit_sentiment": self._score_posts(self.reddit_posts),
            "twitter_posts": len(self.twitter_posts),
            "reddit_posts": len(self.reddit_posts),
        }
        return AlternativeDataPoint(
            source="social_sentiment",
            symbol=symbol,
            observed_at=observed_at,
            value=payload,
            quality_score=self.quality_score(payload),
            is_stale=self.is_stale(observed_at),
        )

    def normalize_data(self, payload: dict[str, float]) -> dict[str, float]:
        return {
            "twitter_sentiment": max(-1.0, min(float(payload["twitter_sentiment"]), 1.0)),
            "reddit_sentiment": max(-1.0, min(float(payload["reddit_sentiment"]), 1.0)),
        }
