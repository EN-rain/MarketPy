"""API tests for health endpoints."""

from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app


def test_health_endpoints_exist():
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        paths = [
            "/api/health/connections",
            "/api/health/processing",
            "/api/health/memory",
            "/api/health/rate-limits",
            "/api/health/config",
            "/api/health/summary",
            "/api/data/health",
        ]
        for path in paths:
            resp = client.get(path)
            assert resp.status_code == 200
            assert isinstance(resp.json(), dict)


def test_cooldown_endpoint_without_engine():
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        resp = client.get("/api/cooldown/BTCUSDT")
        assert resp.status_code in (404, 503)


def test_exchange_client_health_degraded_on_runtime_error():
    class _BrokenExchangeClient:
        def get_rate_limit_info(self):
            raise RuntimeError("boom")

    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        app.state.exchange_client = _BrokenExchangeClient()
        resp = client.get("/api/health/exchange-client")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "degraded"
        assert "reason" in payload


def test_data_health_payload_shape():
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        resp = client.get("/api/data/health")
        assert resp.status_code == 200
        payload = resp.json()
        for key in (
            "total_markets",
            "active_markets",
            "total_records",
            "storage_size_gb",
            "data_quality_score",
            "datasets",
            "ingestion_status",
            "recent_errors",
        ):
            assert key in payload
