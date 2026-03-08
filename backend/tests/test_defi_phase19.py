"""Phase 19 DeFi integration tests."""

from __future__ import annotations

import pytest

from backend.ingest.exchanges.pancakeswap import PancakeSwapAdapter
from backend.ingest.exchanges.uniswap import UniswapAdapter
from backend.ingest.yield_optimizer import YieldOptimizer, YieldVenue
from backend.risk.defi_risk import DeFiRiskManager


@pytest.mark.asyncio
async def test_uniswap_and_pancakeswap_adapters_support_pool_fetch_and_swaps() -> None:
    pools = {"ETH/USDC": {"bid": 1999.0, "ask": 2001.0, "mid": 2000.0, "liquidity": 500000.0, "volume_24h": 1000000.0, "slippage_bps": 20.0}}
    uni = UniswapAdapter(pools=pools)
    cake = PancakeSwapAdapter(pools=pools)

    uni_ticker = await uni.get_ticker("ETH/USDC")
    pool = await uni.get_liquidity_pool("ETH/USDC")
    swap = await cake.place_order({"symbol": "ETH/USDC", "size": 1.0, "max_slippage_bps": 25.0})

    assert uni_ticker.last == pytest.approx(2000.0)
    assert pool["liquidity"] == pytest.approx(500000.0)
    assert swap["status"] == "filled"


def test_defi_risk_and_yield_optimizer() -> None:
    risk = DeFiRiskManager().snapshot(
        audit_score=0.9,
        tvl=5_000_000.0,
        exploit_history=0,
        price_ratio=1.5,
        gas_price_gwei=80.0,
        target_gas_price_gwei=40.0,
        slippage_bps=20.0,
        pool_depth=500000.0,
    )
    optimizer = YieldOptimizer()
    plan = optimizer.rebalance_plan(
        10_000.0,
        [
            YieldVenue("aave", apr=0.05, liquidity=1_000_000.0),
            YieldVenue("compound", apr=0.04, liquidity=2_000_000.0),
            YieldVenue("uniswap", apr=0.08, liquidity=500_000.0),
        ],
    )

    assert 0.0 <= risk.smart_contract_score <= 1.0
    assert risk.impermanent_loss >= 0.0
    assert plan == {"uniswap": 10_000.0}
