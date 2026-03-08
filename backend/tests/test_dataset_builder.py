"""Tests for dataset integrity safeguards in builder."""

from datetime import UTC, datetime

import polars as pl

from backend.dataset.builder import events_to_dataframe


class TestDatasetBuilder:
    def test_events_to_dataframe_uses_exchange_timestamp(self):
        ts_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
        events = [
            {
                "event_type": "last_trade_price",
                "asset_id": "token-1",
                "ts": ts_ms,
                "price": 0.51,
                "size": 10,
                "_recorded_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        df = events_to_dataframe(events)
        assert not df.is_empty()
        assert df["timestamp"][0] == datetime(2025, 1, 1, tzinfo=UTC)

    def test_events_to_dataframe_filters_invalid_price_and_inverted_bba(self):
        events = [
            {
                "event_type": "last_trade_price",
                "asset_id": "token-1",
                "_recorded_at": "2026-01-01T00:00:00+00:00",
                "price": -1.0,  # invalid negative price
                "size": 10,
            },
            {
                "event_type": "best_bid_ask",
                "asset_id": "token-1",
                "_recorded_at": "2026-01-01T00:00:01+00:00",
                "best_bid": 0.7,
                "best_ask": 0.6,  # inverted spread
            },
        ]
        df = events_to_dataframe(events)
        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()
