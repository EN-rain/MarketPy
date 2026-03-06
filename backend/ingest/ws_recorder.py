"""WebSocket recorder for Binance real-time market updates."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from backend.ingest.binance_client import BinanceClient

logger = logging.getLogger(__name__)


class WSRecorder:
    """Recorder that subscribes to Binance ticker streams and writes JSONL events."""

    def __init__(
        self,
        token_ids: list[str],
        output_dir: str = "data/raw",
        ws_url: str | None = None,
    ) -> None:
        del ws_url
        self.token_ids = token_ids
        self.output_dir = Path(output_dir)
        self._running = False
        self._event_count = 0
        self._client: BinanceClient | None = None

    def _get_output_path(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(UTC).strftime("%Y%m%d")
        return self.output_dir / f"market_events_{date_str}.jsonl"

    async def _write_event(self, event: dict, fh) -> None:
        event["_recorded_at"] = datetime.now(UTC).isoformat()
        fh.write(json.dumps(event) + "\n")
        self._event_count += 1
        if self._event_count % 100 == 0:
            fh.flush()
            logger.debug("Recorded %s events", self._event_count)

    async def run(self, duration_seconds: int | None = None) -> int:
        self._running = True
        self._event_count = 0
        output_path = self._get_output_path()
        symbols = [s.lower() for s in self.token_ids]

        logger.info(
            "Recording %s symbols to %s%s",
            len(symbols),
            output_path,
            f" for {duration_seconds}s" if duration_seconds else " (indefinitely)",
        )

        with open(output_path, "a", encoding="utf-8") as fh:
            self._client = BinanceClient()

            async def on_market_update(symbol: str, data: dict):
                if "market" not in data:
                    return
                market = data["market"]
                ts_ms = int(market.last_update.timestamp() * 1000)
                bba_event = {
                    "event_type": "best_bid_ask",
                    "asset_id": market.symbol.upper(),
                    "timestamp_ms": ts_ms,
                    "best_bid": market.bid,
                    "best_ask": market.ask,
                }
                trade_event = {
                    "event_type": "last_trade_price",
                    "asset_id": market.symbol.upper(),
                    "timestamp_ms": ts_ms,
                    "price": market.price,
                    "size": max(0.0, market.volume_24h),
                    "side": "unknown",
                }
                await self._write_event(bba_event, fh)
                await self._write_event(trade_event, fh)

            self._client.add_handler(on_market_update)
            run_task = asyncio.create_task(self._client.start(symbols))

            try:
                if duration_seconds:
                    await asyncio.sleep(duration_seconds)
                    self.stop()
                while self._running:
                    await asyncio.sleep(0.2)
            finally:
                self.stop()
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass

        logger.info("Recording complete: %s events saved to %s", self._event_count, output_path)
        return self._event_count

    def stop(self) -> None:
        self._running = False
        if self._client:
            self._client.stop()

