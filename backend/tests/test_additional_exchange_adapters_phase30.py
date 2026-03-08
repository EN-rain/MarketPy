from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from backend.ingest.exchanges.deribit import DeribitAdapter
from backend.ingest.exchanges.gateio import GateAdapter
from backend.ingest.exchanges.huobi import HuobiAdapter
from backend.ingest.exchanges.kucoin import KuCoinAdapter


class FakeRest:
    async def post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        return {"path": path, "payload": payload}

    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        if "kucoin" in path or path.endswith("level1"):
            return {"data": {"bestBid": "100", "bestAsk": "101", "price": "100.5", "vol": "10"}}
        if "tickers" in path:
            return [{"highest_bid": "100", "lowest_ask": "101", "last": "100.5", "base_volume": "12"}]
        if "merged" in path:
            return {"tick": {"bid": ["100"], "ask": ["101"], "close": "100.5", "amount": "14"}}
        if "ticker" in path:
            return {"result": {"best_bid_price": 100, "best_ask_price": 101, "last_price": 100.5, "stats": {"volume": 20}}}
        return {"result": []}


async def stream_kucoin(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"bids": [["100", "1"]], "asks": [["101", "2"]]}
    else:
        yield {"tradeId": "1", "price": "100.5", "size": "0.2", "side": "buy"}


async def stream_gate(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"bids": [["100", "1"]], "asks": [["101", "2"]]}
    else:
        yield {"id": "2", "price": "100.5", "amount": "0.2", "side": "sell"}


async def stream_huobi(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"tick": {"bids": [["100", "1"]], "asks": [["101", "2"]]}}
    else:
        yield {"tick": {"id": "3", "price": "100.5", "amount": "0.2", "direction": "buy"}}


async def stream_deribit(kind: str, symbol: str) -> AsyncIterator[dict[str, object]]:
    if kind == "order_book":
        yield {"result": {"bids": [[100, 1]], "asks": [[101, 2]]}}
    else:
        yield {"result": {"trade_id": "4", "price": 100.5, "amount": 0.2, "direction": "buy"}}


@pytest.mark.asyncio
async def test_kucoin_adapter() -> None:
    adapter = KuCoinAdapter(rest_client=FakeRest(), stream_factory=stream_kucoin)
    ob = await anext(adapter.subscribe_order_book("BTC-USDT"))
    tr = await anext(adapter.subscribe_trades("BTC-USDT"))
    tick = await adapter.get_ticker("BTC-USDT")
    placed = await adapter.place_order({"symbol": "BTC-USDT"})
    assert ob.bids[0] == (100.0, 1.0)
    assert tr.trade_id == "1"
    assert tick.last == 100.5
    assert placed["path"] == "/api/v1/orders"


@pytest.mark.asyncio
async def test_gate_huobi_deribit_adapters() -> None:
    gate = GateAdapter(rest_client=FakeRest(), stream_factory=stream_gate)
    huobi = HuobiAdapter(rest_client=FakeRest(), stream_factory=stream_huobi)
    deribit = DeribitAdapter(rest_client=FakeRest(), stream_factory=stream_deribit)

    assert (await anext(gate.subscribe_trades("BTC_USDT"))).trade_id == "2"
    assert (await huobi.get_ticker("btcusdt")).ask == 101.0
    assert (await deribit.get_ticker("BTC-PERPETUAL")).bid == 100.0
