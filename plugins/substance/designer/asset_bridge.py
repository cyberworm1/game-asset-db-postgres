"""Automation Toolkit script for Substance 3D Designer integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from plugins.common import GameAssetDbClient, cache_directory

LOGGER = logging.getLogger(__name__)


def fetch_graphs(tag: str | None = None) -> list[dict[str, Any]]:
    client = GameAssetDbClient()
    payload = client.list_assets(tags=[tag] if tag else None)
    return payload.get("items", [])


def export_graph(graph_id: str, output_path: str) -> None:
    client = GameAssetDbClient()
    response = client.import_asset(graph_id)
    Path(output_path).write_text(json.dumps(response, indent=2), encoding="utf-8")
    LOGGER.info("Exported graph metadata for %s", graph_id)


def publish_graph(metadata: dict[str, Any]) -> dict[str, Any]:
    client = GameAssetDbClient()
    result = client.publish_asset(metadata)
    LOGGER.info("Published Designer graph %s", metadata.get("name"))
    return result


def cache_graph_library() -> Path:
    graphs = fetch_graphs(tag="designer")
    cache_dir = cache_directory()
    library = cache_dir / "designer_graphs.json"
    library.write_text(json.dumps(graphs, indent=2), encoding="utf-8")
    LOGGER.info("Cached %s Designer graphs", len(graphs))
    return library
