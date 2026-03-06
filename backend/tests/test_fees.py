"""Tests for crypto fee calculator."""

from backend.sim.fees import calculate_fee, calculate_fee_pct, estimate_breakeven_edge


class TestCalculateFee:
    def test_fee_scales_with_notional(self):
        fee_low = calculate_fee(100.0, 1.0, fee_rate=0.001)
        fee_high = calculate_fee(200.0, 1.0, fee_rate=0.001)
        assert fee_high == 2 * fee_low

    def test_zero_for_non_positive_inputs(self):
        assert calculate_fee(0.0, 1.0) == 0.0
        assert calculate_fee(100.0, 0.0) == 0.0

    def test_known_value(self):
        fee = calculate_fee(25000.0, 0.5, fee_rate=0.001)
        assert fee == 12.5


class TestCalculateFeePct:
    def test_fee_pct_constant(self):
        assert calculate_fee_pct(100.0, fee_rate=0.001) == 0.1
        assert calculate_fee_pct(30000.0, fee_rate=0.001) == 0.1


class TestBreakevenEdge:
    def test_positive_breakeven(self):
        edge = estimate_breakeven_edge(30000.0, 5.0, fee_rate=0.001)
        assert edge > 0

    def test_wider_spread_higher_breakeven(self):
        edge_narrow = estimate_breakeven_edge(30000.0, 2.0, fee_rate=0.001)
        edge_wide = estimate_breakeven_edge(30000.0, 10.0, fee_rate=0.001)
        assert edge_wide > edge_narrow

