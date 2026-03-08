"""Unit tests for replay cursor behavior."""

from __future__ import annotations

import pytest

from backend.app.replay.replay_engine import build_sample_replay


def test_replay_streams_maintain_independent_cursors() -> None:
    replay = build_sample_replay(10)
    replay.start_replay(speed=1.0)

    orderbooks_a = replay.stream_orderbook(limit=3)
    trades_a = replay.stream_trades(limit=2)
    orderbooks_b = replay.stream_orderbook(limit=2)
    trades_b = replay.stream_trades(limit=2)

    assert [item.price for item in trades_a] == pytest.approx([100.0, 100.01])
    assert [item.price for item in trades_b] == pytest.approx([100.02, 100.03])
    assert [book.bids[0].price for book in orderbooks_a] == pytest.approx([99.95, 99.96, 99.97])
    assert [book.bids[0].price for book in orderbooks_b] == pytest.approx([99.98, 99.99])


def test_replay_seek_updates_both_stream_positions() -> None:
    replay = build_sample_replay(8)
    replay.start_replay(speed=1.0)

    replay.seek(5)
    orderbook = replay.stream_orderbook(limit=1)
    trades = replay.stream_trades(limit=1)

    assert orderbook and orderbook[0].bids[0].price == pytest.approx(100.0)
    assert trades and trades[0].price == pytest.approx(100.05)
