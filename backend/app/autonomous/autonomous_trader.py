"""Autonomous AI Trader - Fully automated trading with ML models.

This module provides a fully autonomous trading system that:
1. Continuously monitors live market data
2. Makes trading decisions using ML models
3. Executes trades automatically based on signals
4. Manages risk and position sizing
5. Tracks performance and adapts to market conditions
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.integrations.discord_notifier import DiscordNotifier, NotificationCategory
from backend.app.models.config import settings
from backend.paper_trading.engine import PaperTradingEngine, RiskLimits
from backend.paper_trading.live_feed import LiveFeedUpdate
from backend.strategies.ai_strategy import AIStrategy

logger = logging.getLogger(__name__)


@dataclass
class AutonomousConfig:
    """Configuration for autonomous trading."""
    
    # Trading parameters
    initial_cash: float = 10000.0
    markets: list[str] = None  # Markets to trade (e.g., ["BTCUSDT", "ETHUSDT"])
    
    # AI Strategy parameters
    edge_buffer: float = 0.001  # Minimum edge required to trade (0.1%)
    kelly_fraction: float = 0.25  # Kelly criterion fraction (0.25 = quarter Kelly)
    order_size: float = 0.1  # Order size as fraction of portfolio
    
    # Risk limits
    max_position_per_market: float = 5000.0  # Max position size per market
    max_total_exposure: float = 8000.0  # Max total exposure across all markets
    max_daily_loss: float = 500.0  # Max daily loss before stopping
    
    # Model settings
    model_path: str | None = None  # Path to trained model (auto-detect if None)
    model_update_interval: int = 3600  # Seconds between model reloads
    
    # Execution settings
    fill_model: str = "M2"  # Fill model: M1 (optimistic), M2 (realistic), M3 (pessimistic)
    fee_rate: float = 0.0002  # Trading fee rate (0.02%)
    
    # Monitoring
    enable_discord_notifications: bool = True
    performance_report_interval: int = 3600  # Seconds between performance reports
    
    def __post_init__(self):
        if self.markets is None:
            self.markets = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


class AutonomousTrader:
    """Fully autonomous AI trading system.
    
    This class orchestrates:
    - Live market data ingestion
    - ML model inference
    - Automated trade execution
    - Risk management
    - Performance monitoring
    
    Example:
        ```python
        # Create autonomous trader
        config = AutonomousConfig(
            initial_cash=10000.0,
            markets=["BTCUSDT", "ETHUSDT"],
            edge_buffer=0.001,
            kelly_fraction=0.25
        )
        
        trader = AutonomousTrader(config)
        
        # Start autonomous trading
        await trader.start()
        
        # Monitor performance
        stats = trader.get_stats()
        print(f"Total PnL: ${stats['total_pnl']:.2f}")
        
        # Stop trading
        await trader.stop()
        ```
    """
    
    def __init__(
        self,
        config: AutonomousConfig | None = None,
        discord_notifier: DiscordNotifier | None = None,
    ):
        """Initialize autonomous trader.
        
        Args:
            config: Trading configuration
            discord_notifier: Optional Discord notifier for alerts
        """
        self.config = config or AutonomousConfig()
        self.discord_notifier = discord_notifier
        
        # Initialize paper trading engine
        risk_limits = RiskLimits(
            max_position_per_market=self.config.max_position_per_market,
            max_total_exposure=self.config.max_total_exposure,
            max_daily_loss=self.config.max_daily_loss,
        )
        
        self.engine = PaperTradingEngine(
            initial_cash=self.config.initial_cash,
            fill_model=self.config.fill_model,
            fee_rate=self.config.fee_rate,
            risk_limits=risk_limits,
            discord_notifier=discord_notifier,
        )
        
        # Initialize AI strategy
        self.strategy = AIStrategy(
            edge_buffer=self.config.edge_buffer,
            kelly_fraction=self.config.kelly_fraction,
            order_size=self.config.order_size,
        )
        
        # Load ML model
        self._load_model()
        
        # Add strategy to engine
        self.engine.add_strategy(self.strategy)
        
        # Register markets
        for market_id in self.config.markets:
            self.engine.register_market(
                market_id,
                {"question": market_id.replace("USDT", "")}
            )
        
        # State tracking
        self._running = False
        self._start_time: datetime | None = None
        self._last_performance_report: datetime | None = None
        self._last_model_reload: datetime | None = None
        self._total_signals = 0
        self._total_trades = 0
        
        logger.info(
            f"Autonomous trader initialized: {len(self.config.markets)} markets, "
            f"${self.config.initial_cash:.2f} initial capital"
        )
    
    def _load_model(self) -> None:
        """Load ML model for predictions."""
        if self.config.model_path:
            model_path = Path(self.config.model_path)
        else:
            # Auto-detect latest model
            model_dir = Path(settings.model_dir)
            if model_dir.exists():
                models = sorted(model_dir.glob("*.joblib"))
                if models:
                    model_path = models[-1]
                else:
                    logger.warning("No trained models found. Using default strategy.")
                    return
            else:
                logger.warning("Model directory not found. Using default strategy.")
                return
        
        try:
            # Load model into strategy
            if hasattr(self.strategy, "load_model"):
                self.strategy.load_model(str(model_path))
                logger.info(f"Loaded ML model: {model_path}")
                self._last_model_reload = datetime.now(UTC)
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
    
    async def start(self) -> None:
        """Start autonomous trading.
        
        This begins:
        1. Market data monitoring
        2. Signal generation
        3. Automated trade execution
        4. Performance tracking
        """
        if self._running:
            logger.warning("Autonomous trader already running")
            return
        
        self._running = True
        self._start_time = datetime.now(UTC)
        self.engine.start()
        
        logger.info("🤖 Autonomous trading started")
        
        if self.discord_notifier and self.config.enable_discord_notifications:
            await self.discord_notifier.send(
                category=NotificationCategory.INFO,
                component="autonomous_trader",
                message="Autonomous trading started",
                metrics={
                    "markets": len(self.config.markets),
                    "initial_cash": self.config.initial_cash,
                    "edge_buffer": self.config.edge_buffer,
                    "kelly_fraction": self.config.kelly_fraction,
                },
            )
        
        # Start background tasks
        asyncio.create_task(self._performance_monitor())
        asyncio.create_task(self._model_reloader())
    
    async def stop(self) -> None:
        """Stop autonomous trading."""
        if not self._running:
            logger.warning("Autonomous trader not running")
            return
        
        self._running = False
        self.engine.stop()
        
        # Generate final report
        stats = self.get_stats()
        
        logger.info(
            f"🛑 Autonomous trading stopped. "
            f"Total PnL: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:.2f}%)"
        )
        
        if self.discord_notifier and self.config.enable_discord_notifications:
            await self.discord_notifier.send(
                category=NotificationCategory.INFO,
                component="autonomous_trader",
                message="Autonomous trading stopped",
                metrics={
                    "total_pnl": round(stats["total_pnl"], 2),
                    "total_pnl_pct": round(stats["total_pnl_pct"], 2),
                    "total_trades": stats["total_trades"],
                    "win_rate": round(stats["win_rate"], 2),
                    "runtime_hours": round(stats["runtime_hours"], 2),
                },
            )
    
    async def on_market_update(self, update: LiveFeedUpdate) -> None:
        """Handle market update and execute autonomous trading logic.
        
        Args:
            update: Live market data update
        """
        if not self._running:
            return
        
        # Pass update to paper trading engine
        # Engine will automatically:
        # 1. Update market state
        # 2. Run AI strategy
        # 3. Generate signals
        # 4. Execute trades if conditions met
        await self.engine.on_market_update(update)
    
    async def _performance_monitor(self) -> None:
        """Background task to monitor and report performance."""
        while self._running:
            await asyncio.sleep(self.config.performance_report_interval)
            
            if not self._running:
                break
            
            stats = self.get_stats()
            
            logger.info(
                f"📊 Performance Update: "
                f"PnL: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:.2f}%), "
                f"Trades: {stats['total_trades']}, "
                f"Win Rate: {stats['win_rate']:.1f}%"
            )
            
            # Send Discord notification for significant changes
            if self.discord_notifier and self.config.enable_discord_notifications:
                if abs(stats["total_pnl_pct"]) >= 5.0:  # 5% change
                    await self.discord_notifier.send(
                        category=NotificationCategory.INFO,
                        component="autonomous_trader",
                        message="Performance milestone reached",
                        metrics={
                            "total_pnl": round(stats["total_pnl"], 2),
                            "total_pnl_pct": round(stats["total_pnl_pct"], 2),
                            "total_trades": stats["total_trades"],
                            "win_rate": round(stats["win_rate"], 2),
                        },
                    )
            
            self._last_performance_report = datetime.now(UTC)
    
    async def _model_reloader(self) -> None:
        """Background task to reload ML model periodically."""
        while self._running:
            await asyncio.sleep(self.config.model_update_interval)
            
            if not self._running:
                break
            
            logger.info("Reloading ML model...")
            self._load_model()
    
    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive trading statistics.
        
        Returns:
            Dictionary with performance metrics:
            - total_pnl: Total profit/loss in dollars
            - total_pnl_pct: Total return percentage
            - total_trades: Number of trades executed
            - win_rate: Percentage of profitable trades
            - sharpe_ratio: Risk-adjusted return
            - max_drawdown: Maximum drawdown percentage
            - runtime_hours: Hours since start
            - current_positions: Number of open positions
            - total_equity: Current portfolio value
        """
        portfolio = self.engine.portfolio
        engine_stats = self.engine.stats
        
        # Calculate win rate
        winning_trades = sum(1 for trade in portfolio.trades if trade.pnl > 0)
        total_trades = len(portfolio.trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # Calculate runtime
        runtime_hours = 0.0
        if self._start_time:
            runtime_seconds = (datetime.now(UTC) - self._start_time).total_seconds()
            runtime_hours = runtime_seconds / 3600
        
        return {
            # Performance
            "total_pnl": portfolio.total_pnl,
            "total_pnl_pct": portfolio.total_pnl_pct,
            "realized_pnl": portfolio.realized_pnl,
            "unrealized_pnl": sum(pos.unrealized_pnl for pos in portfolio.positions.values()),
            
            # Trading activity
            "total_trades": total_trades,
            "total_signals": engine_stats["signal_count"],
            "win_rate": win_rate,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            
            # Risk metrics
            "max_drawdown": portfolio.max_drawdown,
            "sharpe_ratio": portfolio.sharpe_ratio,
            "risk_violations": engine_stats["risk_violation_count"],
            
            # Portfolio state
            "total_equity": portfolio.total_equity,
            "cash": portfolio.cash,
            "positions_value": portfolio.positions_value,
            "current_positions": len(portfolio.positions),
            
            # System state
            "is_running": self._running,
            "runtime_hours": runtime_hours,
            "markets_tracked": len(self.config.markets),
            "last_performance_report": self._last_performance_report.isoformat() if self._last_performance_report else None,
            "last_model_reload": self._last_model_reload.isoformat() if self._last_model_reload else None,
        }
    
    def get_portfolio(self) -> dict[str, Any]:
        """Get current portfolio state.
        
        Returns:
            Dictionary with portfolio details including positions and trades
        """
        portfolio = self.engine.portfolio
        
        return {
            "cash": portfolio.cash,
            "total_equity": portfolio.total_equity,
            "positions_value": portfolio.positions_value,
            "positions": {
                market_id: {
                    "size": pos.size,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                }
                for market_id, pos in portfolio.positions.items()
            },
            "recent_trades": [
                {
                    "market_id": trade.market_id,
                    "action": trade.action.value,
                    "size": trade.size,
                    "price": trade.price,
                    "pnl": trade.pnl,
                    "timestamp": trade.timestamp.isoformat(),
                    "strategy": trade.strategy,
                }
                for trade in portfolio.trades[-10:]  # Last 10 trades
            ],
        }
    
    @property
    def is_running(self) -> bool:
        """Check if autonomous trading is active."""
        return self._running
