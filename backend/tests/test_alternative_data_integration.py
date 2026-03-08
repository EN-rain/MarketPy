from __future__ import annotations

from pathlib import Path

from backend.ingest.alternative_data.funding import FundingRateSource
from backend.ingest.alternative_data.integrator import AlternativeDataIntegrator
from backend.ingest.alternative_data.liquidations import LiquidationDataSource
from backend.ingest.alternative_data.news import NewsSentimentSource
from backend.ingest.alternative_data.onchain import OnChainMetricsSource
from backend.ingest.alternative_data.sentiment import SocialSentimentSource


def test_onchain_funding_and_liquidation_sources_normalize() -> None:
    onchain = OnChainMetricsSource(1_000_000, 120_000, 15.0, 200_000, -0.1)
    funding = FundingRateSource({"binance": 0.01, "bybit": 0.02})
    liquidations = LiquidationDataSource(500_000, 200_000, {"62000": 300_000})

    assert onchain.normalize_data(onchain.get_data("BTCUSDT").value)["active_addresses"] == 120000.0
    assert funding.normalize_data(funding.get_data("BTCUSDT").value)["anomaly_spread"] == 0.01
    assert 0.0 <= liquidations.normalize_data(liquidations.get_data("BTCUSDT").value)["cascade_risk"] <= 1.0


def test_alternative_data_integrator_collects_and_persists(tmp_path: Path) -> None:
    integrator = AlternativeDataIntegrator(
        sentiment_source=SocialSentimentSource(["bull breakout"], ["bear loss"]),
        funding_source=FundingRateSource({"binance": 0.01}),
        liquidation_source=LiquidationDataSource(100_000, 50_000, {"61000": 80_000}),
        onchain_source=OnChainMetricsSource(1_000_000, 120_000, 15.0, 200_000, -0.1),
        news_source=NewsSentimentSource([{"title": "ETF approval drives surge", "body": "regulation"}]),
        storage_path=tmp_path / "alternative_data.json",
    )

    payload = integrator.collect_all("BTCUSDT")

    assert {"sentiment", "funding", "liquidations", "onchain", "news"} <= set(payload)
    assert (tmp_path / "alternative_data.json").exists()
