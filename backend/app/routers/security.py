"""Security endpoints for JWT, RBAC checks, API keys, and monitoring."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.app.security.auth import get_current_user, require_role
from backend.app.security.input_validation import sanitize_text

router = APIRouter()


class TokenIssueRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    role: str = Field(default="viewer", pattern="^(viewer|trader|admin)$")
    bootstrap_token: str = Field(min_length=1, max_length=256)

    @field_validator("user_id")
    @classmethod
    def _clean_user_id(cls, value: str) -> str:
        return sanitize_text(value, max_length=64)


class StoreApiKeyRequest(BaseModel):
    exchange: str = Field(min_length=2, max_length=32)
    key_name: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=256)
    api_secret: str = Field(min_length=1, max_length=512)

    @field_validator("exchange", "key_name")
    @classmethod
    def _sanitize_text_fields(cls, value: str) -> str:
        return sanitize_text(value, max_length=64).lower()


@router.post("/security/token")
async def issue_token(request: Request, params: TokenIssueRequest):
    bootstrap = request.app.state.app_settings.security_bootstrap_token
    if not bootstrap or params.bootstrap_token != bootstrap:
        ip = request.client.host if request.client else "unknown"
        request.app.state.security_monitor.record_auth_attempt(ip=ip, user_id=params.user_id, success=False)
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")

    token = request.app.state.jwt_manager.issue_token(user_id=params.user_id, role=params.role)
    ip = request.client.host if request.client else "unknown"
    request.app.state.security_monitor.record_auth_attempt(ip=ip, user_id=params.user_id, success=True)
    return {"access_token": token, "token_type": "bearer", "role": params.role}


@router.get("/security/me")
async def get_me(request: Request):
    user = get_current_user(request)
    return {"user_id": user.user_id, "role": user.role, "expires_at": user.expires_at.isoformat()}


@router.post("/security/api-keys")
async def store_api_key(request: Request, params: StoreApiKeyRequest):
    user = get_current_user(request)
    require_role(user, {"admin"})
    key_id = f"key_{uuid4().hex[:16]}"
    request.app.state.api_key_store.save(
        key_id=key_id,
        exchange=params.exchange,
        key_name=params.key_name,
        api_key=params.api_key,
        api_secret=params.api_secret,
    )
    return {"id": key_id, "exchange": params.exchange, "key_name": params.key_name, "stored": True}


@router.get("/security/api-keys")
async def list_api_keys(request: Request):
    user = get_current_user(request)
    require_role(user, {"admin", "trader"})
    return {"items": request.app.state.api_key_store.list_masked()}


@router.get("/security/monitoring")
async def get_security_monitoring(request: Request):
    user = get_current_user(request)
    require_role(user, {"admin"})
    return request.app.state.security_monitor.summary()
