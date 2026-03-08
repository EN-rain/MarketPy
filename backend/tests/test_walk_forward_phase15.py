"""Phase 15 walk-forward optimization tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.sim.walk_forward import WalkForwardOptimizer


def _make_frame(days: int = 240) -> pd.DataFrame:
    timestamps = [datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index) for index in range(days)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": [100.0 + index * 0.1 for index in range(days)],
            "volume": [1_000.0 + index for index in range(days)],
        }
    )


@pytest.mark.property_test
@settings(max_examples=20)
@given(
    total_days=st.integers(min_value=150, max_value=400),
    train_days=st.integers(min_value=30, max_value=120),
    validation_days=st.integers(min_value=10, max_value=60),
)
def test_property_walk_forward_temporal_ordering(total_days: int, train_days: int, validation_days: int) -> None:
    frame = _make_frame(total_days)
    result = WalkForwardOptimizer().run_walk_forward(
        frame,
        train_days=train_days,
        validation_days=validation_days,
        step_days=max(1, validation_days),
    )
    for window in result.windows:
        assert window.train_start < window.train_end <= window.validation_start < window.validation_end


def test_walk_forward_framework_checkpoint() -> None:
    frame = _make_frame(240)
    result = WalkForwardOptimizer().run_walk_forward(frame, train_days=90, validation_days=30, step_days=30)
    assert result.windows
    assert result.metrics
    assert all(window.train_rows > 0 and window.validation_rows > 0 for window in result.windows)
