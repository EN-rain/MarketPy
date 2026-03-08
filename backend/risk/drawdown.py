"""Drawdown tracking and automatic control actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrawdownStatus:
    peak_equity: float
    current_equity: float
    drawdown: float
    reduce_positions: bool
    halt_trading: bool
    adjusted_positions: dict[str, float]


class DrawdownController:
    """Tracks peak equity and applies drawdown-based controls."""

    def __init__(self) -> None:
        self.peak_equity: float = 0.0

    def update_peak(self, equity: float) -> None:
        self.peak_equity = max(self.peak_equity, float(equity))

    def compute_drawdown(self, current_equity: float) -> float:
        self.update_peak(current_equity)
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - current_equity) / self.peak_equity)

    def check_drawdown_limits(
        self,
        *,
        current_equity: float,
        position_values: dict[str, float],
    ) -> DrawdownStatus:
        drawdown = self.compute_drawdown(current_equity)
        reduce_positions = drawdown >= 0.10
        halt_trading = drawdown >= 0.20

        if halt_trading:
            adjusted = {key: 0.0 for key in position_values}
        elif reduce_positions:
            adjusted = {key: float(value) * 0.5 for key, value in position_values.items()}
        else:
            adjusted = {key: float(value) for key, value in position_values.items()}

        return DrawdownStatus(
            peak_equity=float(self.peak_equity),
            current_equity=float(current_equity),
            drawdown=float(drawdown),
            reduce_positions=reduce_positions,
            halt_trading=halt_trading,
            adjusted_positions=adjusted,
        )
