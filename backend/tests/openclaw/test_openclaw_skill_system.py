from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.openclaw.skill_system import SkillExtensionSystem


@pytest.mark.asyncio
async def test_skill_system_create_load_execute_remove(tmp_path: Path) -> None:
    system = SkillExtensionSystem(str(tmp_path))
    await system.create_skill("hello_skill", "Return greeting payload")
    loaded = system.load_all()
    assert "hello_skill" in loaded

    result = await system.execute("hello_skill", {"name": "Ada"})
    assert result["status"] == "ok"
    assert result["params"]["name"] == "Ada"

    listing = system.list_skills()
    assert listing and listing[0]["name"] == "hello_skill"
    system.set_enabled("hello_skill", False)
    with pytest.raises(PermissionError):
        await system.execute("hello_skill", {})
    assert system.remove_skill("hello_skill") is True
