"""Shared helpers for loading environment-aware YAML configuration."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_ENVIRONMENT = "dev"
ENVIRONMENT_VARIABLE = "MARKETPY_ENV"
CONFIG_DIR = Path("config")


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a dictionary."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return payload


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge nested dictionaries without mutating inputs."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_environment_name(environment: str | None = None) -> str:
    """Resolve the active MarketPy configuration environment."""
    return environment or os.getenv(ENVIRONMENT_VARIABLE, DEFAULT_ENVIRONMENT)


def load_environment_config(
    environment: str | None = None,
    *,
    config_dir: str | Path = CONFIG_DIR,
) -> dict[str, Any]:
    """Load shared plus environment-specific YAML configuration."""
    env_name = resolve_environment_name(environment)
    config_root = Path(config_dir)
    base_config = load_yaml_config(config_root / f"{env_name}.yaml")
    exchanges_path = config_root / "exchanges.yaml"
    if exchanges_path.exists():
        base_config = deep_merge(base_config, {"exchanges": load_yaml_config(exchanges_path)})
    base_config.setdefault("environment", env_name)
    return base_config
