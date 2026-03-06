from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.openclaw.context_manager import ContextManager


@pytest.mark.asyncio
async def test_context_manager_persists_messages(tmp_path: Path) -> None:
    manager = ContextManager(data_dir=str(tmp_path), max_messages=50)
    await manager.add_message("u1", "user", "hello")
    restored = await manager.get_context("u1")
    assert len(restored.messages) == 1
    assert restored.messages[0].content == "hello"


@pytest.mark.asyncio
async def test_context_manager_rolling_window(tmp_path: Path) -> None:
    manager = ContextManager(data_dir=str(tmp_path), max_messages=50)
    for index in range(55):
        await manager.add_message("u1", "user", f"m{index}")
    restored = await manager.get_context("u1")
    assert len(restored.messages) == 50
    assert restored.messages[0].content == "m5"


@pytest.mark.asyncio
async def test_context_manager_encryption_at_rest(tmp_path: Path) -> None:
    manager = ContextManager(data_dir=str(tmp_path), encryption_key="a-very-secret-key")
    await manager.add_message("u1", "user", "secret text")
    file_path = tmp_path / "contexts" / "u1.json"
    raw = file_path.read_text(encoding="utf-8")
    assert "secret text" not in raw

    reload_manager = ContextManager(data_dir=str(tmp_path), encryption_key="a-very-secret-key")
    await reload_manager.load_contexts_from_disk()
    context = await reload_manager.get_context("u1")
    assert context.messages[-1].content == "secret text"


@pytest.mark.asyncio
async def test_context_backup_creation(tmp_path: Path) -> None:
    manager = ContextManager(data_dir=str(tmp_path))
    await manager.add_message("u1", "user", "a")
    path = await manager.backup_contexts()
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["u1"]["user_id"] == "u1"
