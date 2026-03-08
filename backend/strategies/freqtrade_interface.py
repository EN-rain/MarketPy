"""Freqtrade-style strategy interface for dataframe-driven execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pandas is required for FreqtradeStrategy") from exc


@dataclass(slots=True)
class StrategyConfig:
    minimal_roi: dict[str, float] = field(default_factory=lambda: {"0": 0.01})
    stoploss: float = -0.1
    timeframe: str = "1m"
    execution_mode: str = "candle"


class FreqtradeStrategy(ABC):
    """Base contract mirroring freqtrade populate_* methods."""

    strategy_name: str = "freqtrade_strategy"

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()
        self.minimal_roi = self.config.minimal_roi
        self.stoploss = self.config.stoploss
        self.execution_mode = self.config.execution_mode

    @abstractmethod
    def populate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def populate_entry_trend(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def populate_exit_trend(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


class ExampleSMAStrategy(FreqtradeStrategy):
    """Reference strategy using SMA crossover."""

    strategy_name = "example_sma"

    def __init__(self, fast_period: int = 10, slow_period: int = 30) -> None:
        super().__init__(StrategyConfig())
        self.fast_period = fast_period
        self.slow_period = slow_period

    def populate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe = dataframe.copy()
        dataframe["sma_fast"] = dataframe["close"].rolling(self.fast_period).mean()
        dataframe["sma_slow"] = dataframe["close"].rolling(self.slow_period).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe = dataframe.copy()
        dataframe["enter_long"] = dataframe["sma_fast"] > dataframe["sma_slow"]
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe = dataframe.copy()
        dataframe["exit_long"] = dataframe["sma_fast"] < dataframe["sma_slow"]
        return dataframe


def has_freqtrade_interface(strategy: Any) -> bool:
    return all(
        hasattr(strategy, method)
        for method in ("populate_indicators", "populate_entry_trend", "populate_exit_trend")
    )
