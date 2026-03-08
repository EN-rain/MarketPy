"""JWT auth, RBAC helpers, and encrypted API key management."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, status

from backend.app.models.config import settings
from backend.app.openclaw.context_manager import Aes256Cipher


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


@dataclass(frozen=True, slots=True)
class AuthUser:
    user_id: str
    role: str
    expires_at: datetime


class JWTManager:
    def __init__(self, secret: str, exp_minutes: int = 60) -> None:
        self.secret = secret.encode("utf-8")
        self.exp_minutes = exp_minutes

    def issue_token(self, user_id: str, role: str) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self.exp_minutes)).timestamp()),
        }
        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"

    def verify_token(self, token: str) -> AuthUser:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token") from exc

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected, actual):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
        if expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        return AuthUser(
            user_id=str(payload.get("sub", "")),
            role=str(payload.get("role", "viewer")).lower(),
            expires_at=expires_at,
        )


class APIKeyStore:
    """Encrypted API key storage in sqlite."""

    def __init__(self, db_path: str | Path = "data/security.sqlite", encryption_key: str | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._cipher = Aes256Cipher(encryption_key or settings.security_api_key_encryption_key)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exchange_api_keys (
                id TEXT PRIMARY KEY,
                exchange TEXT NOT NULL,
                key_name TEXT NOT NULL,
                encrypted_api_key TEXT NOT NULL,
                encrypted_api_secret TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_exchange_api_keys_exchange_name
            ON exchange_api_keys(exchange, key_name)
            """
        )
        self._conn.commit()

    def save(self, *, key_id: str, exchange: str, key_name: str, api_key: str, api_secret: str) -> None:
        encrypted_api_key = self._cipher.encrypt(api_key.encode("utf-8"))
        encrypted_api_secret = self._cipher.encrypt(api_secret.encode("utf-8"))
        self._conn.execute(
            """
            INSERT OR REPLACE INTO exchange_api_keys
            (id, exchange, key_name, encrypted_api_key, encrypted_api_secret, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                exchange.lower().strip(),
                key_name.strip(),
                encrypted_api_key,
                encrypted_api_secret,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def list_masked(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, exchange, key_name, created_at FROM exchange_api_keys ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_decrypted(self, key_id: str) -> dict[str, str]:
        row = self._conn.execute(
            """
            SELECT id, exchange, key_name, encrypted_api_key, encrypted_api_secret
            FROM exchange_api_keys WHERE id = ?
            """,
            (key_id,),
        ).fetchone()
        if row is None:
            raise KeyError(key_id)
        return {
            "id": str(row["id"]),
            "exchange": str(row["exchange"]),
            "key_name": str(row["key_name"]),
            "api_key": self._cipher.decrypt(str(row["encrypted_api_key"])).decode("utf-8"),
            "api_secret": self._cipher.decrypt(str(row["encrypted_api_secret"])).decode("utf-8"),
        }


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = header[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return token


def get_current_user(request: Request) -> AuthUser:
    token = _extract_bearer_token(request)
    manager: JWTManager = request.app.state.jwt_manager
    user = manager.verify_token(token)
    request.app.state.security_monitor.record_auth_attempt(
        ip=request.client.host if request.client else "unknown",
        user_id=user.user_id,
        success=True,
    )
    return user


def require_role(user: AuthUser, allowed_roles: set[str]) -> None:
    normalized = {role.lower() for role in allowed_roles}
    if user.role not in normalized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role permissions")
