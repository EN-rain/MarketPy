"""News sentiment and topic extraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .base import AlternativeDataPoint, AlternativeDataSource


NEWS_TOPICS = {
    "etf": "etf",
    "regulation": "regulation",
    "hack": "security",
    "funding": "funding",
}


@dataclass(slots=True)
class NewsSentimentSource(AlternativeDataSource):
    articles: list[dict[str, str]]

    def _article_sentiment(self, text: str) -> float:
        lower = text.lower()
        score = 0.0
        if "surge" in lower or "approval" in lower or "record high" in lower:
            score += 0.6
        if "hack" in lower or "lawsuit" in lower or "ban" in lower:
            score -= 0.6
        return max(-1.0, min(score, 1.0))

    def _topics(self, text: str) -> list[str]:
        lower = text.lower()
        return sorted({topic for key, topic in NEWS_TOPICS.items() if key in lower})

    def get_data(self, symbol: str) -> AlternativeDataPoint:
        observed_at = datetime.now(UTC)
        sentiments = [self._article_sentiment(f"{article.get('title', '')} {article.get('body', '')}") for article in self.articles]
        topics = [topic for article in self.articles for topic in self._topics(f"{article.get('title', '')} {article.get('body', '')}")]
        payload = {
            "sentiment": sum(sentiments) / len(sentiments) if sentiments else 0.0,
            "article_count": len(self.articles),
            "topics": sorted(set(topics)),
        }
        return AlternativeDataPoint(
            source="news_sentiment",
            symbol=symbol,
            observed_at=observed_at,
            value=payload,
            quality_score=self.quality_score(payload),
            is_stale=self.is_stale(observed_at),
        )

    def normalize_data(self, payload: dict[str, object]) -> dict[str, float]:
        return {
            "sentiment": max(-1.0, min(float(payload["sentiment"]), 1.0)),
            "topic_relevance": min(float(len(payload.get("topics", []))) / 5.0, 1.0),
        }
