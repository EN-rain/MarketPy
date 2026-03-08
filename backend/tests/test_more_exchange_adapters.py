from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from backend.ingest.exchanges.bybit import BybitAdapter
from backend.ingest.exchanges.kraken import KrakenAdapter
from backend.ingest.exchanges.okx import OKXAdapter


class FakeRest:
    async def post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        return {"path": path, "payload": payload}


class FakeKrakenRest(FakeRest):
    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        return {"result": {"XBTUSDT": {"b": ["100.0"], "a": ["101.0"], "c": ["100.5"], "v": ["10", "20"]}}}


class FakeBybitRest(FakeRest):
    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        return {"result": {"list": [{"bid1Price": "100.0", "ask1Price": "101.0", "lastPrice": "100.5", "volume24h": "25"}]}}


class FakeOKXRest(FakeRest):
    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        return {"data": [{"bidPx": "100.0", "askPx": "101.0", "last": "100.5", "vol24h": "30"}]}


async def kraken_stream(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"bids": [["100.0", "1.0"]], "asks": [["101.0", "2.0"]]}
    else:
        yield {"trade_id": "1", "price": "100.5", "volume": "0.1", "side": "buy"}


async def bybit_stream(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"b": [["100.0", "1.0"]], "a": [["101.0", "2.0"]]}
    else:
        yield {"i": "1", "p": "100.5", "v": "0.1", "S": "Buy"}


async def okx_stream(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"data": [{"bids": [["100.0", "1.0", "0", "1"]], "asks": [["101.0", "2.0", "0", "1"]]}]}
    else:
        yield {"data": [{"tradeId": "1", "px": "100.5", "sz": "0.1", "side": "buy"}]}


@pytest.mark.asyncio
async def test_kraken_adapter_normalizes_and_places_order() -> None:
    adapter = KrakenAdapter(rest_client=FakeKrakenRest(), stream_factory=kraken_stream)
    trade = await anext(adapter.subscribe_trades("XBT/USDT"))
    ticker = await adapter.get_ticker("XBTUSDT")
    placed = await adapter.place_order({"pair": "XBTUSDT"})
    assert trade.trade_id == "1"
    assert ticker.bid == 100.0
    assert placed["path"] == "/0/private/AddOrder"


@pytest.mark.asyncio
async def test_bybit_adapter_supports_linear_market_payloads() -> None:
    adapter = BybitAdapter(rest_client=FakeBybitRest(), stream_factory=bybit_stream, market_type="linear")
    order_book = await anext(adapter.subscribe_order_book("BTCUSDT"))
    ticker = await adapter.get_ticker("BTCUSDT")
    placed = await adapter.place_order({"symbol": "BTCUSDT"})
    assert order_book.bids[0] == (100.0, 1.0)
    assert ticker.last == 100.5
    assert placed["payload"]["category"] == "linear"


@pytest.mark.asyncio
async def test_okx_adapter_supports_spot_payloads() -> None:
    adapter = OKXAdapter(rest_client=FakeOKXRest(), stream_factory=okx_stream, instrument_type="SPOT")
    trade = await anext(adapter.subscribe_trades("BTC-USDT"))
    ticker = await adapter.get_ticker("BTC-USDT")
    placed = await adapter.place_order({"instId": "BTC-USDT"})
    assert trade.side == "buy"
    assert ticker.ask == 101.0
    assert placed["payload"]["instType"] == "SPOT"
