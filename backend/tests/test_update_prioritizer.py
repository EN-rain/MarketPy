"""Unit tests for UpdatePrioritizer component."""

from datetime import datetime

import pytest

from backend.app.models.realtime import PreviousMarketState, RealtimeMarketUpdate, UpdatePriority
from backend.app.models.realtime_config import PrioritizerConfig
from backend.app.realtime.update_prioritizer import UpdatePrioritizer


class TestUpdatePrioritizer:
    """Test suite for UpdatePrioritizer."""

    @pytest.fixture
    def config(self):
        """Create default prioritizer config."""
        return PrioritizerConfig(
            price_change_threshold=0.02,  # 2%
            volume_spike_multiplier=3.0,
            critical_event_types=["order_fill", "trade_execution"]
        )

    @pytest.fixture
    def prioritizer(self, config):
        """Create UpdatePrioritizer instance."""
        return UpdatePrioritizer(config)

    def test_first_update_is_critical(self, prioritizer):
        """First update for a market (no previous state) should be critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        result = prioritizer.classify(update, None)

        assert result == UpdatePriority.CRITICAL

    def test_critical_event_type(self, prioritizer):
        """Updates with critical event types should be classified as critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="order_fill",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_price_change_exceeds_threshold(self, prioritizer):
        """Price change exceeding threshold should be critical."""
        # 3% price increase (exceeds 2% threshold)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=51500.0  # 3% increase from 50000
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_price_change_at_threshold(self, prioritizer):
        """Price change exactly at threshold should be non-critical."""
        # Exactly 2% price increase (at threshold, not exceeding)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=51000.0  # 2% increase from 50000
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_negative_price_change_exceeds_threshold(self, prioritizer):
        """Negative price change exceeding threshold should be critical."""
        # 3% price decrease (exceeds 2% threshold)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=48500.0  # 3% decrease from 50000
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_small_price_change_is_non_critical(self, prioritizer):
        """Small price change below threshold should be non-critical."""
        # 1% price increase (below 2% threshold)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50500.0  # 1% increase from 50000
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_zero_price_change(self, prioritizer):
        """Zero price change should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_missing_current_price(self, prioritizer):
        """Update with no price data should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={}
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_missing_previous_price(self, prioritizer):
        """Update with no previous price should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=None
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_zero_previous_price(self, prioritizer):
        """Update with zero previous price should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=0.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_price_from_last_trade(self, prioritizer):
        """Should use last_trade when mid is not available."""
        # 3% price increase using last_trade
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            last_trade=51500.0  # 3% increase from 50000
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_price_from_bid_ask_average(self, prioritizer):
        """Should use average of bid/ask when mid and last_trade not available."""
        # 3% price increase using bid/ask average
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            bid=51400.0,
            ask=51600.0  # Average: 51500 (3% increase from 50000)
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_volume_spike_exceeds_threshold(self, prioritizer):
        """Volume spike exceeding threshold should be critical."""
        # 4x volume increase (exceeds 3x threshold)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={"volume": 4000.0},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=1000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_volume_spike_at_threshold(self, prioritizer):
        """Volume spike exactly at threshold should be non-critical."""
        # Exactly 3x volume increase (at threshold, not exceeding)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={"volume": 3000.0},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=1000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_volume_increase_below_threshold(self, prioritizer):
        """Volume increase below threshold should be non-critical."""
        # 2x volume increase (below 3x threshold)
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={"volume": 2000.0},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=1000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_missing_current_volume(self, prioritizer):
        """Update with no volume data should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=1000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_missing_previous_volume(self, prioritizer):
        """Update with no previous volume should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={"volume": 4000.0},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=None
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_zero_previous_volume(self, prioritizer):
        """Update with zero previous volume should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={"volume": 4000.0},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=0.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_is_critical_method(self, prioritizer):
        """is_critical() should return boolean matching classify() result."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="order_fill",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        is_critical = prioritizer.is_critical(update, previous_state)
        classification = prioritizer.classify(update, previous_state)

        assert is_critical == (classification == UpdatePriority.CRITICAL)
        assert is_critical is True

    def test_unknown_event_type(self, prioritizer):
        """Unknown event types should be non-critical."""
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="unknown_event",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_configurable_critical_event_types(self):
        """Should support configurable critical event types."""
        config = PrioritizerConfig(
            price_change_threshold=0.02,
            volume_spike_multiplier=3.0,
            critical_event_types=["custom_event", "another_event"]
        )
        prioritizer = UpdatePrioritizer(config)

        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="custom_event",
            data={},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.CRITICAL

    def test_configurable_price_threshold(self):
        """Should support configurable price change threshold."""
        config = PrioritizerConfig(
            price_change_threshold=0.05,  # 5% threshold
            volume_spike_multiplier=3.0,
            critical_event_types=[]
        )
        prioritizer = UpdatePrioritizer(config)

        # 3% change should be non-critical with 5% threshold
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={},
            mid=51500.0  # 3% increase from 50000
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL

    def test_configurable_volume_multiplier(self):
        """Should support configurable volume spike multiplier."""
        config = PrioritizerConfig(
            price_change_threshold=0.02,
            volume_spike_multiplier=5.0,  # 5x threshold
            critical_event_types=[]
        )
        prioritizer = UpdatePrioritizer(config)

        # 4x volume increase should be non-critical with 5x threshold
        update = RealtimeMarketUpdate(
            market_id="BTC/USD",
            timestamp=datetime.now(),
            event_type="ticker",
            data={"volume": 4000.0},
            mid=50000.0
        )

        previous_state = PreviousMarketState(
            market_id="BTC/USD",
            last_price=50000.0,
            last_volume=1000.0
        )

        result = prioritizer.classify(update, previous_state)

        assert result == UpdatePriority.NON_CRITICAL
