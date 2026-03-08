from __future__ import annotations

import base64
from collections.abc import AsyncIterator

import pytest

from backend.ingest.exchanges.coinbase import CoinbaseAdapter


class FakeCoinbaseRestClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []

    async def post(self, path: str, headers: dict[str, str], content: str) -> dict[str, object]:
        self.posts.append({"path": path, "headers": headers, "content": content})
        return {"status": "pending"}

    async def get(self, path: str) -> object:
        if path.endswith("/ticker"):
            return {"bid": "100.0", "ask": "101.0", "price": "100.5", "volume": "42.0"}
        return [{"currency": "USD", "available": "95", "balance": "100"}]


async def fake_coinbase_stream_factory(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"time": "2026-03-07T12:00:00Z", "bids": [["100.0", "1.0"]], "asks": [["101.0", "2.0"]]}
    else:
        yield {"time": "2026-03-07T12:00:00Z", "trade_id": 7, "price": "100.5", "size": "0.3", "side": "buy"}


@pytest.mark.asyncio
async def test_coinbase_adapter_authenticates_and_places_orders() -> None:
    secret = base64.b64encode(b"secret-key").decode("utf-8")
    rest = FakeCoinbaseRestClient()
    adapter = CoinbaseAdapter(api_key="key", api_secret=secret, passphrase="pass", rest_client=rest)

    result = await adapter.place_order({"product_id": "BTC-USD", "side": "buy"})

    assert result["status"] == "pending"
    headers = rest.posts[0]["headers"]
    assert headers["CB-ACCESS-KEY"] == "key"
    assert headers["CB-ACCESS-PASSPHRASE"] == "pass"
    assert "CB-ACCESS-SIGN" in headers


@pytest.mark.asyncio
async def test_coinbase_adapter_normalizes_stream_payloads() -> None:
    adapter = CoinbaseAdapter(stream_factory=fake_coinbase_stream_factory)

    order_book = await anext(adapter.subscribe_order_book("BTC-USD"))
    trade = await anext(adapter.subscribe_trades("BTC-USD"))

    assert order_book.bids[0] == (100.0, 1.0)
    assert order_book.asks[0] == (101.0, 2.0)
    assert trade.trade_id == "7"
    assert trade.side == "buy"
