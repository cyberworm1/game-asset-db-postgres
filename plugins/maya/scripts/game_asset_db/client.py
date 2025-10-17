"""Maya-specific helpers for talking to the Game Asset Database."""

from __future__ import annotations

import logging

from plugins.common import GameAssetDbClient

LOGGER = logging.getLogger(__name__)


_client: GameAssetDbClient | None = None


def ensure_authenticated_client() -> GameAssetDbClient:
    """Return a cached REST client with a valid bearer token."""

    global _client
    if _client is None:
        _client = GameAssetDbClient()
        LOGGER.debug("Created new GameAssetDbClient for Maya plugin")

    _client.ensure_token()
    return _client


def publish_selection(metadata: dict[str, str]) -> dict[str, object]:
    """Publish the current Maya selection as a new asset version."""

    client = ensure_authenticated_client()
    result = client.publish_asset(metadata)
    LOGGER.info("Published asset with response: %%s", result)
    return result
