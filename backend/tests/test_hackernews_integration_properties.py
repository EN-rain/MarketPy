"""Property tests for Hacker News sentiment integration.

Validates:
- Property 16: Sentiment Classification Validity
- Property 14: Alert Threshold Triggering (sentiment shift)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.hackernews_client import HackerNewsClient
from backend.app.models.market import SentimentScore


# Property 16: Sentiment Classification Validity
@given(
    positive_posts=st.integers(min_value=0, max_value=100),
    negative_posts=st.integers(min_value=0, max_value=100),
    neutral_posts=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_sentiment_classification_validity(
    positive_posts: int, negative_posts: int, neutral_posts: int
) -> None:
    posts: list[dict[str, str]] = []
    posts.extend({"title": "bullish adoption breakout"} for _ in range(positive_posts))
    posts.extend({"title": "bearish crash scam"} for _ in range(negative_posts))
    posts.extend({"title": "market update"} for _ in range(neutral_posts))

    score = HackerNewsClient.analyze_sentiment(posts)
    assert -1.0 <= score.score <= 1.0

    if positive_posts > negative_posts:
        assert score.score >= 0
    elif negative_posts > positive_posts:
        assert score.score <= 0


# Property 14 (sentiment context): shift alerts
@given(
    baseline=st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
    shift=st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_sentiment_shift_alerts_triggered(baseline: float, shift: float) -> None:
    client = HackerNewsClient()
    now = datetime.now(UTC)
    client._history = [  # noqa: SLF001 - intentional internal state setup for property testing
        SentimentScore(
            source="hackernews",
            score=baseline,
            positive_count=1,
            negative_count=1,
            neutral_count=1,
            timestamp=now - timedelta(minutes=10 - i),
        )
        for i in range(5)
    ]
    client._history.append(  # noqa: SLF001 - intentional internal state setup for property testing
        SentimentScore(
            source="hackernews",
            score=max(-1.0, min(1.0, baseline + shift)),
            positive_count=10,
            negative_count=0,
            neutral_count=0,
            timestamp=now,
        )
    )

    signal = client.detect_sentiment_shift(threshold_stddev=0.5)
    assert signal is not None
    assert signal["z_score"] > 0.5

