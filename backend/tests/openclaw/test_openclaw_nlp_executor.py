from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncBaseTransport, Request, Response

from backend.app.openclaw.command_executor import CommandExecutor, MarketPyApiClient, PortfolioState
from backend.app.openclaw.config import (
    DiscordSettings,
    KimiK2Settings,
    OpenClawConfig,
    RiskLimitSettings,
)
from backend.app.openclaw.context_manager import ContextManager
from backend.app.openclaw.kimi_k2_client import KimiK2Client
from backend.app.openclaw.nlp import NaturalLanguageProcessor


class _IntentTransport(AsyncBaseTransport):
    async def handle_async_request(self, request: Request) -> Response:
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "command_type": "place_order",
                                "symbol": "BTCUSDT",
                                "action": "buy",
                                "quantity": 0.25,
                                "parameters": {},
                            }
                        )
                    }
                }
            ]
        }
        return Response(status_code=200, json=payload)


class _MarketApiTransport(AsyncBaseTransport):
    async def handle_async_request(self, request: Request) -> Response:
        if request.url.path.endswith("/api/paper-trading/order"):
            return Response(status_code=200, json={"order_id": "order-1"})
        if "/api/market/" in request.url.path:
            return Response(status_code=200, json={"price": 40000.0})
        if request.url.path.endswith("/api/portfolio"):
            return Response(status_code=200, json={"positions": []})
        if request.url.path.endswith("/api/backtest/run"):
            return Response(status_code=200, json={"job_id": "bt-1"})
        return Response(status_code=404, json={"error": "not-found"})


@pytest.mark.asyncio
async def test_nlp_and_executor_flow(tmp_path: Path) -> None:
    kimi = KimiK2Client(KimiK2Settings(api_key="k"), transport=_IntentTransport())
    context = ContextManager(data_dir=str(tmp_path))
    nlp = NaturalLanguageProcessor(kimi, context)
    command = await nlp.parse_command("Buy 0.25 BTC", "u1")
    assert command.command_type == "place_order"
    assert command.quantity == 0.25

    config = OpenClawConfig(
        discord=DiscordSettings(bot_token="t", authorized_users=["u1"]),
        kimi_k2=KimiK2Settings(api_key="k"),
        risk_limits=RiskLimitSettings(max_order_size=1.0),
    )
    api_client = MarketPyApiClient(base_url="http://test", transport=_MarketApiTransport())
    executor = CommandExecutor(config, api_client=api_client)
    result = await executor.execute(command, portfolio_state=PortfolioState())
    await executor.close()
    await kimi.close()
    assert result.success is True
    assert result.data == {"order_id": "order-1"}
