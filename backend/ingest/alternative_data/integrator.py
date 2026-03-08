"""Alternative data integrator."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .base import AlternativeDataPoint
from .funding import FundingRateSource
from .liquidations import LiquidationDataSource
from .news import NewsSentimentSource
from .onchain import OnChainMetricsSource
from .sentiment import SocialSentimentSource


class AlternativeDataIntegrator:
    def __init__(
        self,
        *,
        sentiment_source: SocialSentimentSource | None = None,
        funding_source: FundingRateSource | None = None,
        liquidation_source: LiquidationDataSource | None = None,
        onchain_source: OnChainMetricsSource | None = None,
        news_source: NewsSentimentSource | None = None,
        storage_path: str | Path | None = None,
    ) -> None:
        self.sentiment_source = sentiment_source
        self.funding_source = funding_source
        self.liquidation_source = liquidation_source
        self.onchain_source = onchain_source
        self.news_source = news_source
        self.storage_path = Path(storage_path) if storage_path else None

    def _persist(self, points: list[AlternativeDataPoint]) -> None:
        if self.storage_path is None:
            return
        payload = [asdict(point) for point in points]
        self.storage_path.write_text(json.dumps(payload, default=str, ensure_ascii=True), encoding="utf-8")

    def get_sentiment(self, symbol: str) -> dict[str, float]:
        if self.sentiment_source is None:
            return {}
        point = self.sentiment_source.get_data(symbol)
        self._persist([point])
        return self.sentiment_source.normalize_data(point.value)

    def get_funding_rates(self, symbol: str) -> dict[str, float]:
        if self.funding_source is None:
            return {}
        point = self.funding_source.get_data(symbol)
        self._persist([point])
        return self.funding_source.normalize_data(point.value)

    def get_liquidations(self, symbol: str) -> dict[str, float]:
        if self.liquidation_source is None:
            return {}
        point = self.liquidation_source.get_data(symbol)
        self._persist([point])
        return self.liquidation_source.normalize_data(point.value)

    def get_on_chain_metrics(self, symbol: str) -> dict[str, float]:
        if self.onchain_source is None:
            return {}
        point = self.onchain_source.get_data(symbol)
        self._persist([point])
        return self.onchain_source.normalize_data(point.value)

    def get_news(self, symbol: str) -> dict[str, float]:
        if self.news_source is None:
            return {}
        point = self.news_source.get_data(symbol)
        self._persist([point])
        return self.news_source.normalize_data(point.value)

    def collect_all(self, symbol: str) -> dict[str, dict[str, float]]:
        results = {
            "sentiment": self.get_sentiment(symbol),
            "funding": self.get_funding_rates(symbol),
            "liquidations": self.get_liquidations(symbol),
            "onchain": self.get_on_chain_metrics(symbol),
            "news": self.get_news(symbol),
        }
        return {key: value for key, value in results.items() if value}
