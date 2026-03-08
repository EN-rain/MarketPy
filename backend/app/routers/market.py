"""Market endpoint - real-time crypto data from Binance."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

_binance_client: Any = None
_binance_rest: Any = None
_coindesk_client: Any = None

ASSET_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "ADA": "Cardano",
    "DOT": "Polkadot",
    "LINK": "Chainlink",
    "MATIC": "Polygon",
    "AVAX": "Avalanche",
}


def get_binance_client(request: Request | None = None):
    """Get Binance client from app state or create a fallback instance."""
    global _binance_client

    # Try to get from app state if request is provided
    if (
        request
        and hasattr(request.app.state, "binance_client")
        and request.app.state.binance_client is not None
    ):
        return request.app.state.binance_client

    # Fallback to module-level singleton
    if _binance_client is None:
        from backend.ingest.binance_client import BinanceClient
        _binance_client = BinanceClient()
    return _binance_client


def get_binance_rest():
    global _binance_rest
    if _binance_rest is None:
        from backend.ingest.binance_client import BinanceRestClient

        _binance_rest = BinanceRestClient()
    return _binance_rest


def get_coindesk_client():
    global _coindesk_client
    if _coindesk_client is None:
        from backend.app.integrations.coindesk_client import CoinDeskClient

        _coindesk_client = CoinDeskClient()
    return _coindesk_client


def get_asset_name(symbol: str) -> str:
    base = symbol.replace("USDT", "").upper()
    return ASSET_NAMES.get(base, base)


@router.get("/markets")
async def list_markets(request: Request):
    """Return real-time cryptocurrency markets from Binance."""
    client = get_binance_client(request)

    if client.is_running and client.markets:
        return [
            {
                "market_id": m.symbol,
                "question": get_asset_name(m.symbol),
                "active": m.active,
                "mid": m.price,
                "spread": m.spread / m.price if m.price > 0 else 0,
                "bid": m.bid,
                "ask": m.ask,
                "change_24h": m.change_24h,
                "change_24h_pct": m.change_24h_pct,
                "volume_24h": m.volume_24h,
                "high_24h": m.high_24h,
                "low_24h": m.low_24h,
                "last_update": m.last_update.isoformat(),
            }
            for m in client.markets.values()
        ]
    # Cold-start fallback so UI can still select markets before first stream tick arrives.
    return [
        {
            "market_id": symbol.upper(),
            "question": get_asset_name(symbol.upper()),
            "active": True,
            "mid": 0.0,
            "spread": 0.0,
            "bid": 0.0,
            "ask": 0.0,
            "change_24h": 0.0,
            "change_24h_pct": 0.0,
            "volume_24h": 0.0,
            "high_24h": 0.0,
            "low_24h": 0.0,
            "last_update": datetime.now(UTC).isoformat(),
        }
        for symbol in client.DEFAULT_SYMBOLS
    ]


@router.get("/market/{market_id}")
async def get_market(market_id: str, request: Request):
    """Return detailed market data including candles."""
    client = get_binance_client(request)
    rest = get_binance_rest()
    symbol = market_id.upper()

    market = client.get_market(symbol.lower())
    if market:
        candles = await rest.get_klines(symbol, interval="1h", limit=50)
        return {
            "market_id": symbol,
            "question": get_asset_name(market.symbol),
            "active": market.active,
            "bid": market.bid,
            "ask": market.ask,
            "mid": market.price,
            "spread": market.spread / market.price if market.price > 0 else 0,
            "last_trade_price": market.price,
            "change_24h": market.change_24h,
            "change_24h_pct": market.change_24h_pct,
            "volume_24h": market.volume_24h,
            "high_24h": market.high_24h,
            "low_24h": market.low_24h,
            "updated_at": market.last_update.isoformat(),
            "candles": [
                {
                    "timestamp": c.timestamp.isoformat(),
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in candles
            ],
        }

    candles = await rest.get_klines(symbol, interval="1h", limit=50)
    if candles:
        latest = candles[-1]
        return {
            "market_id": symbol,
            "question": get_asset_name(symbol),
            "active": True,
            "bid": latest.close * 0.999,
            "ask": latest.close * 1.001,
            "mid": latest.close,
            "spread": 0.002,
            "last_trade_price": latest.close,
            "updated_at": datetime.now(UTC).isoformat(),
            "candles": [
                {
                    "timestamp": c.timestamp.isoformat(),
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in candles
            ],
        }
    raise HTTPException(status_code=404, detail=f"Market {market_id} not found")


@router.post("/markets/start-stream")
async def start_market_stream(request: Request, symbols: list[str] | None = None):
    client = get_binance_client(request)
    if client.is_running:
        return {"status": "already_running", "symbols": list(client.markets.keys())}
    asyncio.create_task(client.start(symbols))
    return {"status": "started", "symbols": symbols or client.DEFAULT_SYMBOLS}


@router.post("/markets/stop-stream")
async def stop_market_stream(request: Request):
    client = get_binance_client(request)
    client.stop()
    return {"status": "stopped"}


@router.get("/markets/status")
async def get_stream_status(request: Request):
    client = get_binance_client(request)
    return {
        "is_running": client.is_running,
        "symbols_tracked": list(client.markets.keys()),
        "event_count": client.event_count,
        "markets": [
            {"symbol": m.symbol, "price": m.price, "change_24h_pct": m.change_24h_pct}
            for m in client.markets.values()
        ],
    }


@router.get("/metrics/market/{coin_id}")
async def get_market_metrics(coin_id: str, request: Request):
    """Return CoinPaprika-backed market metrics with staleness indicator."""
    service = getattr(request.app.state, "market_metrics_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Market metrics service unavailable")
    result = service.get_metrics(coin_id)
    if result is None:
        # Trigger on-demand fetch if cache is empty.
        updated = await service.update_coin(coin_id)
        if not updated:
            raise HTTPException(
                status_code=503, detail="CoinPaprika unavailable and no cached data"
            )
        result = service.get_metrics(coin_id)
        if result is None:
            raise HTTPException(status_code=503, detail="Failed to load market metrics")

    metrics = result["metrics"]
    return {
        "coin_id": metrics.coin_id,
        "volume_24h": metrics.volume_24h,
        "market_cap": metrics.market_cap,
        "circulating_supply": metrics.circulating_supply,
        "total_supply": metrics.total_supply,
        "max_supply": metrics.max_supply,
        "timestamp": metrics.timestamp.isoformat(),
        "is_stale": bool(result["is_stale"]),
        "age_seconds": float(result["age_seconds"]),
    }


@router.get("/correlation/bpi")
async def get_bpi_correlations(indices: str = "SPX,NDX,DXY"):
    """Expose CoinDesk BPI correlations with traditional market indices."""
    client = get_coindesk_client()
    index_list = [item.strip().upper() for item in indices.split(",") if item.strip()]
    correlations = await client.calculate_correlation(index_list)
    return {"indices": index_list, "correlations": correlations}
