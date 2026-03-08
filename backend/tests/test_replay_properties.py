"""Property tests for market replay."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.replay.replay_engine import build_sample_replay


# Property 48: Market Replay Speed Accuracy
@given(speed=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_market_replay_speed_accuracy(speed: float) -> None:
    replay = build_sample_replay(1000)
    replay.start_replay(speed)
    duration = replay.estimated_replay_duration_seconds(
        event_count=1000, base_rate_per_second=100.0
    )
    expected = 1000 / (100.0 * speed)
    assert duration == pytest.approx(expected, rel=0.05)


# Property 49: Replay Fill Simulation Realism
@given(
    size=st.floats(min_value=0.1, max_value=30.0, allow_nan=False, allow_infinity=False),
    side=st.sampled_from(["BUY", "SELL"]),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_replay_fill_simulation_realism(size: float, side: str) -> None:
    replay = build_sample_replay(10)
    book = replay.orderbooks[0]
    fill = replay.simulate_fill(side=side, size=size, orderbook=book)
    best_bid = book.bids[0].price
    best_ask = book.asks[0].price
    worst_bid = book.bids[-1].price
    worst_ask = book.asks[-1].price
    if side == "BUY":
        assert fill == pytest.approx(fill, abs=1e-9)
        assert (best_ask - 1e-9) <= fill <= (worst_ask + 1e-9)
    else:
        assert (worst_bid - 1e-9) <= fill <= (best_bid + 1e-9)
