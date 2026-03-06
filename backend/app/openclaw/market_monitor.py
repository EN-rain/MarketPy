"""Autonomous market monitor for conditions and proactive analysis."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean
from typing import Any, Protocol

from .command_executor import CommandExecutor
from .discord_bridge import DiscordBridge
from .logging import StructuredLogger
from .models import CommandType, MarketCondition, TradingCommand


class ExchangeDataClient(Protocol):
    async def fetch_ticker(self, symbol: str) -> dict[str, Any]: ...

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 120
    ) -> list[list[Any]]: ...


class MarketMonitor:
    """Background monitor evaluating user-defined market conditions."""

    def __init__(
        self,
        *,
        exchange_client: ExchangeDataClient,
        command_executor: CommandExecutor,
        discord_bridge: DiscordBridge | None = None,
        monitor_interval_seconds: int = 60,
        logger: StructuredLogger | None = None,
    ):
        self._exchange_client = exchange_client
        self._executor = command_executor
        self._discord = discord_bridge
        self._interval_seconds = monitor_interval_seconds
        self._logger = logger or StructuredLogger("openclaw.market_monitor")
        self._conditions: dict[str, MarketCondition] = {}
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())
        self._logger.info("Market monitor started", {"interval_seconds": self._interval_seconds})

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._logger.info("Market monitor stopped")

    async def add_condition(self, condition: MarketCondition) -> str:
        errors = condition.validate()
        if errors:
            raise ValueError("; ".join(errors))
        self._conditions[condition.condition_id] = condition
        self._logger.info("Condition added", {"condition_id": condition.condition_id})
        return condition.condition_id

    async def remove_condition(self, condition_id: str) -> bool:
        return self._conditions.pop(condition_id, None) is not None

    async def list_conditions(self, user_id: str) -> list[MarketCondition]:
        return [cond for cond in self._conditions.values() if cond.user_id == user_id]

    async def evaluate_conditions(self) -> list[tuple[MarketCondition, dict[str, Any]]]:
        by_symbol: dict[str, list[MarketCondition]] = defaultdict(list)
        for condition in self._conditions.values():
            if condition.enabled:
                by_symbol[condition.symbol.upper()].append(condition)

        triggered: list[tuple[MarketCondition, dict[str, Any]]] = []
        for symbol, conditions in by_symbol.items():
            ticker = await self._exchange_client.fetch_ticker(symbol)
            market_data = self._normalize_ticker(ticker)
            for condition in conditions:
                if condition.evaluate(market_data):
                    condition.last_triggered = datetime.now(UTC)
                    triggered.append((condition, market_data))
        return triggered

    async def market_analysis(self, symbol: str) -> dict[str, Any]:
        candles = await self._exchange_client.fetch_ohlcv(symbol, timeframe="1h", limit=120)
        closes = [float(candle[4]) for candle in candles if len(candle) >= 5]
        volumes = [float(candle[5]) for candle in candles if len(candle) >= 6]
        if len(closes) < 20:
            return {
                "symbol": symbol.upper(),
                "summary": "Insufficient data for analysis",
                "support": None,
                "resistance": None,
                "pattern": "unknown",
            }

        support = min(closes[-20:])
        resistance = max(closes[-20:])
        avg_volume = mean(volumes[-20:]) if volumes else 0.0
        trend = "bullish" if closes[-1] > mean(closes[-20:]) else "bearish"
        pattern = self._detect_pattern(closes[-30:])
        return {
            "symbol": symbol.upper(),
            "support": support,
            "resistance": resistance,
            "trend": trend,
            "pattern": pattern,
            "average_volume_20": avg_volume,
        }

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval_seconds)
                triggered = await self.evaluate_conditions()
                for condition, snapshot in triggered:
                    await self._execute_action(condition, snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error("Market monitor loop error", {"error": str(exc)})

    async def _execute_action(self, condition: MarketCondition, snapshot: dict[str, Any]) -> None:
        self._logger.info(
            "Condition triggered",
            {
                "condition_id": condition.condition_id,
                "user_id": condition.user_id,
                "symbol": condition.symbol,
            },
        )
        if condition.action == "notify":
            if self._discord:
                content = (
                    f"📈 Condition triggered: `{condition.condition_type}` on {condition.symbol}\n"
                    f"Current price: {snapshot.get('price')}"
                )
                channel = condition.action_params.get("channel_id", "")
                if channel:
                    await self._discord.send_message(channel, content)
            return

        if condition.action == "execute_order":
            side = str(condition.action_params.get("side", "buy"))
            size = float(condition.action_params.get("quantity", 0.0))
            command = TradingCommand(
                command_type=CommandType.PLACE_ORDER,
                user_id=condition.user_id,
                symbol=condition.symbol,
                action=side,
                quantity=size,
                parameters={},
            )
            await self._executor.execute(command)
            return

        if condition.action == "run_analysis":
            analysis = await self.market_analysis(condition.symbol)
            channel = condition.action_params.get("channel_id", "")
            if self._discord and channel:
                summary = (
                    f"Trend: {analysis.get('trend')}, "
                    f"Pattern: {analysis.get('pattern')}"
                )
                embed = self._discord.create_embed(
                    title=f"Market Analysis: {condition.symbol}",
                    description=summary,
                    fields=analysis,
                )
                await self._discord.send_message(channel, "Market analysis update", embeds=[embed])

    @staticmethod
    def _normalize_ticker(payload: dict[str, Any]) -> dict[str, float]:
        price = float(
            payload.get("price")
            or payload.get("last")
            or payload.get("mid")
            or payload.get("data", {}).get("price", 0.0)
        )
        previous = float(payload.get("previous_price") or payload.get("open", price))
        volume = float(payload.get("volume") or payload.get("baseVolume", 0.0))
        average_volume = float(payload.get("average_volume") or max(volume, 1.0))
        rsi = float(payload.get("rsi", 50.0))
        return {
            "price": price,
            "previous_price": previous,
            "volume": volume,
            "average_volume": average_volume,
            "rsi": rsi,
        }

    @staticmethod
    def _detect_pattern(closes: list[float]) -> str:
        if len(closes) < 10:
            return "unknown"
        mid = len(closes) // 2
        left_avg = mean(closes[:mid])
        right_avg = mean(closes[mid:])
        if right_avg > left_avg * 1.02:
            return "ascending_channel"
        if right_avg < left_avg * 0.98:
            return "descending_channel"
        return "range"
