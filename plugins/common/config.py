"""Shared configuration helpers for Game Asset Database plugins.

The configuration file is a JSON document that stores the API base URL,
OAuth client identifiers, and plugin-specific overrides. The helpers in
this module intentionally avoid host application dependencies so that
they can be reused across Python environments (Maya, Blender, 3ds Max,
etc.).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_base_url": "https://game-asset-db.example.com/api",
    "username": "artist",
    "password": "changeme",
    "project_id": "",
    "cache_directory": "",
    "log_level": "INFO",
}

_CONFIG_ENV_VAR = "GAME_ASSET_DB_CONFIG"


def _platform_config_root() -> Path:
    """Return the default per-user configuration directory."""

    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "GameAssetDB"
        return Path.home() / "AppData" / "Roaming" / "GameAssetDB"

    xdg_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_home:
        return Path(xdg_home) / "game-asset-db"

    return Path.home() / ".config" / "game-asset-db"


def config_path() -> Path:
    """Resolve the path to the configuration JSON file."""

    override = os.getenv(_CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return _platform_config_root() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load the configuration dictionary, falling back to defaults."""

    path = config_path()
    if not path.exists():
        ensure_default_config()
        return DEFAULT_CONFIG.copy()

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    return merged


def ensure_default_config() -> Path:
    """Create a default configuration file if one is missing."""

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, indent=2)
    return path


def update_config(**overrides: Any) -> Dict[str, Any]:
    """Merge overrides into the stored configuration and persist them."""

    config = load_config()
    config.update(overrides)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    return config


def cache_directory() -> Path:
    """Return the filesystem path where plugins should store cached data."""

    config = load_config()
    cache_dir = config.get("cache_directory")
    if cache_dir:
        resolved = Path(cache_dir).expanduser()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    default_cache = _platform_config_root() / "cache"
    default_cache.mkdir(parents=True, exist_ok=True)
    return default_cache
