"""Tests for ML pipeline guardrails (log-return labels + embargo split)."""

from datetime import UTC, datetime, timedelta

import polars as pl

from backend.dataset.features import add_labels
from backend.ml.trainer import walk_forward_split


def _make_df(n: int = 120) -> pl.DataFrame:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        mid = min(0.99, max(0.01, 0.5 + (i - n / 2) * 0.001))
        rows.append(
            {
                "timestamp": start + timedelta(minutes=5 * i),
                "token_id": "m1",
                "mid": mid,
                "spread": 0.01,
            }
        )
    return pl.DataFrame(rows)


class TestMLPipelineGuards:
    def test_add_labels_log_return_is_finite(self):
        df = _make_df(80)
        out = add_labels(df, horizons={"y_1h": 12}, embargo_bars=12)
        non_null = out.select("y_1h").drop_nulls()
        assert len(non_null) > 0
        assert non_null["y_1h"].is_nan().sum() == 0

    def test_walk_forward_split_respects_embargo(self):
        df = _make_df(100)
        train_df, val_df, test_df = walk_forward_split(df, train_pct=0.6, val_pct=0.2, embargo_bars=5)
        # Sizes with embargo: train=60, val indices [65:80] => 15, test [85:] => 15
        assert len(train_df) == 60
        assert len(val_df) == 15
        assert len(test_df) == 15
