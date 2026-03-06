"""Dynamic skill extension system for OpenClaw."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .kimi_k2_client import KimiK2Client
from .logging import StructuredLogger


class SkillProtocol(Protocol):
    name: str

    async def execute(self, params: dict[str, Any]) -> Any: ...


@dataclass(slots=True)
class LoadedSkill:
    name: str
    path: Path
    enabled: bool
    instance: SkillProtocol


class SkillExtensionSystem:
    """Discover, load, execute, create, and manage OpenClaw skills."""

    def __init__(
        self,
        skills_dir: str,
        *,
        kimi_client: KimiK2Client | None = None,
        logger: StructuredLogger | None = None,
    ):
        self._skills_dir = Path(skills_dir)
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._kimi_client = kimi_client
        self._logger = logger or StructuredLogger("openclaw.skill_system")
        self._skills: dict[str, LoadedSkill] = {}

    def discover(self) -> list[Path]:
        return sorted(
            path for path in self._skills_dir.glob("*.py") if not path.name.startswith("_")
        )

    def load_all(self) -> dict[str, LoadedSkill]:
        loaded: dict[str, LoadedSkill] = {}
        for path in self.discover():
            skill = self._load_skill(path)
            if skill:
                loaded[skill.name] = skill
        self._skills = loaded
        return dict(self._skills)

    def _load_skill(self, path: Path) -> LoadedSkill | None:
        module_name = f"openclaw_skill_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            self._logger.warning("Skipping invalid skill spec", {"path": str(path)})
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        skill_class = getattr(module, "Skill", None)
        if skill_class is None:
            self._logger.warning("Skipping skill without Skill class", {"path": str(path)})
            return None
        instance = skill_class()
        name = getattr(instance, "name", path.stem)
        return LoadedSkill(name=name, path=path, enabled=True, instance=instance)

    async def execute(self, skill_name: str, params: dict[str, Any]) -> Any:
        skill = self._skills.get(skill_name)
        if skill is None:
            raise KeyError(f"Skill not found: {skill_name}")
        if not skill.enabled:
            raise PermissionError(f"Skill is disabled: {skill_name}")
        return await skill.instance.execute(params)

    async def create_skill(self, skill_name: str, capability_description: str) -> Path:
        code = await self._generate_skill_code(skill_name, capability_description)
        path = self._skills_dir / f"{skill_name}.py"
        path.write_text(code, encoding="utf-8")
        manifest_path = self._skills_dir / f"{skill_name}.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "name": skill_name,
                    "description": capability_description,
                    "created_by": "openclaw",
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._logger.info("Skill created", {"skill_name": skill_name, "path": str(path)})
        self.load_all()
        return path

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {"name": skill.name, "enabled": skill.enabled, "path": str(skill.path)}
            for skill in sorted(self._skills.values(), key=lambda item: item.name)
        ]

    def set_enabled(self, skill_name: str, enabled: bool) -> None:
        skill = self._skills.get(skill_name)
        if skill is None:
            raise KeyError(f"Skill not found: {skill_name}")
        skill.enabled = enabled

    def remove_skill(self, skill_name: str) -> bool:
        skill = self._skills.pop(skill_name, None)
        if not skill:
            return False
        skill.path.unlink(missing_ok=True)
        json_path = skill.path.with_suffix(".json")
        json_path.unlink(missing_ok=True)
        return True

    async def _generate_skill_code(self, skill_name: str, capability_description: str) -> str:
        if self._kimi_client:
            prompt = (
                "Generate async Python skill module with class Skill containing "
                f"name='{skill_name}' and async execute(params: dict) -> dict. "
                f"Capability: {capability_description}. "
                "Return code only."
            )
            try:
                generated = await self._kimi_client.complete([{"role": "user", "content": prompt}])
                if "class Skill" in generated:
                    return generated
            except Exception as exc:
                self._logger.warning("Skill generation via Kimi failed", {"error": str(exc)})

        return (
            "from __future__ import annotations\n\n"
            "class Skill:\n"
            f'    name = "{skill_name}"\n\n'
            "    async def execute(self, params: dict) -> dict:\n"
            "        return {\n"
            '            "skill": self.name,\n'
            '            "status": "ok",\n'
            f'            "description": "{capability_description}",\n'
            '            "params": params,\n'
            "        }\n"
        )
