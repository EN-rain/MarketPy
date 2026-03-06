"""Live feed service that connects to exchange WebSocket and distributes updates.

This service:
1. Connects to exchange WebSocket
2. Parses incoming market data
3. Broadcasts to:
   - JSONL recorder (for data persistence)
   - Paper trading engine (for signal generation)
   - WebSocket clients (for UI updates)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import websockets

from backend.app.models.config import settings
from backend.app.models.market import OrderBookSnapshot
from backend.app.models.realtime import PreviousMarketState, RealtimeMarketUpdate
from backend.app.models.realtime_config import BatcherConfig, PrioritizerConfig
from backend.app.realtime.message_batcher import MessageBatcher
from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig
from backend.app.realtime.update_prioritizer import UpdatePrioritizer

logger = logging.getLogger(__name__)


@dataclass
class LiveFeedUpdate:
    """Normalized market update from live feed WebSocket parsing.
    
    This is an internal data structure used by LiveFeedService for parsing
    WebSocket events. For the canonical market update model, use
    backend.app.models.market.MarketUpdate.
    """

    market_id: str
    timestamp: datetime
    event_type: str  # book, price_change, last_trade_price, best_bid_ask
    data: dict[str, Any] = field(default_factory=dict)

    # Parsed orderbook data (if available)
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    spread: float | None = None
    last_trade: float | None = None

    @property
    def orderbook(self) -> OrderBookSnapshot | None:
        """Convert to OrderBookSnapshot if bid/ask are available."""
        if self.bid is not None and self.ask is not None:
            return OrderBookSnapshot(
                token_id=self.market_id,
                timestamp=self.timestamp,
                best_bid=self.bid,
                best_ask=self.ask,
                mid=self.mid or (self.bid + self.ask) / 2,
                spread=self.spread or (self.ask - self.bid),
            )
        return None


class LiveFeedService:
    """Live WebSocket feed service for real-time market data.
    
    Usage:
        service = LiveFeedService()
        service.add_handler(paper_engine.on_market_update)
        service.add_handler(ui_broadcast)
        await service.start(["token_id_1", "token_id_2"])
    """

    def __init__(
        self,
        ws_url: str | None = None,
        output_dir: str = "data/live",
        worker_pool_size: int = 10,
        update_prioritizer: UpdatePrioritizer | None = None,
        message_batcher: MessageBatcher | None = None,
        task_manager: BoundedTaskManager | None = None,
    ) -> None:
        self.ws_url = ws_url or settings.binance_ws_url
        self.output_dir = Path(output_dir)
        self._handlers: list[Callable[[LiveFeedUpdate], None]] = []
        self._running = False
        self._ws = None
        self._token_ids: list[str] = []
        self._event_count = 0
        self._last_prices: dict[str, dict] = {}
        self._worker_pool_size = max(1, worker_pool_size)
        self._market_locks: dict[str, asyncio.Lock] = {}
        self._previous_state: dict[str, PreviousMarketState] = {}
        self._prioritizer = update_prioritizer or UpdatePrioritizer(PrioritizerConfig())
        self._batcher = message_batcher or MessageBatcher(BatcherConfig())
        self._batcher.flush_callback = self._on_batch_flushed
        self._task_manager = task_manager or BoundedTaskManager(TaskManagerConfig())

    def add_handler(self, handler: Callable[[LiveFeedUpdate], None]) -> None:
        """Register a handler for market updates."""
        self._handlers.append(handler)
        logger.info(f"Added handler: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")

    def remove_handler(self, handler: Callable[[LiveFeedUpdate], None]) -> None:
        """Remove a handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def _build_subscribe_msg(self) -> str:
        """Build the initial subscription message."""
        return json.dumps({
            "type": "market",
            "assets_ids": self._token_ids,
            "custom_feature_enabled": True,
        })

    def _parse_event(self, event: dict) -> LiveFeedUpdate | None:
        """Parse a raw WebSocket event into a LiveFeedUpdate."""
        try:
            event_type = event.get("event_type", "unknown")
            timestamp = self._extract_event_timestamp(event)

            # Try to extract market_id from various locations
            market_id = event.get("asset_id") or event.get("market") or event.get("condition_id")
            if not market_id and "asset_ids" in event:
                market_id = event["asset_ids"][0] if event["asset_ids"] else None

            if not market_id:
                return None

            update = LiveFeedUpdate(
                market_id=market_id,
                timestamp=timestamp,
                event_type=event_type,
                data=event,
            )

            # Parse orderbook data based on event type
            if event_type == "book" and "book" in event:
                book = event["book"]
                if "bids" in book and "asks" in book:
                    bids = book["bids"]
                    asks = book["asks"]
                    if bids and asks:
                        update.bid = float(bids[0]["price"])
                        update.ask = float(asks[0]["price"])
                        update.mid = (update.bid + update.ask) / 2
                        update.spread = update.ask - update.bid

            elif event_type == "best_bid_ask":
                if "best_bid" in event and "best_ask" in event:
                    update.bid = float(event["best_bid"])
                    update.ask = float(event["best_ask"])
                    update.mid = (update.bid + update.ask) / 2
                    update.spread = update.ask - update.bid

            elif event_type == "last_trade_price":
                if "price" in event:
                    update.last_trade = float(event["price"])
                    # Use last trade as mid if no book data
                    update.mid = update.last_trade

            # Store last known prices for this market
            if update.bid and update.ask:
                self._last_prices[market_id] = {
                    "bid": update.bid,
                    "ask": update.ask,
                    "mid": update.mid,
                    "timestamp": timestamp,
                }
            elif market_id in self._last_prices:
                # Fill in missing data from cache
                cached = self._last_prices[market_id]
                update.bid = cached["bid"]
                update.ask = cached["ask"]
                update.mid = cached["mid"]

            return update

        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None

    def _extract_event_timestamp(self, event: dict) -> datetime:
        """Prefer exchange timestamps when present."""
        for key in ("timestamp_ms", "ts", "event_ts", "E"):
            value = event.get(key)
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value / 1000, UTC)
        for key in ("timestamp", "event_timestamp", "time"):
            value = event.get(key)
            if isinstance(value, str) and value:
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
                except ValueError:
                    continue
        return datetime.now(UTC)

    async def _broadcast(self, update: LiveFeedUpdate) -> None:
        """Broadcast update to all handlers."""
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(update)
                else:
                    handler(update)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    async def _route_update(self, update: LiveFeedUpdate) -> None:
        """Route updates: critical updates immediately, non-critical through batcher."""
        prev = self._previous_state.get(update.market_id)
        if self._prioritizer.is_critical(update, prev):
            # Critical updates get highest priority (0)
            await self._task_manager.submit_task(self._broadcast(update), priority=0)
        else:
            await self._batcher.add_update(
                RealtimeMarketUpdate(
                    market_id=update.market_id,
                    timestamp=update.timestamp,
                    event_type=update.event_type,
                    data=update.data,
                    bid=update.bid,
                    ask=update.ask,
                    mid=update.mid,
                    spread=update.spread,
                    last_trade=update.last_trade,
                )
            )
        self._previous_state[update.market_id] = PreviousMarketState(
            market_id=update.market_id,
            last_price=update.mid or update.last_trade or prev.last_price if prev else None,
            last_bid=update.bid or (prev.last_bid if prev else None),
            last_ask=update.ask or (prev.last_ask if prev else None),
            last_volume=(update.data or {}).get("volume", prev.last_volume if prev else None),
            last_update=update.timestamp,
            price_history=(
                ((prev.price_history if prev else []) + ([update.mid] if update.mid else []))[-200:]
            ),
        )

    async def _process_update(self, update: LiveFeedUpdate) -> None:
        """Ensure per-market ordering while allowing cross-market concurrency."""
        lock = self._market_locks.setdefault(update.market_id, asyncio.Lock())
        async with lock:
            await self._route_update(update)

    def _on_batch_flushed(self, batched_message) -> None:
        """Re-broadcast each message in the flushed batch for backward compatibility."""
        for u in batched_message.updates:
            legacy = LiveFeedUpdate(
                market_id=u.market_id,
                timestamp=u.timestamp,
                event_type=u.event_type,
                data=u.data,
                bid=u.bid,
                ask=u.ask,
                mid=u.mid,
                spread=u.spread,
                last_trade=u.last_trade,
            )
            # Batched messages get low priority (2)
            asyncio.create_task(
                self._task_manager.submit_task(self._broadcast(legacy), priority=2)
            )

    async def _record_event(self, event: dict) -> None:
        """Record event to JSONL file."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(UTC).strftime("%Y%m%d")
            output_path = self.output_dir / f"live_events_{date_str}.jsonl"

            event["_recorded_at"] = datetime.now(UTC).isoformat()
            with open(output_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")

        except Exception as e:
            logger.error(f"Recording error: {e}")

    async def start(self, token_ids: list[str]) -> None:
        """Start the live feed service."""
        self._token_ids = token_ids
        self._running = True
        self._event_count = 0

        logger.info(f"Starting live feed for {len(token_ids)} markets")

        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self._ws = ws
                    await ws.send(self._build_subscribe_msg())
                    logger.info("Connected to exchange WebSocket")

                    while self._running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                            event = json.loads(msg)

                            # Record raw event
                            await self._record_event(event)

                            # Parse and broadcast
                            update = self._parse_event(event)
                            if update:
                                # Regular market updates get normal priority (1)
                                await self._task_manager.submit_task(
                                    self._process_update(update),
                                    priority=1
                                )
                                self._event_count += 1

                                if self._event_count % 100 == 0:
                                    logger.debug(f"Processed {self._event_count} events")

                        except TimeoutError:
                            await ws.send(json.dumps({"type": "ping"}))
                        except websockets.ConnectionClosed:
                            logger.warning("WebSocket closed, reconnecting...")
                            break

            except Exception as e:
                logger.error(f"Live feed error: {e}")
                await asyncio.sleep(5)  # Reconnect delay

    def stop(self) -> None:
        """Stop the live feed service."""
        self._running = False
        logger.info("Live feed stopped")

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the live feed service and task manager.
        
        Args:
            timeout: Maximum time to wait for tasks to complete (seconds)
        """
        self.stop()
        await self._task_manager.shutdown(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def event_count(self) -> int:
        return self._event_count

    def get_task_metrics(self):
        """Get current task manager metrics.
        
        Returns:
            TaskMetrics with current task count, queue depth, rejected count, etc.
        """
        return self._task_manager.get_metrics()
