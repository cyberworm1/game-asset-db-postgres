"""Substance 3D Painter plugin entry point for Game Asset Database."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import substance_painter  # type: ignore  # pragma: no cover - requires Painter
import substance_painter.events  # type: ignore
import substance_painter.projects  # type: ignore
import substance_painter.ui  # type: ignore

from plugins.common import GameAssetDbClient, cache_directory

LOGGER = logging.getLogger(__name__)


def start_plugin() -> None:
    LOGGER.info("Starting Game Asset DB plugin for Substance Painter")
    toolbar = substance_painter.ui.add_toolbar("Game Asset DB")
    toolbar.add_action("Sync Materials", sync_materials)
    toolbar.add_action("Publish Texture Set", publish_texture_set)


def close_plugin() -> None:
    LOGGER.info("Stopping Game Asset DB plugin for Substance Painter")
    substance_painter.ui.remove_toolbar("Game Asset DB")


def sync_materials() -> None:
    client = GameAssetDbClient()
    try:
        payload = client.list_assets(tags=["material"])
    except Exception as exc:  # noqa: BLE001 - Painter UI feedback
        substance_painter.ui.log_error(f"Failed to fetch materials: {exc}")
        return

    materials = payload.get("items", [])
    cache_dir = cache_directory()
    manifest = Path(cache_dir) / "painter_materials.json"
    manifest.write_text(json.dumps(materials, indent=2), encoding="utf-8")
    substance_painter.ui.log_info(f"Cached {len(materials)} materials for Painter")


def publish_texture_set() -> None:
    project = substance_painter.projects.current_project()
    if project is None:
        substance_painter.ui.log_error("No project open")
        return

    export_path = cache_directory() / "painter_exports"
    export_path.mkdir(parents=True, exist_ok=True)
    export_file = export_path / f"{project.metadata().get('name', 'texture_set')}.zip"
    project.export_textures(str(export_file))

    client = GameAssetDbClient()
    metadata: dict[str, Any] = {
        "name": project.metadata().get("name", "Texture Set"),
        "type": "material",
        "files": [str(export_file)],
    }
    client.publish_asset(metadata)
    substance_painter.ui.log_info(f"Published texture set to Game Asset DB: {export_file}")
