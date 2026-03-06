"""Tests for the FastAPI endpoints."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest
from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app
from backend.app.models.config import settings
from backend.app.routers.backtest import MAX_MARKETS_PER_REQUEST


@pytest.fixture
def client():
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


class TestStatusEndpoint:
    def test_get_status(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert "is_running" in data
        assert "connected_markets" in data


class TestPortfolioEndpoint:
    def test_get_portfolio(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "cash" in data
        assert "total_equity" in data
        assert "positions" in data


class TestMarketEndpoint:
    def test_market_not_found(self, client):
        resp = client.get("/api/market/nonexistent-id")
        assert resp.status_code == 404

    def test_list_markets_empty(self, client):
        resp = client.get("/api/markets")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert {"market_id", "question", "mid"}.issubset(data[0].keys())


class TestTradesEndpoint:
    def test_get_trades_empty(self, client):
        resp = client.get("/api/trades")
        assert resp.status_code == 200
        assert resp.json() == []


class TestSignalsEndpoint:
    def test_signals_not_found(self, client):
        resp = client.get("/api/signals/nonexistent-id")
        assert resp.status_code == 404


class TestBacktestEndpoint:
    def test_backtest_request(self, client, tmp_path):
        data_dir = tmp_path / "data"
        market_dir = data_dir / "parquet" / "market_id=test-market"
        market_dir.mkdir(parents=True, exist_ok=True)

        start = datetime(2025, 1, 1, tzinfo=UTC)
        rows = []
        for i in range(60):
            ts = start + timedelta(minutes=5 * i)
            mid = 0.5 + (i * 0.001)
            rows.append(
                {
                    "timestamp": ts,
                    "token_id": "test-market",
                    "open": mid,
                    "high": mid + 0.01,
                    "low": mid - 0.01,
                    "close": mid,
                    "bid": mid - 0.005,
                    "ask": mid + 0.005,
                    "mid": mid,
                    "spread": 0.01,
                    "volume": 100.0,
                    "trade_count": 10,
                }
            )
        pl.DataFrame(rows).write_parquet(market_dir / "bars.parquet")
        old_data_dir = settings.data_dir
        settings.data_dir = str(data_dir)
        try:
            resp = client.post(
                "/api/backtest/run",
                json={
                    "market_ids": ["test-market"],
                    "strategy": "momentum",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "total_pnl" in data
            assert "total_pnl_pct" in data
            assert data["total_pnl"] == pytest.approx((data["total_pnl_pct"] / 100.0) * 10000.0)
            assert "trades" in data
            assert "diagnostics" in data
        finally:
            settings.data_dir = old_data_dir

    def test_backtest_capabilities_endpoint(self, client):
        resp = client.get("/api/backtest/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "strategies" in data
        assert "momentum" in data["strategies"]
        assert "execution_modes" in data
        assert "event_driven" in data["execution_modes"]
        assert data["constraints"]["max_markets_per_request"] >= 1

    def test_backtest_api_key_enforced_when_configured(self, client):
        old_key = settings.backtest_api_key
        settings.backtest_api_key = "secret-key"
        try:
            unauthorized = client.post(
                "/api/backtest/run",
                json={"market_ids": ["missing-market"], "strategy": "momentum"},
            )
            assert unauthorized.status_code == 401

            wrong_key = client.post(
                "/api/backtest/run",
                headers={"x-api-key": "wrong-key"},
                json={"market_ids": ["missing-market"], "strategy": "momentum"},
            )
            assert wrong_key.status_code == 401
        finally:
            settings.backtest_api_key = old_key

    def test_backtest_market_count_validation(self, client):
        too_many_markets = [f"m{i}" for i in range(MAX_MARKETS_PER_REQUEST + 1)]
        resp = client.post(
            "/api/backtest/run",
            json={"market_ids": too_many_markets, "strategy": "momentum"},
        )
        assert resp.status_code == 422

    def test_backtest_rate_limit_status_endpoint(self, client):
        old_limit = settings.backtest_rate_limit_per_minute
        settings.backtest_rate_limit_per_minute = 50
        try:
            status = client.get("/api/backtest/rate-limit-status")
            assert status.status_code == 200
            payload = status.json()
            assert payload["limit"] == 50
            assert "used" in payload
            assert "remaining" in payload
            assert payload["window_seconds"] == 60
        finally:
            settings.backtest_rate_limit_per_minute = old_limit
