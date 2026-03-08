"""Advanced order type helpers and execution schedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.execution.order_manager import OrderManager, OrderRecord, OrderStatus


@dataclass(frozen=True, slots=True)
class BracketOrder:
    entry: OrderRecord
    stop_loss: OrderRecord
    take_profit: OrderRecord


@dataclass(frozen=True, slots=True)
class IcebergOrderState:
    parent_id: str
    total_size: float
    visible_size: float
    filled_size: float
    active_order_id: str
    remaining_size: float


@dataclass(frozen=True, slots=True)
class ScheduledSlice:
    execute_at: datetime
    size: float
    limit_price: float | None = None


class AdvancedOrderEngine:
    """Adds bracket, trailing-stop, iceberg, TWAP and VWAP behavior."""

    def __init__(self, manager: OrderManager | None = None) -> None:
        self.manager = manager or OrderManager()
        self._oco_groups: dict[str, tuple[str, str]] = {}
        self._icebergs: dict[str, IcebergOrderState] = {}

    def place_bracket_order(
        self,
        *,
        market_id: str,
        side: str,
        entry_size: float,
        entry_price: float | None,
        stop_loss_price: float,
        take_profit_price: float,
    ) -> BracketOrder:
        oco_group = str(uuid4())
        entry = self.manager.place_order(
            market_id=market_id,
            side=side,
            size=entry_size,
            order_type="bracket",
            limit_price=entry_price,
            metadata={"role": "entry", "oco_group": oco_group},
        )
        opposite = "SELL" if side.upper() == "BUY" else "BUY"
        stop_loss = self.manager.place_order(
            market_id=market_id,
            side=opposite,
            size=entry_size,
            order_type="stop_loss",
            limit_price=stop_loss_price,
            metadata={"role": "stop_loss", "parent_order_id": entry.order_id, "oco_group": oco_group, "active": False},
        )
        take_profit = self.manager.place_order(
            market_id=market_id,
            side=opposite,
            size=entry_size,
            order_type="take_profit",
            limit_price=take_profit_price,
            metadata={"role": "take_profit", "parent_order_id": entry.order_id, "oco_group": oco_group, "active": False},
        )
        self._oco_groups[oco_group] = (stop_loss.order_id, take_profit.order_id)
        return BracketOrder(entry=entry, stop_loss=stop_loss, take_profit=take_profit)

    def on_entry_filled(self, order_id: str) -> None:
        entry = self.manager.orders[order_id]
        if entry.metadata.get("role") != "entry":
            return
        self.manager.update_status(order_id, OrderStatus.FILLED)
        oco_group = str(entry.metadata.get("oco_group", ""))
        for child_id in self._oco_groups.get(oco_group, ()):
            child = self.manager.orders[child_id]
            child.metadata["active"] = True
            child.updated_at = datetime.now(UTC)

    def on_oco_child_filled(self, order_id: str) -> None:
        child = self.manager.orders[order_id]
        oco_group = str(child.metadata.get("oco_group", ""))
        self.manager.update_status(order_id, OrderStatus.FILLED)
        sibling_ids = self._oco_groups.get(oco_group, ())
        for sibling_id in sibling_ids:
            if sibling_id != order_id and self.manager.orders[sibling_id].status == OrderStatus.PENDING:
                self.manager.cancel_order(sibling_id)

    def update_trailing_stop(self, order_id: str, current_price: float) -> float:
        order = self.manager.orders[order_id]
        if order.order_type != "trailing_stop":
            raise ValueError("order is not a trailing_stop order")

        trail_percent = order.trail_percent
        trail_amount = order.trail_amount
        if trail_percent is None and trail_amount is None:
            raise ValueError("trailing stop is missing trail configuration")

        distance = float(current_price * trail_percent) if trail_percent is not None else float(trail_amount)
        if order.side.upper() == "SELL":
            new_stop = current_price - distance
            current_stop = order.limit_price if order.limit_price is not None else float("-inf")
            next_stop = max(current_stop, new_stop)
        else:
            new_stop = current_price + distance
            current_stop = order.limit_price if order.limit_price is not None else float("inf")
            next_stop = min(current_stop, new_stop)

        order.limit_price = float(next_stop)
        order.updated_at = datetime.now(UTC)
        return float(next_stop)

    def place_iceberg_order(
        self,
        *,
        market_id: str,
        side: str,
        total_size: float,
        visible_size: float,
        limit_price: float,
    ) -> IcebergOrderState:
        if visible_size <= 0 or total_size <= 0:
            raise ValueError("iceberg sizes must be positive")
        if visible_size > total_size:
            raise ValueError("visible_size cannot exceed total_size")

        parent_id = str(uuid4())
        first_size = min(visible_size, total_size)
        first_order = self.manager.place_order(
            market_id=market_id,
            side=side,
            size=first_size,
            order_type="iceberg",
            limit_price=limit_price,
            metadata={"parent_iceberg_id": parent_id, "slice_index": 0},
        )
        state = IcebergOrderState(
            parent_id=parent_id,
            total_size=float(total_size),
            visible_size=float(visible_size),
            filled_size=0.0,
            active_order_id=first_order.order_id,
            remaining_size=float(total_size - first_size),
        )
        self._icebergs[parent_id] = state
        return state

    def on_iceberg_slice_filled(self, parent_id: str, filled_size: float) -> IcebergOrderState:
        state = self._icebergs[parent_id]
        updated_filled = min(state.total_size, state.filled_size + float(filled_size))
        remaining = max(0.0, state.total_size - updated_filled)

        next_order_id = state.active_order_id
        if remaining > 0:
            prev = self.manager.orders[state.active_order_id]
            next_size = min(state.visible_size, remaining)
            next_order = self.manager.place_order(
                market_id=prev.market_id,
                side=prev.side,
                size=next_size,
                order_type="iceberg",
                limit_price=prev.limit_price,
                metadata={
                    "parent_iceberg_id": parent_id,
                    "slice_index": int(prev.metadata.get("slice_index", 0)) + 1,
                },
            )
            next_order_id = next_order.order_id

        new_state = IcebergOrderState(
            parent_id=parent_id,
            total_size=state.total_size,
            visible_size=state.visible_size,
            filled_size=updated_filled,
            active_order_id=next_order_id,
            remaining_size=remaining,
        )
        self._icebergs[parent_id] = new_state
        return new_state

    @staticmethod
    def build_twap_schedule(
        *,
        total_size: float,
        slices: int,
        start_time: datetime,
        duration_seconds: int,
        limit_price: float | None = None,
    ) -> list[ScheduledSlice]:
        if total_size <= 0 or slices <= 0:
            raise ValueError("total_size and slices must be positive")
        interval = max(duration_seconds / slices, 1.0)
        chunk = total_size / slices
        return [
            ScheduledSlice(
                execute_at=start_time + timedelta(seconds=interval * index),
                size=float(chunk),
                limit_price=limit_price,
            )
            for index in range(slices)
        ]

    @staticmethod
    def build_vwap_schedule(
        *,
        total_size: float,
        volume_profile: list[float],
        start_time: datetime,
        interval_seconds: int,
        limit_price: float | None = None,
    ) -> list[ScheduledSlice]:
        if total_size <= 0:
            raise ValueError("total_size must be positive")
        if not volume_profile:
            raise ValueError("volume_profile cannot be empty")
        weights = [max(float(v), 0.0) for v in volume_profile]
        total_weight = sum(weights)
        if total_weight <= 0:
            equal = 1.0 / len(weights)
            weights = [equal for _ in weights]
        else:
            weights = [value / total_weight for value in weights]
        return [
            ScheduledSlice(
                execute_at=start_time + timedelta(seconds=interval_seconds * index),
                size=float(total_size * weight),
                limit_price=limit_price,
            )
            for index, weight in enumerate(weights)
        ]
