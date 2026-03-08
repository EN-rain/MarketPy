"""Phase 22 monitoring dashboard and websocket channel tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app


def test_monitoring_dashboard_endpoints() -> None:
    app = create_app(AppConfig(enable_binance_stream=False))
    with TestClient(app) as client:
        dashboard = client.get("/api/monitoring/dashboard")
        assert dashboard.status_code == 200
        payload = dashboard.json()
        assert "system_health" in payload
        assert "active_alerts" in payload
        assert "dashboard_panels" in payload
        assert "model_management" in payload["dashboard_panels"]
        assert "feature_store" in payload["dashboard_panels"]
        assert "pattern_detection" in payload["dashboard_panels"]
        assert "risk_dashboard" in payload["dashboard_panels"]
        assert "execution_quality" in payload["dashboard_panels"]
        assert "regime_classification" in payload["dashboard_panels"]
        assert "multi_exchange" in payload["dashboard_panels"]
        assert "explainability" in payload["dashboard_panels"]

        health = client.get("/api/monitoring/system-health")
        assert health.status_code == 200
        assert "status" in health.json()

        alerts = client.get("/api/monitoring/alerts")
        assert alerts.status_code == 200
        assert "items" in alerts.json()


def test_websocket_channel_subscription_protocol() -> None:
    app = create_app(AppConfig(enable_binance_stream=False))
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"

            websocket.send_json({"type": "subscribe_channels", "channels": ["predictions", "risk", "alerts"]})
            subscribed = websocket.receive_json()
            assert subscribed["type"] == "subscribed_channels"
            assert "predictions" in subscribed["data"]["channels"]
            assert "risk" in subscribed["data"]["channels"]
            assert "alerts" in subscribed["data"]["channels"]

            websocket.send_json({"type": "get_status"})
            status = websocket.receive_json()
            assert status["type"] == "status_update"

            websocket.send_json({"type": "unsubscribe_channels", "channels": ["risk"]})
            unsubscribed = websocket.receive_json()
            assert unsubscribed["type"] == "unsubscribed_channels"
            assert "risk" in unsubscribed["data"]["channels"]
