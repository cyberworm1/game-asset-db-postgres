"""Lightweight REST client used by Game Asset Database plugins."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from .config import load_config

LOGGER = logging.getLogger("game_asset_db.plugins")


@dataclass
class OAuthToken:
    """Simple representation of an OAuth token."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    obtained_at: float = time.time()

    @property
    def is_expired(self) -> bool:
        buffer_seconds = 60
        return time.time() >= self.obtained_at + self.expires_in - buffer_seconds


class GameAssetDbClient:
    """Minimal REST client that wraps urllib for plugin environments."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or load_config()
        self._token: Optional[OAuthToken] = None

    @property
    def api_base_url(self) -> str:
        return self._config["api_base_url"].rstrip("/")

    def set_token(self, token: OAuthToken) -> None:
        self._token = token

    def _request(self, method: str, path: str, *, data: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = f"{self.api_base_url}/{path.lstrip('/')}"
        payload: Optional[bytes] = None
        req_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
        if headers:
            req_headers.update(headers)
        if self._token and not self._token.is_expired:
            req_headers["Authorization"] = f"{self._token.token_type} {self._token.access_token}"

        request = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else ""
            LOGGER.error("Game Asset DB request failed: %s %s -> %s", method, url, exc.code)
            raise RuntimeError(f"Request failed ({exc.code}): {error_body}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - networking failure
            LOGGER.error("Game Asset DB request failed: %s %s -> %s", method, url, exc.reason)
            raise RuntimeError(f"Request failed: {exc.reason}") from exc

        if not body:
            return {}

        return json.loads(body)

    def list_assets(self, query: Optional[str] = None, tags: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if query:
            payload["query"] = query
        if tags:
            payload["tags"] = list(tags)
        LOGGER.debug("Fetching assets with payload: %s", payload)
        return self._request("GET", "/assets", data=payload if payload else None)

    def import_asset(self, asset_id: str) -> Dict[str, Any]:
        LOGGER.info("Importing asset %s", asset_id)
        return self._request("POST", f"/assets/{asset_id}/import")

    def publish_asset(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        LOGGER.info("Publishing asset with metadata keys: %s", list(metadata))
        return self._request("POST", "/assets", data=metadata)

    def refresh_token(self) -> OAuthToken:
        client_id = self._config.get("client_id")
        client_secret = self._config.get("client_secret")
        if not client_id or not client_secret:
            raise RuntimeError("Client credentials are required to obtain an OAuth token.")

        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        response = self._request("POST", "/oauth/token", data=payload)
        token = OAuthToken(
            access_token=response["access_token"],
            token_type=response.get("token_type", "Bearer"),
            expires_in=int(response.get("expires_in", 3600)),
            obtained_at=time.time(),
        )
        self._token = token
        return token
