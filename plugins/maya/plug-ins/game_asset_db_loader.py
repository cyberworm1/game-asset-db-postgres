"""Maya plug-in entry point exposing commands for the Game Asset DB."""

from __future__ import annotations

import logging

from maya.api import OpenMaya  # type: ignore  # pragma: no cover - Maya import

from game_asset_db import show_asset_browser  # type: ignore

LOGGER = logging.getLogger(__name__)


class GameAssetDbCommand(OpenMaya.MPxCommand):  # type: ignore[misc]
    COMMAND_NAME = "gameAssetDb"

    def doIt(self, args):  # noqa: N802 - Maya naming convention
        LOGGER.info("Opening Game Asset DB browser")
        show_asset_browser()


def cmdCreator():  # noqa: N802 - Maya naming convention
    return GameAssetDbCommand


def initializePlugin(mobject):  # noqa: N802 - Maya naming convention
    plugin = OpenMaya.MFnPlugin(mobject, "Game Asset DB", "1.0", "Any")
    plugin.registerCommand(GameAssetDbCommand.COMMAND_NAME, cmdCreator)
    LOGGER.info("Registered Game Asset DB Maya command")


def uninitializePlugin(mobject):  # noqa: N802 - Maya naming convention
    plugin = OpenMaya.MFnPlugin(mobject)
    plugin.deregisterCommand(GameAssetDbCommand.COMMAND_NAME)
    LOGGER.info("Unregistered Game Asset DB Maya command")
