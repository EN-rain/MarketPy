"""API endpoints for autonomous AI trading."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.autonomous.autonomous_trader import AutonomousConfig, AutonomousTrader
from backend.app.models.config import settings

router = APIRouter()

# Global autonomous trader instance
_autonomous_trader: AutonomousTrader | None = None


class StartAutonomousRequest(BaseModel):
    """Request to start autonomous trading."""
    
    initial_cash: float = Field(default=10000.0, gt=0, description="Initial capital")
    markets: list[str] = Field(default=["BTCUSDT", "ETHUSDT"], description="Markets to trade")
    edge_buffer: float = Field(default=0.001, ge=0, le=0.1, description="Minimum edge required")
    kelly_fraction: float = Field(default=0.25, gt=0, le=1.0, description="Kelly criterion fraction")
    order_size: float = Field(default=0.1, gt=0, le=1.0, description="Order size fraction")
    max_position_per_market: float = Field(default=5000.0, gt=0, description="Max position per market")
    max_total_exposure: float = Field(default=8000.0, gt=0, description="Max total exposure")
    max_daily_loss: float = Field(default=500.0, gt=0, description="Max daily loss")


class AutonomousStatusResponse(BaseModel):
    """Autonomous trading status."""
    
    is_running: bool
    stats: dict[str, Any] | None = None
    portfolio: dict[str, Any] | None = None


@router.post("/autonomous/start")
async def start_autonomous_trading(
    request: Request,
    config: StartAutonomousRequest,
) -> dict[str, str]:
    """Start autonomous AI trading.
    
    This endpoint initializes and starts a fully autonomous trading system that:
    - Monitors live market data continuously
    - Makes trading decisions using ML models
    - Executes trades automatically
    - Manages risk and position sizing
    - Tracks performance in real-time
    
    Example:
        ```bash
        curl -X POST http://localhost:8000/api/autonomous/start \\
          -H "Content-Type: application/json" \\
          -d '{
            "initial_cash": 10000,
            "markets": ["BTCUSDT", "ETHUSDT"],
            "edge_buffer": 0.001,
            "kelly_fraction": 0.25
          }'
        ```
    """
    global _autonomous_trader
    
    if _autonomous_trader and _autonomous_trader.is_running:
        raise HTTPException(status_code=400, detail="Autonomous trading already running")
    
    # Create configuration
    autonomous_config = AutonomousConfig(
        initial_cash=config.initial_cash,
        markets=config.markets,
        edge_buffer=config.edge_buffer,
        kelly_fraction=config.kelly_fraction,
        order_size=config.order_size,
        max_position_per_market=config.max_position_per_market,
        max_total_exposure=config.max_total_exposure,
        max_daily_loss=config.max_daily_loss,
    )
    
    # Get Discord notifier from app state
    discord_notifier = getattr(request.app.state, "discord_notifier", None)
    
    # Create and start autonomous trader
    _autonomous_trader = AutonomousTrader(
        config=autonomous_config,
        discord_notifier=discord_notifier,
    )
    
    await _autonomous_trader.start()
    
    # Connect to live market feed
    binance_client = getattr(request.app.state, "binance_client", None)
    if binance_client:
        # Add handler to receive market updates
        async def handle_market_update(symbol: str, data: dict):
            if "market" not in data:
                return
            market = data["market"]
            
            from backend.paper_trading.live_feed import LiveFeedUpdate
            
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
            
            await _autonomous_trader.on_market_update(update)
        
        binance_client.add_handler(handle_market_update)
    
    return {
        "status": "started",
        "message": f"Autonomous trading started with {len(config.markets)} markets",
        "markets": config.markets,
    }


@router.post("/autonomous/stop")
async def stop_autonomous_trading() -> dict[str, Any]:
    """Stop autonomous AI trading.
    
    This stops the autonomous trading system and returns final statistics.
    
    Example:
        ```bash
        curl -X POST http://localhost:8000/api/autonomous/stop
        ```
    """
    global _autonomous_trader
    
    if not _autonomous_trader or not _autonomous_trader.is_running:
        raise HTTPException(status_code=400, detail="Autonomous trading not running")
    
    # Get final stats before stopping
    final_stats = _autonomous_trader.get_stats()
    
    await _autonomous_trader.stop()
    
    return {
        "status": "stopped",
        "message": "Autonomous trading stopped",
        "final_stats": final_stats,
    }


@router.get("/autonomous/status")
async def get_autonomous_status() -> AutonomousStatusResponse:
    """Get autonomous trading status and statistics.
    
    Returns current state, performance metrics, and portfolio details.
    
    Example:
        ```bash
        curl http://localhost:8000/api/autonomous/status
        ```
    """
    global _autonomous_trader
    
    if not _autonomous_trader:
        return AutonomousStatusResponse(is_running=False)
    
    return AutonomousStatusResponse(
        is_running=_autonomous_trader.is_running,
        stats=_autonomous_trader.get_stats() if _autonomous_trader.is_running else None,
        portfolio=_autonomous_trader.get_portfolio() if _autonomous_trader.is_running else None,
    )


@router.get("/autonomous/stats")
async def get_autonomous_stats() -> dict[str, Any]:
    """Get detailed autonomous trading statistics.
    
    Returns comprehensive performance metrics including:
    - Total PnL and return percentage
    - Number of trades and win rate
    - Risk metrics (Sharpe ratio, max drawdown)
    - Current portfolio state
    - System runtime and status
    
    Example:
        ```bash
        curl http://localhost:8000/api/autonomous/stats
        ```
    """
    global _autonomous_trader
    
    if not _autonomous_trader or not _autonomous_trader.is_running:
        raise HTTPException(status_code=400, detail="Autonomous trading not running")
    
    return _autonomous_trader.get_stats()


@router.get("/autonomous/portfolio")
async def get_autonomous_portfolio() -> dict[str, Any]:
    """Get current autonomous trading portfolio.
    
    Returns detailed portfolio information including:
    - Cash and total equity
    - Open positions with unrealized PnL
    - Recent trade history
    
    Example:
        ```bash
        curl http://localhost:8000/api/autonomous/portfolio
        ```
    """
    global _autonomous_trader
    
    if not _autonomous_trader or not _autonomous_trader.is_running:
        raise HTTPException(status_code=400, detail="Autonomous trading not running")
    
    return _autonomous_trader.get_portfolio()
