"""Phase 17 derivatives tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.execution.derivatives import DerivativesEngine
from backend.ingest.exchanges.base import MarginAccount, OptionContract, PerpetualPosition
from backend.ingest.exchanges.bybit import BybitAdapter
from backend.ingest.exchanges.okx import OKXAdapter
from backend.risk.derivatives_risk import DerivativesRiskManager


class _FakeRestClient:
    def __init__(self, responses: dict[tuple[str, str], object]) -> None:
        self.responses = responses

    async def get(self, path: str, params=None):
        key = (path, str(sorted((params or {}).items())))
        return self.responses[key]


@pytest.mark.property_test
@settings(max_examples=40)
@given(
    spot=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    strike=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    vol=st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
    time_to_expiry=st.floats(min_value=0.05, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_option_pricing_and_greeks_are_finite(spot: float, strike: float, vol: float, time_to_expiry: float) -> None:
    engine = DerivativesEngine()
    call = engine.black_scholes(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        rate=0.02,
        volatility=vol,
        option_type="call",
    )
    greeks = engine.greeks(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        rate=0.02,
        volatility=vol,
        option_type="call",
    )
    assert call >= 0.0
    assert -1.0 <= greeks["delta"] <= 1.0
    assert greeks["gamma"] >= 0.0
    assert greeks["vega"] >= 0.0


@pytest.mark.asyncio
async def test_bybit_and_okx_support_perpetuals_and_options() -> None:
    bybit = BybitAdapter(
        rest_client=_FakeRestClient(
            {
                ("/v5/market/funding/history", "[('category', 'linear'), ('symbol', 'BTCUSDT')]"): {
                    "result": {"list": [{"fundingRate": "0.0001"}]}
                },
                ("/v5/position/list", "[('category', 'linear')]"): {
                    "result": {
                        "list": [
                            {
                                "symbol": "BTCUSDT",
                                "side": "Buy",
                                "size": "2",
                                "avgPrice": "100",
                                "markPrice": "101",
                                "leverage": "5",
                                "unrealisedPnl": "2",
                                "positionIM": "20",
                                "positionBalance": "50",
                                "cumRealisedPnl": "0.0001",
                            }
                        ]
                    }
                },
                ("/v5/account/wallet-balance", "[('accountType', 'UNIFIED')]"): {
                    "result": {
                        "list": [
                            {
                                "totalEquity": "1000",
                                "totalMaintenanceMargin": "100",
                                "totalInitialMargin": "200",
                                "totalAvailableBalance": "800",
                            }
                        ]
                    }
                },
                ("/v5/market/instruments-info", "[('baseCoin', 'BTC'), ('category', 'option')]"): {
                    "result": {"list": [{"symbol": "BTC-30DEC26-50000-C", "markPrice": "1200", "markIv": "0.6"}]}
                },
            }
        )
    )
    okx = OKXAdapter(
        rest_client=_FakeRestClient(
            {
                ("/api/v5/public/funding-rate", "[('instId', 'BTC-USDT-SWAP')]"): {"data": [{"fundingRate": "0.0002"}]},
                ("/api/v5/account/positions", "[('instType', 'SWAP')]"): {
                    "data": [
                        {
                            "instId": "BTC-USDT-SWAP",
                            "pos": "1",
                            "avgPx": "100",
                            "markPx": "102",
                            "lever": "4",
                            "upl": "2",
                            "mmr": "40",
                            "margin": "80",
                            "fundingFee": "0.0002",
                        }
                    ]
                },
                ("/api/v5/account/balance", "[]"): {"data": [{"totalEq": "500", "mmr": "50", "imr": "100", "adjEq": "400"}]},
                ("/api/v5/public/instruments", "[('instType', 'OPTION'), ('uly', 'BTC-USD')]"): {
                    "data": [{"instId": "BTC-USD-261230-50000-C", "stk": "50000", "expTime": "1798588800000", "optType": "C", "markPx": "1500", "markVol": "0.7"}]
                },
            }
        ),
        instrument_type="SWAP",
    )

    assert (await bybit.get_funding_rates(["BTCUSDT"]))["BTCUSDT"] == pytest.approx(0.0001)
    assert (await okx.get_funding_rates(["BTC-USDT-SWAP"]))["BTC-USDT-SWAP"] == pytest.approx(0.0002)
    assert len(await bybit.get_perpetual_positions()) == 1
    assert len(await okx.get_perpetual_positions()) == 1
    assert (await bybit.get_margin_account()).margin_ratio == pytest.approx(10.0)
    assert (await okx.get_margin_account()).margin_ratio == pytest.approx(10.0)
    assert len(await bybit.get_option_chain("BTC")) == 1
    assert len(await okx.get_option_chain("BTC-USD")) == 1


def test_derivatives_risk_triggers_position_reduction_below_margin_threshold() -> None:
    manager = DerivativesRiskManager()
    account = MarginAccount(equity=100.0, used_margin=80.0, free_margin=20.0, margin_ratio=1.1, maintenance_margin=90.0)
    position = PerpetualPosition(
        symbol="BTCUSDT",
        side="long",
        quantity=1.0,
        entry_price=100.0,
        mark_price=95.0,
        leverage=5.0,
        unrealized_pnl=-5.0,
        maintenance_margin=90.0,
        notional_value=95.0,
    )
    snapshot = manager.snapshot(account, position)
    assert snapshot.requires_reduction is True
    assert snapshot.reduction_factor < 1.0
