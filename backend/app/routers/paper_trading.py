"""Paper trading endpoints for live simulation."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.app.integrations.discord_notifier import DiscordNotifier, DiscordNotifierConfig
from backend.app.models.config import SimMode, settings
from backend.paper_trading.live_feed import LiveFeedUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

_paper_engine: Any | None = None
_binance_handler: Any | None = None
_fallback_task: asyncio.Task | None = None
_last_ws_tick_by_symbol: dict[str, datetime] = {}


def get_binance_client(request: Request):
    """Get Binance client from app state or create a fallback instance."""
    # Prefer shared app-level singleton from app state
    if hasattr(request.app.state, 'binance_client') and request.app.state.binance_client is not None:
        return request.app.state.binance_client

    # Fallback to router-level factory (pass None since we don't have app state)
    from backend.app.routers.market import get_binance_client as get_router_binance_client
    return get_router_binance_client(None)


class StartPaperTradingRequest(BaseModel):
    market_ids: list[str] = Field(min_length=1, description="Token IDs to trade")
    strategy: str = "momentum"
    initial_cash: float = 10000.0
    fill_model: str = "M2"
    fee_rate: float = 0.02


class PaperTradingStatus(BaseModel):
    is_running: bool
    mode: str
    markets_count: int
    signal_count: int
    trade_count: int
    total_equity: float
    total_pnl: float
    total_pnl_pct: float


@router.post("/paper/start")
async def start_paper_trading(request: Request, params: StartPaperTradingRequest):
    global _paper_engine, _binance_handler, _fallback_task, _last_ws_tick_by_symbol

    app_state = request.app.state.app_state
    if app_state.mode == SimMode.PAPER and _paper_engine and _paper_engine.is_running:
        raise HTTPException(status_code=400, detail="Paper trading already running")

    from backend.paper_trading.engine import PaperTradingEngine
    from backend.strategies.ai_strategy import AIStrategy
    from backend.strategies.mean_reversion import MeanReversionStrategy
    from backend.strategies.momentum import MomentumStrategy

    notifier = getattr(request.app.state, "discord_notifier", None)
    if notifier is None:
        notifier = DiscordNotifier(DiscordNotifierConfig.from_env())

    _paper_engine = PaperTradingEngine(
        initial_cash=params.initial_cash,
        fill_model=params.fill_model,
        fee_rate=params.fee_rate,
        discord_notifier=notifier,
    )

    if params.strategy == "momentum":
        # Tuned for live ticker cadence: faster signal generation.
        strategy = MomentumStrategy(lookback=3, threshold=0.00005, order_size=0.1)
    elif params.strategy == "mean_reversion":
        strategy = MeanReversionStrategy(lookback=10, z_entry=1.2, z_exit=0.4, order_size=0.1)
    elif params.strategy in {"ai_predictor", "ai"}:
        strategy = AIStrategy(edge_buffer=0.0, kelly_fraction=0.05, order_size=0.1)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy '{params.strategy}'")
    _paper_engine.add_strategy(strategy)

    ws_manager = request.app.state.ws_manager

    async def broadcast_to_ui(event_type: str, data: dict):
        await ws_manager.broadcast(
            {
                "type": f"paper_{event_type}",
                "data": data,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    _paper_engine.add_ui_handler(broadcast_to_ui)
    selected_symbols = [m.upper().strip() for m in params.market_ids if m and m.strip()]
    for symbol in selected_symbols:
        _paper_engine.register_market(symbol, {"question": symbol.replace("USDT", "")})
    _paper_engine.start()
    await _paper_engine._notify_ui(
        "signal",
        {
            "market_id": selected_symbols[0] if selected_symbols else "SYSTEM",
            "decision": "HOLD",
            "confidence": 0.0,
            "edge": 0.0,
            "edge_pct": 0.0,
            "current_mid": None,
            "predicted_price": None,
            "reason": "Paper engine started. Waiting for first market ticks.",
            "strategy": getattr(strategy, "name", strategy.__class__.__name__),
        },
    )

    binance_client = get_binance_client(request)
    if binance_client is None:
        raise HTTPException(status_code=500, detail="Binance client unavailable")

    # Ensure stream is running for selected symbols.
    if not binance_client.is_running:
        logger.info("Starting Binance stream from paper trading endpoint")
        asyncio.create_task(binance_client.start(selected_symbols))
        # Give stream a short warm-up window.
        await asyncio.sleep(0.5)

    selected_set = set(selected_symbols)
    _last_ws_tick_by_symbol = {}

    async def binance_handler(symbol: str, data: dict):
        if "market" not in data:
            return
        market = data["market"]
        if selected_set and market.symbol.upper() not in selected_set:
            return
        _last_ws_tick_by_symbol[market.symbol.upper()] = datetime.now(UTC)
        update = LiveFeedUpdate(
            market_id=market.symbol.upper(),
            timestamp=market.last_update,
            event_type="price_change",
            data={"price": market.price, "change_24h": market.change_24h},
            bid=market.bid,
            ask=market.ask,
            mid=market.price,
            spread=market.spread,
            last_trade=market.price,
        )
        await _paper_engine.on_market_update(update)

    binance_client.add_handler(binance_handler)
    _binance_handler = binance_handler

    async def fallback_rest_ticks(symbols: list[str]) -> None:
        """Fallback updater when websocket ticks are stale or unavailable."""
        from backend.ingest.binance_client import BinanceRestClient

        rest = BinanceRestClient()
        try:
            while _paper_engine and _paper_engine.is_running:
                now = datetime.now(UTC)
                for symbol in symbols:
                    last_tick = _last_ws_tick_by_symbol.get(symbol)
                    if last_tick and (now - last_tick).total_seconds() < 4:
                        continue
                    quote = await rest.get_book_ticker(symbol)
                    if not quote:
                        continue
                    update = LiveFeedUpdate(
                        market_id=symbol,
                        timestamp=now,
                        event_type="fallback_price",
                        data={"source": "rest_fallback"},
                        bid=quote["bid"],
                        ask=quote["ask"],
                        mid=quote["mid"],
                        spread=max(0.0, quote["ask"] - quote["bid"]),
                        last_trade=quote["mid"],
                    )
                    await _paper_engine.on_market_update(update)
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        finally:
            await rest.close()

    if _fallback_task and not _fallback_task.done():
        _fallback_task.cancel()
    _fallback_task = asyncio.create_task(fallback_rest_ticks(selected_symbols))

    app_state.mode = SimMode.PAPER
    app_state.is_running = True
    app_state.connected_markets = params.market_ids

    return {
        "status": "started",
        "mode": "paper",
        "markets": params.market_ids,
        "strategy": params.strategy,
    }


@router.post("/paper/stop")
async def stop_paper_trading(request: Request):
    global _paper_engine, _binance_handler, _fallback_task

    binance_client = get_binance_client(request)
    if binance_client and _binance_handler:
        binance_client.remove_handler(_binance_handler)
        _binance_handler = None
    if _paper_engine:
        _paper_engine.stop()
    if _fallback_task and not _fallback_task.done():
        _fallback_task.cancel()
    _fallback_task = None

    app_state = request.app.state.app_state
    app_state.mode = SimMode.BACKTEST
    app_state.is_running = False
    app_state.connected_markets = []

    return {"status": "stopped", "mode": "backtest"}


@router.post("/paper/reset")
async def reset_paper_trading():
    global _paper_engine
    if _paper_engine:
        _paper_engine.reset()
        return {"status": "reset"}
    raise HTTPException(status_code=400, detail="Paper trading not initialized")


@router.get("/paper/status")
async def get_paper_status(request: Request) -> PaperTradingStatus:
    global _paper_engine
    app_state = request.app.state.app_state

    if _paper_engine:
        stats = _paper_engine.stats
        markets_count = (
            len(app_state.connected_markets)
            if app_state.connected_markets
            else stats["market_count"]
        )
        return PaperTradingStatus(
            is_running=stats["is_running"],
            mode=app_state.mode.value,
            markets_count=markets_count,
            signal_count=stats["signal_count"],
            trade_count=stats["trade_count"],
            total_equity=stats["total_equity"],
            total_pnl=stats["total_pnl"],
            total_pnl_pct=(
                (stats["total_pnl"] / _paper_engine.initial_cash * 100) if _paper_engine else 0
            ),
        )

    return PaperTradingStatus(
        is_running=False,
        mode=app_state.mode.value,
        markets_count=len(app_state.connected_markets) if app_state.connected_markets else 0,
        signal_count=0,
        trade_count=0,
        total_equity=10000.0,
        total_pnl=0.0,
        total_pnl_pct=0.0,
    )


@router.get("/paper-trading/risk-status")
async def get_paper_risk_status():
    global _paper_engine
    if not _paper_engine:
        return {
            "limits": {
                "max_position_per_market": settings.max_position_per_market,
                "max_total_exposure": settings.max_total_exposure,
                "max_daily_loss": settings.max_daily_loss,
            },
            "metrics": {
                "current_exposure": 0.0,
                "daily_pnl": 0.0,
                "position_sizes": {},
            },
            "status": {
                "position_limit_ok": True,
                "exposure_limit_ok": True,
                "daily_loss_limit_ok": True,
            },
            "risk_violation_count": 0,
        }
    return _paper_engine.get_risk_status()


@router.get("/paper/portfolio")
async def get_paper_portfolio():
    global _paper_engine

    default_portfolio = {
        "cash": 10000.0,
        "initial_cash": 10000.0,
        "total_equity": 10000.0,
        "total_pnl": 0.0,
        "total_pnl_pct": 0.0,
        "total_fees_paid": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "max_drawdown": 0.0,
        "win_rate": 0.0,
        "positions_count": 0,
        "trades_count": 0,
        "positions": {},
        "trades": [],
    }

    if not _paper_engine:
        return default_portfolio

    try:
        portfolio = _paper_engine.portfolio
        return {
            "cash": portfolio.cash,
            "initial_cash": _paper_engine.initial_cash,
            "total_equity": portfolio.total_equity,
            "total_pnl": portfolio.total_pnl,
            "total_pnl_pct": portfolio.total_pnl_pct,
            "total_fees_paid": portfolio.total_fees_paid,
            "realized_pnl": portfolio.realized_pnl,
            "unrealized_pnl": sum(pos.unrealized_pnl for pos in portfolio.positions.values()),
            "max_drawdown": portfolio.max_drawdown,
            "win_rate": portfolio.win_rate,
            "positions_count": len(portfolio.positions),
            "trades_count": len(portfolio.trades),
            "positions": {
                mid: {
                    "side": pos.side,
                    "size": pos.size,
                    "avg_entry_price": pos.avg_entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                    "market_value": pos.market_value,
                }
                for mid, pos in portfolio.positions.items()
            },
            "trades": [
                {
                    "id": t.id,
                    "timestamp": t.timestamp.isoformat(),
                    "market_id": t.market_id,
                    "action": t.action.value,
                    "price": t.price,
                    "size": t.size,
                    "fee": t.fee,
                    "pnl": t.pnl,
                    "strategy": t.strategy,
                }
                for t in portfolio.trades[-50:]
            ],
        }
    except Exception:
        return default_portfolio


@router.websocket("/ws/paper")
async def websocket_paper(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = {"type": "pong"} if data == "ping" else {"type": "ack"}
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
