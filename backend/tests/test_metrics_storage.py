"""Tests for SQLite metrics storage tables and persistence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.app.execution.slippage_tracker import SlippageRecord
from backend.app.models.market import MarketMetrics, OnChainMetrics, SentimentScore
from backend.app.storage.metrics_store import MetricsStore


def test_metrics_store_creates_required_tables(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))
    try:
        assert store.count_rows("market_metrics") == 0
        assert store.count_rows("onchain_metrics") == 0
        assert store.count_rows("sentiment_scores") == 0
        assert store.count_rows("slippage_records") == 0
    finally:
        store.close()


def test_metrics_store_persists_market_onchain_and_sentiment_rows(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))
    try:
        store.insert_market_metrics(
            MarketMetrics(
                coin_id="btc-bitcoin",
                volume_24h=1.0,
                market_cap=2.0,
                circulating_supply=3.0,
                total_supply=4.0,
                max_supply=5.0,
                timestamp=datetime.now(UTC),
            )
        )
        store.insert_onchain_metrics(
            OnChainMetrics(
                timestamp=datetime.now(UTC),
                mempool_size_mb=10.0,
                fee_rate_sat_vb=20.0,
                hash_rate_eh_s=30.0,
                difficulty=40.0,
            )
        )
        store.insert_sentiment_score(
            SentimentScore(
                source="hackernews",
                score=0.5,
                positive_count=10,
                negative_count=2,
                neutral_count=3,
                timestamp=datetime.now(UTC),
            )
        )
        assert store.count_rows("market_metrics") == 1
        assert store.count_rows("onchain_metrics") == 1
        assert store.count_rows("sentiment_scores") == 1
    finally:
        store.close()


def test_metrics_store_persists_slippage_rows(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))
    try:
        store.insert_slippage_record(
            SlippageRecord(
                symbol="BTCUSDT",
                side="BUY",
                expected_price=100.0,
                executed_price=100.2,
                size=1.0,
                timestamp=datetime.now(UTC),
                volatility=0.2,
                volume=1000000.0,
                spread=0.05,
            )
        )
        assert store.count_rows("slippage_records") == 1
    finally:
        store.close()


def test_metrics_store_count_rows_rejects_unknown_tables(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))
    try:
        with pytest.raises(ValueError):
            store.count_rows("sqlite_master")
    finally:
        store.close()
