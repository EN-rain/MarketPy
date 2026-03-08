from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from backend.ingest.exchanges.binance import BinanceAdapter


class FakeRestClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []

    async def post(self, path: str, headers: dict[str, str], content: str) -> dict[str, object]:
        self.posts.append({"path": path, "headers": headers, "content": content})
        return {"status": "NEW", "path": path}

    async def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if path == "/api/v3/ticker/bookTicker":
            return {"bidPrice": "100.0", "askPrice": "101.0", "lastPrice": "100.5", "volume": "42.0"}
        return {
            "positions": [{"symbol": "BTCUSDT", "positionAmt": "1", "entryPrice": "100", "markPrice": "101", "leverage": "2", "unRealizedProfit": "1"}],
            "balances": [{"asset": "USDT", "free": "1000", "locked": "5"}],
        }


async def fake_stream_factory(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"T": 1_700_000_000_000, "b": [["100.0", "1.5"]], "a": [["101.0", "2.0"]]}
    else:
        yield {"T": 1_700_000_000_000, "t": 123, "p": "100.5", "q": "0.2", "m": False}


@pytest.mark.asyncio
async def test_binance_adapter_signs_and_places_orders() -> None:
    rest = FakeRestClient()
    adapter = BinanceAdapter(api_key="key", api_secret="secret", rest_client=rest)

    result = await adapter.place_order({"symbol": "BTCUSDT", "side": "BUY", "timestamp": 1700000000000})

    assert result["status"] == "NEW"
    assert rest.posts[0]["path"] == "/api/v3/order"
    assert rest.posts[0]["headers"] == {"X-MBX-APIKEY": "key"}
    assert "signature=" in str(rest.posts[0]["content"])


@pytest.mark.asyncio
async def test_binance_adapter_normalizes_order_book_and_trade_streams() -> None:
    adapter = BinanceAdapter(stream_factory=fake_stream_factory)

    order_book = await anext(adapter.subscribe_order_book("BTCUSDT"))
    trade = await anext(adapter.subscribe_trades("BTCUSDT"))

    assert order_book.bids[0] == (100.0, 1.5)
    assert order_book.asks[0] == (101.0, 2.0)
    assert trade.trade_id == "123"
    assert trade.side == "buy"


@pytest.mark.asyncio
async def test_binance_adapter_requires_injected_clients_for_network_operations() -> None:
    adapter = BinanceAdapter()

    with pytest.raises(RuntimeError, match="rest_client is required"):
        await adapter.place_order({"symbol": "BTCUSDT"})

    with pytest.raises(RuntimeError, match="stream_factory is required"):
        await anext(adapter.subscribe_order_book("BTCUSDT"))
