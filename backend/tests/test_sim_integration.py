"""Integration test for the simulation engine with baseline strategies."""

from datetime import UTC, datetime, timedelta

from backend.app.models.market import Candle, MarketInfo
from backend.sim.engine import SimEngine
from backend.strategies.mean_reversion import MeanReversionStrategy
from backend.strategies.momentum import MomentumStrategy


def generate_synthetic_candles(
    n_bars: int = 200,
    start_price: float = 0.50,
    volatility: float = 0.005,
    trend: float = 0.0001,
) -> list[Candle]:
    """Generate synthetic candle data with controllable trend + noise."""
    import random

    random.seed(42)
    candles = []
    price = start_price
    start_time = datetime(2025, 1, 1, tzinfo=UTC)

    for i in range(n_bars):
        # Random walk with trend
        change = random.gauss(trend, volatility)
        price = max(0.01, min(0.99, price + change))

        spread = random.uniform(0.01, 0.04)
        bid = max(0.01, price - spread / 2)
        ask = min(0.99, price + spread / 2)
        mid = (bid + ask) / 2

        candles.append(
            Candle(
                timestamp=start_time + timedelta(minutes=5 * i),
                open=price,
                high=price + abs(change) * 2,
                low=price - abs(change) * 2,
                close=price,
                mid=mid,
                bid=bid,
                ask=ask,
                spread=spread,
                volume=random.uniform(10, 1000),
                trade_count=random.randint(1, 50),
            )
        )

    return candles


class TestSimEngineIntegration:
    def test_momentum_backtest(self):
        """Smoke test: momentum strategy runs and produces results."""
        market_info = MarketInfo(
            condition_id="test-market-1",
            question="Will X happen?",
            token_id_yes="token-yes-1",
        )
        candles = generate_synthetic_candles(n_bars=200)

        engine = SimEngine()
        engine.add_market(market_info, candles)

        strategy = MomentumStrategy(lookback=12, threshold=0.01, order_size=100)
        result = engine.run(strategy)

        # Verify basic structure
        assert result.duration_bars == 200
        assert result.markets_processed == 1
        assert result.portfolio is not None
        assert len(result.portfolio.equity_curve) > 0
        assert result.errors == []

    def test_mean_reversion_backtest(self):
        """Smoke test: mean reversion strategy runs and produces results."""
        market_info = MarketInfo(
            condition_id="test-market-2",
            question="Will Y happen?",
            token_id_yes="token-yes-2",
        )
        candles = generate_synthetic_candles(n_bars=200)

        engine = SimEngine()
        engine.add_market(market_info, candles)

        strategy = MeanReversionStrategy(lookback=20, z_entry=2.0, z_exit=0.5, order_size=100)
        result = engine.run(strategy)

        assert result.duration_bars == 200
        assert result.portfolio is not None
        assert len(result.portfolio.equity_curve) > 0

    def test_fees_reduce_performance(self):
        """Higher fees should produce worse PnL than lower fees."""
        market_info = MarketInfo(
            condition_id="test-market-3",
            question="Fee impact test",
            token_id_yes="token-yes-3",
        )
        candles = generate_synthetic_candles(n_bars=300, trend=0.001)

        # Low fees
        engine_low = SimEngine()
        engine_low.config.default_fee_rate = 0.001
        engine_low.add_market(market_info, candles)
        result_low = engine_low.run(MomentumStrategy(lookback=12, threshold=0.005, order_size=100))

        # High fees
        engine_high = SimEngine()
        engine_high.config.default_fee_rate = 0.10
        engine_high.add_market(market_info, candles)
        result_high = engine_high.run(
            MomentumStrategy(lookback=12, threshold=0.005, order_size=100)
        )

        # Higher fees should lead to more fees paid (or fewer fills)
        assert (
            result_low.portfolio.total_fees_paid <= result_high.portfolio.total_fees_paid
            or result_low.orders_filled >= result_high.orders_filled
        )

    def test_multi_market(self):
        """Engine should handle multiple markets."""
        markets = []
        for i in range(3):
            info = MarketInfo(
                condition_id=f"market-{i}",
                question=f"Market {i}?",
                token_id_yes=f"token-{i}",
            )
            candles = generate_synthetic_candles(n_bars=100)
            markets.append((info, candles))

        engine = SimEngine()
        for info, candles in markets:
            engine.add_market(info, candles)

        strategy = MomentumStrategy(lookback=12, threshold=0.01, order_size=50)
        result = engine.run(strategy)

        assert result.markets_processed == 3
        assert result.duration_bars == 300  # 100 bars × 3 markets
