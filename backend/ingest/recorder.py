"""Recorder orchestrator for crypto market data."""

from __future__ import annotations

import argparse
import asyncio
import logging

from backend.ingest.ws_recorder import WSRecorder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["btcusdt", "ethusdt", "solusdt", "adausdt", "dotusdt"]


async def run_recorder(
    max_markets: int = 5,
    duration_seconds: int | None = None,
) -> None:
    symbols = DEFAULT_SYMBOLS[:max_markets]
    logger.info("Selected %s symbols for recording: %s", len(symbols), ", ".join(symbols))
    recorder = WSRecorder(token_ids=symbols)
    event_count = await recorder.run(duration_seconds=duration_seconds)
    logger.info("Finished: %s events recorded", event_count)


def main():
    parser = argparse.ArgumentParser(description="Crypto market data recorder")
    parser.add_argument("--duration", type=int, default=None, help="Recording duration in seconds")
    parser.add_argument("--markets", type=int, default=5, help="Max number of symbols")
    args = parser.parse_args()
    asyncio.run(run_recorder(max_markets=args.markets, duration_seconds=args.duration))


if __name__ == "__main__":
    main()

