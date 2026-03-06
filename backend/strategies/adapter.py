"""Adapters for backward compatibility between legacy and freqtrade-style strategies."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.app.models.market import Side
from backend.sim.engine import Order
from backend.strategies.freqtrade_interface import FreqtradeStrategy, StrategyConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AdapterContext:
    markets_provider: Callable[[], dict[str, Any]]
    portfolio_provider: Callable[[], Any]
    order_size: float = 1.0


class StrategyAdapter(FreqtradeStrategy):
    """Wraps a legacy `on_bar` strategy with freqtrade populate_* methods."""

    _warned_types: set[type[Any]] = set()

    def __init__(self, legacy_strategy: Any, context: AdapterContext) -> None:
        super().__init__(StrategyConfig())
        self.legacy_strategy = legacy_strategy
        self.context = context
        self.strategy_name = f"adapter:{legacy_strategy.__class__.__name__}"
        self._warn_deprecation()

    def _warn_deprecation(self) -> None:
        strategy_type = type(self.legacy_strategy)
        if strategy_type in self._warned_types:
            return
        self._warned_types.add(strategy_type)
        message = (
            f"Legacy strategy interface `{strategy_type.__name__}` is deprecated. "
            "Migrate to FreqtradeStrategy populate_* methods."
        )
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        logger.warning(message)

    def _extract_latest_order(self, dataframe: pd.DataFrame) -> Order | None:
        try:
            orders = self.legacy_strategy.on_bar(
                markets=self.context.markets_provider(),
                portfolio=self.context.portfolio_provider(),
            )
        except Exception as exc:
            logger.warning("Legacy strategy execution failed in adapter: %s", exc)
            return None
        if not orders:
            return None
        return orders[-1]

    def populate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        return dataframe.copy()

    def populate_entry_trend(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe = dataframe.copy()
        dataframe["enter_long"] = False
        order = self._extract_latest_order(dataframe)
        if order is not None and order.side == Side.BUY:
            dataframe.iloc[-1, dataframe.columns.get_loc("enter_long")] = True
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe = dataframe.copy()
        dataframe["exit_long"] = False
        order = self._extract_latest_order(dataframe)
        if order is not None and order.side == Side.SELL:
            dataframe.iloc[-1, dataframe.columns.get_loc("exit_long")] = True
        return dataframe
