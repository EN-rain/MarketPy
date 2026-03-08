"""Unit tests for adaptive cooldown in PaperTradingEngine."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.paper_trading.engine import PaperTradingEngine
from backend.paper_trading.live_feed import LiveFeedUpdate


@pytest.mark.asyncio
async def test_cooldown_bounds():
    engine = PaperTradingEngine()
    engine.start()
    market = "BTCUSDT"
    t0 = datetime.now(UTC)
    prices = [100.0, 100.1, 100.2, 100.15, 100.18]
    for i, p in enumerate(prices):
        update = LiveFeedUpdate(
            market_id=market,
            timestamp=t0 + timedelta(seconds=i),
            event_type="ticker",
            data={},
            mid=p,
            bid=p - 0.01,
            ask=p + 0.01,
        )
        await engine.on_market_update(update)
    cd = engine.get_market_cooldown(market)
    assert engine.min_signal_cooldown <= cd <= engine.max_signal_cooldown

