"""Qt UI for browsing Game Asset Database assets inside Maya."""

from __future__ import annotations

import logging
from typing import List

from plugins.common import cache_directory
from .client import ensure_authenticated_client

LOGGER = logging.getLogger(__name__)


try:  # pragma: no cover - only executed inside Maya
    from PySide2 import QtWidgets
    import maya.OpenMayaUI as omui
    import shiboken2
except Exception:  # noqa: BLE001 - Maya environment may not be available during linting
    QtWidgets = None  # type: ignore[assignment]
    omui = None  # type: ignore[assignment]
    shiboken2 = None  # type: ignore[assignment]


class AssetBrowserDialog(QtWidgets.QDialog):  # type: ignore[misc]
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Game Asset Database")
        self.resize(480, 640)

        self.search_field = QtWidgets.QLineEdit(self)
        self.asset_list = QtWidgets.QListWidget(self)
        self.import_button = QtWidgets.QPushButton("Import", self)
        self.refresh_button = QtWidgets.QPushButton("Refresh", self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.search_field)
        layout.addWidget(self.asset_list)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.import_button)
        layout.addLayout(button_row)

        self.refresh_button.clicked.connect(self.refresh_assets)  # type: ignore[attr-defined]
        self.import_button.clicked.connect(self.import_selected_asset)  # type: ignore[attr-defined]

        self.refresh_assets()

    def refresh_assets(self) -> None:
        client = ensure_authenticated_client()
        query = self.search_field.text()  # type: ignore[union-attr]
        response = client.list_assets(query=query or None)
        items: List[dict] = response.get("items", [])
        self.asset_list.clear()  # type: ignore[union-attr]
        for item in items:
            display = f"{item.get('name')} (v{item.get('version')})"
            list_item = QtWidgets.QListWidgetItem(display)  # type: ignore[call-arg]
            list_item.setData(32, item.get("id"))
            self.asset_list.addItem(list_item)  # type: ignore[union-attr]
        LOGGER.debug("Loaded %s assets into Maya browser", len(items))

    def import_selected_asset(self) -> None:
        selected_items = self.asset_list.selectedItems()  # type: ignore[union-attr]
        if not selected_items:
            LOGGER.warning("No asset selected for import")
            return
        asset_id = selected_items[0].data(32)
        client = ensure_authenticated_client()
        payload = client.import_asset(asset_id)
        cache_directory()  # ensure cache exists for downloaded files
        LOGGER.info("Triggered Maya import for asset %s -> %s", asset_id, payload)


def maya_main_window():  # pragma: no cover - Maya specific
    if omui is None:
        raise RuntimeError("Maya UI modules unavailable")
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        raise RuntimeError("Unable to locate Maya main window")
    return shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)


def show_asset_browser() -> AssetBrowserDialog:
    if QtWidgets is None:
        raise RuntimeError("PySide2 is not available; launch from Maya")

    dialog = AssetBrowserDialog(parent=maya_main_window())
    dialog.show()
    dialog.raise_()
    return dialog
