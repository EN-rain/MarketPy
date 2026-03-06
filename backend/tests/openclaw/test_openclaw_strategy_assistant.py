from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncBaseTransport, Request, Response

from backend.app.openclaw.command_executor import CommandExecutor, MarketPyApiClient
from backend.app.openclaw.config import DiscordSettings, KimiK2Settings, OpenClawConfig
from backend.app.openclaw.kimi_k2_client import KimiK2Client
from backend.app.openclaw.strategy_assistant import StrategyAssistant


class _KimiTransport(AsyncBaseTransport):
    async def handle_async_request(self, request: Request) -> Response:
        return Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```python\n"
                                "class DemoStrategy:\n"
                                "    def populate_indicators(self, dataframe, metadata):\n"
                                "        return dataframe\n"
                                "    def populate_entry_trend(self, dataframe, metadata):\n"
                                "        return dataframe\n"
                                "    def populate_exit_trend(self, dataframe, metadata):\n"
                                "        return dataframe\n"
                                "```"
                            )
                        }
                    }
                ]
            },
        )


class _BacktestTransport(AsyncBaseTransport):
    async def handle_async_request(self, request: Request) -> Response:
        if request.url.path.endswith("/api/backtest/run"):
            return Response(
                status_code=200,
                json={"total_return": 0.12, "sharpe_ratio": 1.4, "max_drawdown": 0.08},
            )
        return Response(status_code=404, json={"error": "unknown"})


@pytest.mark.asyncio
async def test_strategy_creation_generation_and_backtest(tmp_path: Path) -> None:
    kimi = KimiK2Client(KimiK2Settings(api_key="k"), transport=_KimiTransport())
    config = OpenClawConfig(
        discord=DiscordSettings(bot_token="t", authorized_users=["u1"]),
        kimi_k2=KimiK2Settings(api_key="k"),
    )
    api_client = MarketPyApiClient(base_url="http://test", transport=_BacktestTransport())
    executor = CommandExecutor(config, api_client=api_client)
    assistant = StrategyAssistant(
        kimi_client=kimi,
        command_executor=executor,
        strategies_dir=str(tmp_path),
    )

    spec = await assistant.create_strategy("u1", "Momentum breakout strategy")
    code = await assistant.generate_code(spec)
    assert "class DemoStrategy" in code

    result = await assistant.run_backtest(spec.name, "2025-01-01", "2025-06-01", ["BTCUSDT"])
    summary = assistant.analyze_results(result)
    assert "Backtest summary" in summary
    assert assistant.list_strategies()
    await executor.close()
    await kimi.close()
