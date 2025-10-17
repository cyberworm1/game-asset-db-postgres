"""Maya module entry point for the Game Asset Database integration."""

from .client import ensure_authenticated_client
from .ui import show_asset_browser

__all__ = ["ensure_authenticated_client", "show_asset_browser"]
