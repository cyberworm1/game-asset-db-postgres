"""Lightweight REST client used by Game Asset Database plugins."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
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

    @property
    def project_id(self) -> str:
        return self._config.get("project_id", "")

    def set_token(self, token: OAuthToken) -> None:
        self._token = token

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.api_base_url}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"
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

    def list_assets(
        self,
        project_id: Optional[str] = None,
        query: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        target_project = project_id or self.project_id
        if not target_project:
            raise RuntimeError("A project_id is required to list assets.")
        params: Dict[str, Any] = {}
        if query:
            params["search"] = query
        if tags:
            params["tags"] = list(tags)
        LOGGER.debug("Fetching assets for project %s with params: %s", target_project, params)
        self.ensure_token()
        response = self._request("GET", f"/projects/{target_project}/assets", params=params or None)
        if isinstance(response, list):
            return {"items": response}
        return response

    def import_asset(self, asset_id: str) -> Dict[str, Any]:
        LOGGER.info("Fetching asset detail %s", asset_id)
        self.ensure_token()
        return self._request("GET", f"/assets/{asset_id}")

    def publish_asset(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        LOGGER.info("Publishing asset with metadata keys: %s", list(metadata))
        self.ensure_token()
        return self._request("POST", "/assets", data=metadata)

    def authenticate(self) -> OAuthToken:
        username = self._config.get("username")
        password = self._config.get("password")
        if not username or not password:
            raise RuntimeError("Username and password are required to obtain an access token.")

        payload = {"username": username, "password": password}
        response = self._request("POST", "/auth/token", data=payload)
        token = OAuthToken(
            access_token=response["access_token"],
            token_type=response.get("token_type", "bearer").capitalize(),
            expires_in=int(response.get("expires_in", 3600)),
            obtained_at=time.time(),
        )
        self._token = token
        return token

    def ensure_token(self) -> OAuthToken:
        if self._token and not self._token.is_expired:
            return self._token
        return self.authenticate()

    def list_branches(self, project_id: str) -> Dict[str, Any]:
        LOGGER.debug("Fetching branches for project %s", project_id)
        self.ensure_token()
        return self._request("GET", f"/projects/{project_id}/branches")

    def create_branch(self, project_id: str, name: str, description: str | None = None,
                      parent_branch_id: str | None = None) -> Dict[str, Any]:
        LOGGER.info("Creating branch %s for project %s", name, project_id)
        self.ensure_token()
        payload: Dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if parent_branch_id:
            payload["parent_branch_id"] = parent_branch_id
        return self._request("POST", f"/projects/{project_id}/branches", data=payload)

    def list_permissions(self, project_id: str) -> Dict[str, Any]:
        LOGGER.debug("Fetching permissions for project %s", project_id)
        self.ensure_token()
        return self._request("GET", f"/projects/{project_id}/permissions")

    def set_permission(
        self,
        project_id: str,
        user_id: str,
        *,
        asset_id: Optional[str] = None,
        read: bool = True,
        write: bool = False,
        delete: bool = False,
    ) -> Dict[str, Any]:
        LOGGER.info("Granting permissions for user %s on project %s", user_id, project_id)
        self.ensure_token()
        payload = {
            "project_id": project_id,
            "user_id": user_id,
            "asset_id": asset_id,
            "read": read,
            "write": write,
            "delete": delete,
        }
        return self._request("POST", f"/projects/{project_id}/permissions", data=payload)

    def create_shelf(self, workspace_id: str, asset_version_id: str, description: Optional[str] = None) -> Dict[str, Any]:
        LOGGER.info("Creating shelf for workspace %s", workspace_id)
        self.ensure_token()
        payload: Dict[str, Any] = {
            "workspace_id": workspace_id,
            "asset_version_id": asset_version_id,
        }
        if description:
            payload["description"] = description
        return self._request("POST", "/shelves", data=payload)
