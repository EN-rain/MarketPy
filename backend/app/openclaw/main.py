"""OpenClaw service entrypoint with health and metrics endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from backend.ingest.exchange_client import ExchangeClient, ExchangeConfig, ExchangeType

from .autonomous_agent import AutonomousAgent
from .config import OpenClawConfigManager
from .discord_bridge import DiscordMessage


def _build_exchange_client() -> ExchangeClient | None:
    try:
        config = ExchangeConfig.from_env(exchange_type=ExchangeType.BINANCE)
        return ExchangeClient(config)
    except Exception:
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_manager = OpenClawConfigManager()
    exchange_client = _build_exchange_client()
    agent = AutonomousAgent(config_manager=config_manager, exchange_client=exchange_client)
    app.state.openclaw_agent = agent
    await agent.start()
    yield
    await agent.stop()
    if exchange_client is not None:
        await exchange_client.close()


app = FastAPI(
    title="OpenClaw Integration Service",
    description="Natural-language autonomous assistant for MarketPy",
    version="1.0.0",
    lifespan=lifespan,
)


class CommandRequest(BaseModel):
    user_id: str
    channel_id: str
    content: str


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    agent: AutonomousAgent | None = getattr(request.app.state, "openclaw_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="OpenClaw agent not initialized")
    payload = agent.health_check()
    payload["timestamp"] = datetime.now(UTC).isoformat()
    return payload


@app.get("/metrics")
async def metrics(request: Request) -> Response:
    agent: AutonomousAgent | None = getattr(request.app.state, "openclaw_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="OpenClaw agent not initialized")
    return Response(content=agent.metrics_text(), media_type="text/plain; version=0.0.4")


@app.post("/command")
async def command(request: Request, payload: CommandRequest) -> dict[str, str]:
    agent: AutonomousAgent | None = getattr(request.app.state, "openclaw_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="OpenClaw agent not initialized")
    await agent.enqueue_message(
        DiscordMessage(
            user_id=payload.user_id,
            channel_id=payload.channel_id,
            content=payload.content,
        )
    )
    return {"status": "queued"}


def run() -> None:
    uvicorn.run("backend.app.openclaw.main:app", host="0.0.0.0", port=8100, reload=False)


if __name__ == "__main__":
    run()
