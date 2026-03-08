"""Fill models for simulator execution quality."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.app.models.market import OrderBookSnapshot, Side
from backend.sim.fees import calculate_fee


class FillModelLevel(str, Enum):
    M1_MID = "M1"
    M2_BIDASK = "M2"
    M3_DEPTH = "M3"


@dataclass(slots=True)
class OrderBookLevel:
    price: float
    size: float


@dataclass(slots=True)
class OrderBookDepth:
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]

    @property
    def total_bid_size(self) -> float:
        return sum(level.size for level in self.bids)

    @property
    def total_ask_size(self) -> float:
        return sum(level.size for level in self.asks)


@dataclass
class FillResult:
    """Result of attempting to fill an order."""

    filled: bool
    fill_price: float = 0.0
    fill_size: float = 0.0
    fee: float = 0.0
    slippage: float = 0.0
    reason: str | None = None

    @property
    def total_cost(self) -> float:
        return self.fill_price * self.fill_size + self.fee


def _depth_from_snapshot(orderbook: OrderBookSnapshot) -> OrderBookDepth | None:
    if not orderbook.bids and not orderbook.asks:
        return None
    bids = [OrderBookLevel(price=float(price), size=float(size)) for price, size in orderbook.bids]
    asks = [OrderBookLevel(price=float(price), size=float(size)) for price, size in orderbook.asks]
    return OrderBookDepth(bids=bids, asks=asks)


def fill_order_m1(
    side: Side,
    size: float,
    orderbook: OrderBookSnapshot,
    fee_rate: float = 0.02,
    fee_exponent: float = 2.0,
) -> FillResult:
    if orderbook.mid is None:
        return FillResult(filled=False)
    fill_price = orderbook.mid
    fee = calculate_fee(fill_price, size, fee_rate, fee_exponent)
    return FillResult(filled=True, fill_price=fill_price, fill_size=size, fee=fee, slippage=0.0)


def fill_order_m2(
    side: Side,
    size: float,
    orderbook: OrderBookSnapshot,
    fee_rate: float = 0.02,
    fee_exponent: float = 2.0,
    limit_price: float | None = None,
) -> FillResult:
    if orderbook.best_bid is None or orderbook.best_ask is None or orderbook.mid is None:
        return FillResult(filled=False, reason="no_orderbook")

    if side == Side.BUY:
        fill_price = orderbook.best_ask
        if limit_price is not None and fill_price > limit_price:
            return FillResult(filled=False, reason="not_crossed")
    else:
        fill_price = orderbook.best_bid
        if limit_price is not None and fill_price < limit_price:
            return FillResult(filled=False, reason="not_crossed")

    fee = calculate_fee(fill_price, size, fee_rate, fee_exponent)
    slippage = abs(fill_price - orderbook.mid)
    return FillResult(
        filled=True,
        fill_price=fill_price,
        fill_size=size,
        fee=fee,
        slippage=slippage,
    )


def fill_order_m3(
    side: Side,
    size: float,
    orderbook: OrderBookSnapshot,
    fee_rate: float = 0.02,
    fee_exponent: float = 2.0,
    max_depth_pct: float = 0.10,
    limit_price: float | None = None,
) -> FillResult:
    depth = _depth_from_snapshot(orderbook)
    if depth is None:
        # Fallback to M2 when depth is unavailable.
        return fill_order_m2(side, size, orderbook, fee_rate, fee_exponent, limit_price)

    levels = depth.asks if side == Side.BUY else depth.bids
    available_depth = depth.total_ask_size if side == Side.BUY else depth.total_bid_size
    if available_depth <= 0:
        return FillResult(filled=False, reason="no_depth")

    if size > available_depth * max_depth_pct:
        return FillResult(filled=False, reason="depth_limit_exceeded")

    remaining = size
    cost = 0.0
    filled_size = 0.0

    for level in levels:
        if remaining <= 0:
            break
        price = level.price
        if side == Side.BUY and limit_price is not None and price > limit_price:
            break
        if side == Side.SELL and limit_price is not None and price < limit_price:
            break

        take = min(remaining, level.size)
        cost += price * take
        remaining -= take
        filled_size += take

    if filled_size <= 0:
        return FillResult(filled=False, reason="not_crossed")

    weighted_price = cost / filled_size
    mid = orderbook.mid if orderbook.mid is not None else weighted_price
    fee = calculate_fee(weighted_price, filled_size, fee_rate, fee_exponent)
    slippage = abs(weighted_price - mid)
    return FillResult(
        filled=True,
        fill_price=weighted_price,
        fill_size=filled_size,
        fee=fee,
        slippage=slippage,
    )


def fill_order(
    side: Side,
    size: float,
    orderbook: OrderBookSnapshot,
    model: FillModelLevel = FillModelLevel.M2_BIDASK,
    fee_rate: float = 0.02,
    fee_exponent: float = 2.0,
    limit_price: float | None = None,
) -> FillResult:
    if model == FillModelLevel.M1_MID:
        return fill_order_m1(side, size, orderbook, fee_rate, fee_exponent)
    if model == FillModelLevel.M3_DEPTH:
        return fill_order_m3(side, size, orderbook, fee_rate, fee_exponent, limit_price=limit_price)
    return fill_order_m2(side, size, orderbook, fee_rate, fee_exponent, limit_price)
