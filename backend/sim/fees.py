"""Crypto fee calculator.

Default model uses simple notional-based taker fees:
    fee = notional * fee_rate = (price * size) * fee_rate
"""

from __future__ import annotations


def calculate_fee(
    price: float,
    size: float,
    fee_rate: float = 0.001,  # 10 bps default
    exponent: float = 2.0,  # retained for backward compatibility
) -> float:
    """Calculate trading fee for a crypto trade."""
    del exponent
    if price <= 0 or size <= 0:
        return 0.0
    return max(0.0, price * size * fee_rate)


def calculate_fee_pct(price: float, fee_rate: float = 0.001, exponent: float = 2.0) -> float:
    """Return fee as percent of notional."""
    del price, exponent
    return max(0.0, fee_rate * 100)


def estimate_breakeven_edge(
    price: float,
    spread: float,
    fee_rate: float = 0.001,
    exponent: float = 2.0,
) -> float:
    """Estimate minimum edge in price units to break even."""
    half_spread = max(0.0, spread) / 2
    fee_pct = calculate_fee_pct(price, fee_rate, exponent) / 100
    return half_spread + max(0.0, price) * fee_pct

