"""UpdatePrioritizer classifies market updates based on configurable criteria."""

from __future__ import annotations

from backend.app.models.realtime import PreviousMarketState, RealtimeMarketUpdate, UpdatePriority
from backend.app.models.realtime_config import PrioritizerConfig


class UpdatePrioritizer:
    """Classifies market updates as critical or non-critical based on configurable criteria.
    
    Critical conditions:
    - Price change exceeds threshold (e.g., 2%)
    - Order fill event
    - Volume spike (e.g., 3x increase)
    - First update for a market (no previous state)
    """

    def __init__(self, config: PrioritizerConfig):
        """Initialize UpdatePrioritizer with configuration.
        
        Args:
            config: Configuration parameters for prioritization
        """
        self.price_change_threshold = config.price_change_threshold
        self.volume_spike_multiplier = config.volume_spike_multiplier
        self.critical_event_types = config.critical_event_types

    def classify(self, update: RealtimeMarketUpdate, previous_state: PreviousMarketState | None) -> UpdatePriority:
        """Classify update as CRITICAL or NON_CRITICAL.
        
        Args:
            update: The market update to classify
            previous_state: Previous market state for comparison, None if first update
            
        Returns:
            UpdatePriority.CRITICAL or UpdatePriority.NON_CRITICAL
        """
        # First update for a market is always critical
        if previous_state is None:
            return UpdatePriority.CRITICAL

        # Check if event type is in critical list
        if update.event_type in self.critical_event_types:
            return UpdatePriority.CRITICAL

        # Check price change threshold
        if self._is_price_change_critical(update, previous_state):
            return UpdatePriority.CRITICAL

        # Check volume spike
        if self._is_volume_spike_critical(update, previous_state):
            return UpdatePriority.CRITICAL

        return UpdatePriority.NON_CRITICAL

    def is_critical(self, update: RealtimeMarketUpdate, previous_state: PreviousMarketState | None) -> bool:
        """Quick check if update is critical.
        
        Args:
            update: The market update to check
            previous_state: Previous market state for comparison, None if first update
            
        Returns:
            True if update is critical, False otherwise
        """
        return self.classify(update, previous_state) == UpdatePriority.CRITICAL

    def _is_price_change_critical(self, update: RealtimeMarketUpdate, previous_state: PreviousMarketState) -> bool:
        """Check if price change exceeds threshold.
        
        Args:
            update: The market update to check
            previous_state: Previous market state for comparison
            
        Returns:
            True if price change exceeds threshold, False otherwise
        """
        # Determine current price (prefer mid, then last_trade, then average of bid/ask)
        current_price = None
        if update.mid is not None:
            current_price = update.mid
        elif update.last_trade is not None:
            current_price = update.last_trade
        elif update.bid is not None and update.ask is not None:
            current_price = (update.bid + update.ask) / 2

        if current_price is None:
            return False

        # Get previous price
        previous_price = previous_state.last_price
        if previous_price is None or previous_price == 0:
            return False

        # Calculate percentage change
        price_change = abs((current_price - previous_price) / previous_price)

        return price_change > self.price_change_threshold

    def _is_volume_spike_critical(self, update: RealtimeMarketUpdate, previous_state: PreviousMarketState) -> bool:
        """Check if volume spike exceeds threshold.
        
        Args:
            update: The market update to check
            previous_state: Previous market state for comparison
            
        Returns:
            True if volume spike exceeds threshold, False otherwise
        """
        # Extract volume from update data if available
        current_volume = update.data.get('volume')
        if current_volume is None:
            return False

        previous_volume = previous_state.last_volume
        if previous_volume is None or previous_volume == 0:
            return False

        # Check if current volume exceeds previous volume by multiplier
        return current_volume > previous_volume * self.volume_spike_multiplier
