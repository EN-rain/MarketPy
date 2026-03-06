"""Property tests for CoinDesk BPI integration.

Validates:
- Property 17: Correlation Calculation Correctness
- Property 13: Periodic Update Interval Compliance (15-minute updates)
- Property 15: Historical Data Persistence
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.bpi_service import BPIService
from backend.app.integrations.coindesk_client import CoinDeskClient


@dataclass
class MutableClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


# Property 17: Correlation Calculation Correctness
@given(
    series_x=st.lists(
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=40,
    ),
    series_y=st.lists(
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=40,
    ),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_correlation_calculation_correctness(
    series_x: list[float], series_y: list[float]
) -> None:
    n = min(len(series_x), len(series_y))
    corr = CoinDeskClient._pearson(series_x[:n], series_y[:n])  # noqa: SLF001
    assert -1.0 <= corr <= 1.0


# Property 13: Periodic Update Interval Compliance
@given(
    under_interval=st.floats(min_value=0.0, max_value=899.0, allow_nan=False, allow_infinity=False),
    over_interval=st.floats(
        min_value=900.0, max_value=1800.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_bpi_periodic_update_interval_compliance(
    under_interval: float, over_interval: float
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "bpi": {
                    "USD": {"rate_float": 50000.0},
                    "EUR": {"rate_float": 45000.0},
                    "GBP": {"rate_float": 40000.0},
                }
            },
        )

    clock = MutableClock()
    client = CoinDeskClient(transport=httpx.MockTransport(handler))
    service = BPIService(client, now_fn=clock.now, update_interval_seconds=900.0)
    try:
        assert await service.update_if_due() is True
        first_len = len(client._history)  # noqa: SLF001

        clock.advance(under_interval)
        assert await service.update_if_due() is False
        assert len(client._history) == first_len  # noqa: SLF001

        clock.advance(over_interval)
        assert await service.update_if_due() is True
        assert len(client._history) == first_len + 1  # noqa: SLF001
    finally:
        await client.close()


# Property 15: Historical Data Persistence
@given(sample_count=st.integers(min_value=1, max_value=50))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_bpi_historical_data_persistence(sample_count: int) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "bpi": {
                    "USD": {"rate_float": 50000.0},
                    "EUR": {"rate_float": 45000.0},
                    "GBP": {"rate_float": 40000.0},
                }
            },
        )

    client = CoinDeskClient(transport=httpx.MockTransport(handler))
    try:
        for _ in range(sample_count):
            await client.get_bpi(["USD", "EUR", "GBP"])
    finally:
        await client.close()

    assert len(client._history) == sample_count  # noqa: SLF001
