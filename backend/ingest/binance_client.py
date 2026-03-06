"""Binance WebSocket client for real-time cryptocurrency market data.

Streams real-time price data from Binance via WebSocket.
Supports: ticker prices, orderbook, trades, klines/candles
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import websockets

from backend.ingest.exchange_client import ExchangeClient, ExchangeConfig, ExchangeType

logger = logging.getLogger(__name__)

# Binance WebSocket endpoints
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_WS_STREAM_URL = "wss://stream.binance.com:9443/stream"


@dataclass
class CryptoMarket:
    """Represents a cryptocurrency market."""
    symbol: str
    base_asset: str
    quote_asset: str
    price: float = 0.0
    change_24h: float = 0.0
    change_24h_pct: float = 0.0
    volume_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


@dataclass
class Candle:
    """OHLCV candlestick data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class BinanceClient:
    """Real-time Binance WebSocket client.
    
    Usage:
        client = BinanceClient()
        client.add_handler(process_market_update)
        await client.start(["btcusdt", "ethusdt"])
    """

    # Popular crypto pairs for prediction markets
    DEFAULT_SYMBOLS = [
        "btcusdt",   # Bitcoin
        "ethusdt",   # Ethereum
        "solusdt",   # Solana
        "adausdt",   # Cardano
        "dotusdt",   # Polkadot
        "linkusdt",  # Chainlink
        "maticusdt", # Polygon
        "avaxusdt",  # Avalanche
    ]

    def __init__(self) -> None:
        self.symbols: list[str] = []
        self._handlers: list[Callable[[str, dict], None]] = []
        self._running = False
        self._ws = None
        self._markets: dict[str, CryptoMarket] = {}
        self._candles: dict[str, list[Candle]] = {}
        self._event_count = 0

    def add_handler(self, handler: Callable[[str, dict], None]) -> None:
        """Register a handler for market updates."""
        self._handlers.append(handler)

    def remove_handler(self, handler: Callable[[str, dict], None]) -> None:
        """Remove a handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def _build_stream_url(self, symbols: list[str]) -> str:
        """Build WebSocket stream URL for multiple symbols."""
        # Subscribe to ticker streams for each symbol
        streams = "/".join([f"{s}@ticker" for s in symbols])
        return f"{BINANCE_WS_STREAM_URL}?streams={streams}"

    def _parse_ticker(self, data: dict) -> tuple[str, CryptoMarket] | None:
        """Parse ticker data into CryptoMarket."""
        try:
            symbol = data.get("s", "").lower()
            if not symbol:
                return None

            market = CryptoMarket(
                symbol=symbol.upper(),
                base_asset=symbol[:-4].upper() if symbol.endswith("usdt") else symbol[:3].upper(),
                quote_asset="USDT",
                price=float(data.get("c", 0)),
                change_24h=float(data.get("p", 0)),
                change_24h_pct=float(data.get("P", 0)),
                volume_24h=float(data.get("v", 0)),
                high_24h=float(data.get("h", 0)),
                low_24h=float(data.get("l", 0)),
                bid=float(data.get("b", 0)),
                ask=float(data.get("a", 0)),
                spread=float(data.get("a", 0)) - float(data.get("b", 0)),
                last_update=datetime.now(UTC),
                active=True,
            )
            return symbol, market
        except Exception as e:
            logger.error(f"Error parsing ticker: {e}")
            return None

    async def _broadcast(self, symbol: str, data: dict) -> None:
        """Broadcast update to all handlers."""
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(symbol, data)
                else:
                    handler(symbol, data)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    async def start(self, symbols: list[str] | None = None) -> None:
        """Start streaming data for specified symbols."""
        self.symbols = [s.lower() for s in (symbols or self.DEFAULT_SYMBOLS)]
        self._running = True
        self._event_count = 0

        url = self._build_stream_url(self.symbols)
        logger.info(f"Connecting to Binance WebSocket for {len(self.symbols)} symbols")

        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    logger.info("Connected to Binance WebSocket")

                    while self._running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                            data = json.loads(msg)

                            # Parse combined stream format
                            if "stream" in data and "data" in data:
                                ticker_data = data["data"]

                                parsed = self._parse_ticker(ticker_data)
                                if parsed:
                                    symbol, market = parsed
                                    self._markets[symbol] = market
                                    self._event_count += 1

                                    # Broadcast to handlers
                                    await self._broadcast(symbol, {
                                        "type": "ticker",
                                        "market": market,
                                        "raw": ticker_data,
                                    })

                                    if self._event_count % 100 == 0:
                                        logger.debug(f"Processed {self._event_count} events")

                        except TimeoutError:
                            # Send ping to keep connection alive
                            await ws.send(json.dumps({"method": "LIST_SUBSCRIPTIONS", "id": 1}))
                        except websockets.ConnectionClosed:
                            logger.warning("Binance WebSocket closed, reconnecting...")
                            break

            except Exception as e:
                logger.error(f"Binance WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect delay

    def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False
        logger.info("Binance client stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def markets(self) -> dict[str, CryptoMarket]:
        """Get current market data."""
        return self._markets.copy()

    def get_market(self, symbol: str) -> CryptoMarket | None:
        """Get specific market data."""
        return self._markets.get(symbol.lower())

    @property
    def event_count(self) -> int:
        return self._event_count


class BinanceRestClient:
    """REST API client for Binance (for historical data)."""

    BASE_URL = "https://api.binance.com"

    def __init__(self) -> None:
        import httpx
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> list[Candle]:
        """Get historical klines/candles.
        
        Intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        """
        try:
            response = await self._client.get(
                "/api/v3/klines",
                params={
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "limit": limit,
                }
            )
            response.raise_for_status()
            data = response.json()

            candles = []
            for item in data:
                # Binance kline format: [time, open, high, low, close, volume, ...]
                candles.append(Candle(
                    timestamp=datetime.fromtimestamp(item[0] / 1000, UTC),
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                ))
            return candles
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return []

    async def get_exchange_info(self) -> dict:
        """Get exchange info including available symbols."""
        try:
            response = await self._client.get("/api/v3/exchangeInfo")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching exchange info: {e}")
            return {}

    async def get_book_ticker(self, symbol: str) -> dict[str, float] | None:
        """Get best bid/ask for a symbol."""
        try:
            response = await self._client.get(
                "/api/v3/ticker/bookTicker",
                params={"symbol": symbol.upper()},
            )
            response.raise_for_status()
            data = response.json()
            bid = float(data.get("bidPrice", 0.0))
            ask = float(data.get("askPrice", 0.0))
            if bid <= 0 and ask <= 0:
                return None
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else max(bid, ask)
            return {"bid": bid, "ask": ask, "mid": mid}
        except Exception as e:
            logger.error(f"Error fetching book ticker for {symbol}: {e}")
            return None


class BinanceClientAdapter:
    """Backward-compatible adapter that routes legacy Binance REST calls to ExchangeClient."""

    _warned = False

    def __init__(self, exchange_client: ExchangeClient | None = None) -> None:
        if exchange_client is None:
            config = ExchangeConfig(
                exchange_type=ExchangeType.BINANCE,
                api_key=os.getenv("BINANCE_API_KEY"),
                api_secret=os.getenv("BINANCE_API_SECRET"),
            )
            exchange_client = ExchangeClient(config)
        self._client = exchange_client

    def _warn_deprecated(self) -> None:
        if self.__class__._warned:
            return
        self.__class__._warned = True
        message = (
            "BinanceClientAdapter/legacy Binance REST interface is deprecated. "
            "Migrate to backend.ingest.exchange_client.ExchangeClient "
            "(see docs/migration-notes-phase41.md)."
        )
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        logger.warning(message)

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[Candle]:
        self._warn_deprecated()
        converted_symbol = symbol.upper()
        if "/" not in converted_symbol and converted_symbol.endswith("USDT"):
            converted_symbol = f"{converted_symbol[:-4]}/USDT"
        candles = await self._client.fetch_ohlcv(converted_symbol, timeframe=interval, limit=limit)
        return [
            Candle(
                timestamp=c.timestamp,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in candles
        ]

    async def get_book_ticker(self, symbol: str) -> dict[str, float] | None:
        self._warn_deprecated()
        converted_symbol = symbol.upper()
        if "/" not in converted_symbol and converted_symbol.endswith("USDT"):
            converted_symbol = f"{converted_symbol[:-4]}/USDT"
        snapshot = await self._client.fetch_order_book(converted_symbol, limit=1)
        if snapshot.best_bid is None and snapshot.best_ask is None and snapshot.mid is None:
            return None
        return {
            "bid": snapshot.best_bid or 0.0,
            "ask": snapshot.best_ask or 0.0,
            "mid": snapshot.mid or 0.0,
        }

    async def close(self) -> None:
        await self._client.close()
