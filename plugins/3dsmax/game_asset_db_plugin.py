"""Autodesk 3ds Max integration with the Game Asset Database."""

from __future__ import annotations

import json
import logging
from typing import Any

from pymxs import runtime as rt  # type: ignore  # pragma: no cover - requires 3ds Max

from plugins.common import GameAssetDbClient, cache_directory

LOGGER = logging.getLogger(__name__)


def show_asset_browser() -> None:
    dialog = rt.createDialog(rt.newRollout("gameAssetDbRollout", "Game Asset DB"), 400, 600)
    dialog.addControl(rt.createControl(rt.Name("editText"), "searchField", caption="Search"))
    dialog.addControl(rt.createControl(rt.Name("button"), "refreshButton", caption="Refresh"))
    dialog.addControl(rt.createControl(rt.Name("button"), "importButton", caption="Import"))
    dialog.addControl(rt.createControl(rt.Name("listBox"), "assetList"))

    def refresh_assets(*_args):
        client = GameAssetDbClient()
        try:
            payload = client.list_assets()
        except Exception as exc:  # noqa: BLE001 - display message box
            rt.messageBox(f"Failed to load assets: {exc}")
            return
        items = payload.get("items", [])
        display_items = []
        for asset in items:
            versions = asset.get("versions", []) or []
            latest_version = versions[-1]["version_number"] if versions else "-"
            display_items.append(f"{asset.get('name', 'Unnamed')} (v{latest_version})")
        dialog.assetList.items = display_items
        dialog.assetList.tag = json.dumps(items)
        LOGGER.info("Loaded assets into 3ds Max browser")

    def import_selected(*_args):
        index = dialog.assetList.selection - 1
        if index < 0:
            rt.messageBox("Select an asset to import")
            return
        items = json.loads(dialog.assetList.tag or "[]")
        asset = items[index]
        client = GameAssetDbClient()
        detail = client.import_asset(asset["id"])
        cache_dir = cache_directory()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{asset.get('name', asset['id'])}_metadata.json"
        cache_path.write_text(json.dumps(detail, indent=2, default=str), encoding="utf-8")
        LOGGER.info("Cached metadata for asset %s at %s", asset["id"], cache_path)

    dialog.refreshButton.pressed = refresh_assets
    dialog.importButton.pressed = import_selected
    refresh_assets()


def publish_selection(metadata: dict[str, Any]) -> dict[str, Any]:
    client = GameAssetDbClient()
    result = client.publish_asset(metadata)
    LOGGER.info("Published selection from 3ds Max -> %s", result)
    return result
