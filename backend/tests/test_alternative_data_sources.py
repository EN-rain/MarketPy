from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.ingest.alternative_data.base import AlternativeDataPoint, AlternativeDataSource
from backend.ingest.alternative_data.news import NewsSentimentSource
from backend.ingest.alternative_data.sentiment import SocialSentimentSource


class DummySource(AlternativeDataSource):
    def get_data(self, symbol: str) -> AlternativeDataPoint:
        now = datetime.now(UTC)
        payload = {"value": 1.0}
        return AlternativeDataPoint("dummy", symbol, now, payload, self.quality_score(payload), self.is_stale(now))

    def normalize_data(self, payload: dict[str, float]) -> dict[str, float]:
        return payload


def test_alternative_data_base_scores_quality_and_staleness() -> None:
    source = DummySource()
    point = source.get_data("BTCUSDT")

    assert source.validate_quality(point) is True
    assert source.is_stale(datetime.now(UTC) - timedelta(minutes=6), now=datetime.now(UTC)) is True


def test_social_sentiment_source_normalizes_scores() -> None:
    source = SocialSentimentSource(
        twitter_posts=["BTC bull breakout moon"],
        reddit_posts=["Fear after crash but recovery gain"],
    )

    point = source.get_data("BTCUSDT")
    normalized = source.normalize_data(point.value)

    assert -1.0 <= normalized["twitter_sentiment"] <= 1.0
    assert -1.0 <= normalized["reddit_sentiment"] <= 1.0
    assert point.source == "social_sentiment"


def test_news_sentiment_source_extracts_topics() -> None:
    source = NewsSentimentSource(
        articles=[
            {"title": "ETF approval drives surge", "body": "Regulation clarity and funding demand rise"},
            {"title": "Exchange hack sparks concern", "body": "Security review underway"},
        ]
    )

    point = source.get_data("BTCUSDT")
    normalized = source.normalize_data(point.value)

    assert point.source == "news_sentiment"
    assert -1.0 <= normalized["sentiment"] <= 1.0
    assert 0.0 <= normalized["topic_relevance"] <= 1.0
