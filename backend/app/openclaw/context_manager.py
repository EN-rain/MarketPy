"""Persistent context manager with rolling history, backup, and AES-256 encryption."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .logging import StructuredLogger
from .models import ConversationMessage, UserContext


def _derive_256_bit_key(raw: str) -> bytes:
    data = raw.encode("utf-8")
    if len(data) == 32:
        return data
    try:
        decoded = base64.urlsafe_b64decode(data + b"=" * ((4 - len(data) % 4) % 4))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass

    # Deterministic 32-byte derivation for convenience in local projects.
    import hashlib

    return hashlib.sha256(data).digest()


class Aes256Cipher:
    """AES-256-GCM helper for at-rest encryption."""

    def __init__(self, key_material: str):
        self._key = _derive_256_bit_key(key_material)
        self._aes = AESGCM(self._key)

    def encrypt(self, plaintext: bytes) -> str:
        nonce = os.urandom(12)
        ciphertext = self._aes.encrypt(nonce, plaintext, associated_data=None)
        bundle = nonce + ciphertext
        return base64.urlsafe_b64encode(bundle).decode("utf-8")

    def decrypt(self, token: str) -> bytes:
        bundle = base64.urlsafe_b64decode(token.encode("utf-8"))
        nonce, ciphertext = bundle[:12], bundle[12:]
        return self._aes.decrypt(nonce, ciphertext, associated_data=None)


class ContextManager:
    """Manages per-user conversational memory and persistent storage."""

    def __init__(
        self,
        *,
        data_dir: str = "data/openclaw",
        max_messages: int = 50,
        backup_interval_seconds: int = 300,
        encryption_key: str | None = None,
        logger: StructuredLogger | None = None,
        time_provider: Callable[[], datetime] | None = None,
    ):
        self._logger = logger or StructuredLogger("openclaw.context_manager")
        self._max_messages = max_messages
        self._backup_interval_seconds = backup_interval_seconds
        self._time_provider = time_provider or (lambda: datetime.now(UTC))

        self._data_dir = Path(data_dir)
        self._contexts_dir = self._data_dir / "contexts"
        self._preferences_dir = self._data_dir / "preferences"
        self._conditions_dir = self._data_dir / "conditions"
        self._backups_dir = self._data_dir / "backups"
        for directory in [
            self._contexts_dir,
            self._preferences_dir,
            self._conditions_dir,
            self._backups_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        self._contexts: dict[str, UserContext] = {}
        self._lock = asyncio.Lock()
        self._backup_task: asyncio.Task[None] | None = None
        self._cipher = Aes256Cipher(encryption_key) if encryption_key else None

    async def load_contexts_from_disk(self) -> None:
        async with self._lock:
            for file_path in self._contexts_dir.glob("*.json"):
                raw_text = file_path.read_text(encoding="utf-8")
                if self._cipher:
                    payload = json.loads(self._cipher.decrypt(raw_text).decode("utf-8"))
                else:
                    payload = json.loads(raw_text)
                context = UserContext.from_dict(payload)
                self._contexts[context.user_id] = context
            self._logger.info("Loaded contexts from disk", {"users": len(self._contexts)})

    async def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        async with self._lock:
            context = self._contexts.get(user_id) or UserContext(user_id=user_id)
            context.add_message(
                ConversationMessage(
                    role=role,
                    content=content,
                    user_id=user_id,
                    metadata=metadata or {},
                    timestamp=self._time_provider(),
                ),
                max_messages=self._max_messages,
            )
            self._contexts[user_id] = context
            await self._persist_context(user_id)

    async def get_context(self, user_id: str, max_messages: int = 50) -> UserContext:
        async with self._lock:
            context = self._contexts.get(user_id)
            if context is None:
                context = UserContext(user_id=user_id)
                self._contexts[user_id] = context
            if len(context.messages) > max_messages:
                context.messages = context.messages[-max_messages:]
            return context

    async def update_preferences(self, user_id: str, preferences: dict[str, Any]) -> None:
        async with self._lock:
            context = self._contexts.get(user_id) or UserContext(user_id=user_id)
            context.preferences.update(preferences)
            self._contexts[user_id] = context
            await self._persist_context(user_id)
            pref_path = self._preferences_dir / f"{user_id}.json"
            pref_path.write_text(
                json.dumps(context.preferences, ensure_ascii=True), encoding="utf-8"
            )

    async def clear_context(self, user_id: str) -> None:
        async with self._lock:
            self._contexts[user_id] = UserContext(user_id=user_id)
            await self._persist_context(user_id)

    async def _persist_context(self, user_id: str) -> None:
        context = self._contexts[user_id]
        payload = json.dumps(context.to_dict(), ensure_ascii=True, separators=(",", ":"))
        if self._cipher:
            output = self._cipher.encrypt(payload.encode("utf-8"))
        else:
            output = payload
        context_path = self._contexts_dir / f"{user_id}.json"
        context_path.write_text(output, encoding="utf-8")

    async def backup_contexts(self) -> Path:
        async with self._lock:
            snapshot = {user_id: context.to_dict() for user_id, context in self._contexts.items()}
        filename = f"context_backup_{self._time_provider().strftime('%Y%m%d_%H%M%S')}.json"
        path = self._backups_dir / filename
        raw = json.dumps(snapshot, ensure_ascii=True, indent=2)
        if self._cipher:
            path.write_text(self._cipher.encrypt(raw.encode("utf-8")), encoding="utf-8")
        else:
            path.write_text(raw, encoding="utf-8")
        self._logger.info("Context backup created", {"backup_file": str(path)})
        return path

    async def start_backup_loop(self) -> None:
        if self._backup_task and not self._backup_task.done():
            return
        self._backup_task = asyncio.create_task(self._backup_worker())

    async def stop_backup_loop(self) -> None:
        if self._backup_task is None:
            return
        self._backup_task.cancel()
        try:
            await self._backup_task
        except asyncio.CancelledError:
            pass
        self._backup_task = None

    async def _backup_worker(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._backup_interval_seconds)
                await self.backup_contexts()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error("Context backup failed", {"error": str(exc)})
