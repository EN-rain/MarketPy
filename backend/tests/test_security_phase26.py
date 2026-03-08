"""Phase 26 security hardening tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app
from backend.app.models.config import settings
from backend.app.security.auth import APIKeyStore, JWTManager
from backend.app.security.monitoring import SecurityMonitor
from backend.app.security.rate_limit import HttpRateLimiter


def test_jwt_issue_verify_and_rbac_path() -> None:
    manager = JWTManager(secret="test-secret", exp_minutes=5)
    token = manager.issue_token("alice", "admin")
    user = manager.verify_token(token)
    assert user.user_id == "alice"
    assert user.role == "admin"


def test_api_key_store_encrypts_and_decrypts(tmp_path) -> None:
    store = APIKeyStore(db_path=tmp_path / "security.sqlite", encryption_key="unit-test-key")
    store.save(
        key_id="k1",
        exchange="binance",
        key_name="main",
        api_key="api-key-value",
        api_secret="secret-value",
    )
    items = store.list_masked()
    assert len(items) == 1
    payload = store.get_decrypted("k1")
    assert payload["api_key"] == "api-key-value"
    assert payload["api_secret"] == "secret-value"


def test_security_monitor_blocks_after_failed_auth_attempts() -> None:
    monitor = SecurityMonitor(failed_auth_threshold=3, block_duration_seconds=60)
    for _ in range(3):
        monitor.record_auth_attempt(ip="1.2.3.4", user_id="alice", success=False)
    assert monitor.is_blocked("1.2.3.4") is True


def test_http_rate_limiter_token_bucket() -> None:
    limiter = HttpRateLimiter(rate_per_sec=1.0, burst_size=2)
    assert limiter.allow("user") is True
    assert limiter.allow("user") is True
    assert limiter.allow("user") is False


def test_https_and_security_headers_available() -> None:
    original = settings.security_require_https
    settings.security_require_https = True
    app = create_app(AppConfig(enable_binance_stream=False))
    try:
        with TestClient(app) as client:
            response = client.get("/health", headers={"x-forwarded-proto": "https"})
            assert response.status_code == 200
            assert response.headers.get("strict-transport-security") is not None
    finally:
        settings.security_require_https = original
