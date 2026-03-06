from __future__ import annotations

import pytest

from backend.app.openclaw.command_executor import CommandExecutor
from backend.app.openclaw.config import DiscordSettings, KimiK2Settings, OpenClawConfig
from backend.app.openclaw.discord_bridge import DiscordBridge, InMemoryBotAdapter
from backend.app.openclaw.market_monitor import MarketMonitor
from backend.app.openclaw.models import MarketCondition


class _FakeExchange:
    async def fetch_ticker(self, symbol: str):
        return {
            "price": 42000.0,
            "open": 41000.0,
            "volume": 1000.0,
            "average_volume": 300.0,
            "rsi": 25.0,
        }

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 120):
        rows = []
        base = 40000.0
        for index in range(limit):
            close = base + index * 10
            rows.append([index, close - 5, close + 5, close - 10, close, 1000 + index])
        return rows


class _FakeExecutor(CommandExecutor):
    def __init__(self):
        config = OpenClawConfig(
            discord=DiscordSettings(bot_token="token", authorized_users=["u1"]),
            kimi_k2=KimiK2Settings(api_key="key"),
        )
        super().__init__(config)
        self.executed = []

    async def execute(self, command, **kwargs):  # type: ignore[override]
        self.executed.append(command)
        return await super().execute(command, **kwargs)


@pytest.mark.asyncio
async def test_market_monitor_condition_trigger() -> None:
    bridge = DiscordBridge(
        DiscordSettings(bot_token="token", authorized_users=["u1"]),
        bot_adapter=InMemoryBotAdapter(),
    )
    await bridge.start()
    executor = _FakeExecutor()
    monitor = MarketMonitor(
        exchange_client=_FakeExchange(),
        command_executor=executor,
        discord_bridge=bridge,
        monitor_interval_seconds=9999,
    )
    condition = MarketCondition(
        user_id="u1",
        condition_type="price_threshold",
        symbol="BTCUSDT",
        parameters={"threshold": 41000.0, "direction": "above"},
        action="notify",
        action_params={"channel_id": "c1"},
    )
    await monitor.add_condition(condition)
    triggered = await monitor.evaluate_conditions()
    assert triggered
    analysis = await monitor.market_analysis("BTCUSDT")
    assert analysis["symbol"] == "BTCUSDT"
    await bridge.stop()
    await executor.close()
