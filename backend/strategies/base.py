"""Abstract base class for all trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.models.market import MarketState
from backend.app.models.portfolio import Portfolio
from backend.sim.engine import Order


class Strategy(ABC):
    """Base strategy interface.

    All strategies must implement `on_bar` which is called
    once per bar/tick by the simulation engine.
    """

    name: str = "base"

    @abstractmethod
    def on_bar(
        self,
        markets: dict[str, MarketState],
        portfolio: Portfolio,
    ) -> list[Order]:
        """Generate orders based on current market state and portfolio.

        Args:
            markets: Dict of market_id -> current MarketState.
            portfolio: Current portfolio state.

        Returns:
            List of orders to submit.
        """
        ...

    def reset(self) -> None:
        """Reset strategy state (called between backtests)."""
        pass
