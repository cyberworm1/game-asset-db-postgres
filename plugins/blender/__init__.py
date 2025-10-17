"""Blender add-on integrating with the Game Asset Database."""

bl_info = {
    "name": "Game Asset Database",
    "author": "Game Asset DB Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Game Asset DB",
    "description": "Browse and publish assets to the Game Asset Database",
    "category": "Import-Export",
}

import json
import logging
from typing import Any

import bpy  # type: ignore

from plugins.common import GameAssetDbClient, load_config, update_config

LOGGER = logging.getLogger(__name__)


class GameAssetDbSettings(bpy.types.AddonPreferences):  # type: ignore[misc]
    bl_idname = __name__

    api_base_url: bpy.props.StringProperty(  # type: ignore[assignment]
        name="API Base URL",
        description="Base URL for the Game Asset Database API",
        default=load_config().get("api_base_url", "https://game-asset-db.example.com/api"),
    )

    project_id: bpy.props.StringProperty(  # type: ignore[assignment]
        name="Project ID",
        description="UUID of the project to browse",
        default=load_config().get("project_id", ""),
    )

    username: bpy.props.StringProperty(  # type: ignore[assignment]
        name="Username",
        description="Service account or artist username",
        default=load_config().get("username", ""),
    )

    password: bpy.props.StringProperty(  # type: ignore[assignment]
        name="Password",
        description="Password used for /auth/token",
        subtype="PASSWORD",
        default=load_config().get("password", ""),
    )

    def draw(self, context):  # noqa: D401 - Blender override
        layout = self.layout
        layout.prop(self, "api_base_url")
        layout.prop(self, "project_id")
        layout.prop(self, "username")
        layout.prop(self, "password")

    def update_config(self) -> None:
        update_config(
            api_base_url=self.api_base_url,
            project_id=self.project_id,
            username=self.username,
            password=self.password,
        )


class GAME_ASSET_DB_OT_refresh(bpy.types.Operator):  # type: ignore[misc]
    bl_idname = "game_asset_db.refresh"
    bl_label = "Refresh Assets"

    def execute(self, context):  # noqa: D401 - Blender override
        config = load_config()
        project_id = config.get("project_id")
        if not project_id:
            self.report({'ERROR'}, "Set project_id in the Game Asset DB add-on preferences.")
            return {'CANCELLED'}

        client = GameAssetDbClient(config)
        try:
            payload = client.list_assets(project_id=project_id)
            items = payload.get("items", [])
        except Exception as exc:  # noqa: BLE001 - user feedback
            self.report({'ERROR'}, f"Failed to load assets: {exc}")
            return {'CANCELLED'}
        collection = context.scene.game_asset_db_assets
        collection.clear()
        for asset in items:
            versions = asset.get("versions", []) or []
            latest_version = versions[-1]["version_number"] if versions else "-"
            item = collection.add()
            item.asset_id = asset.get("id", "")
            item.asset_name = asset.get("name", "Unnamed")
            item.asset_type = asset.get("type", "Unknown")
            item.version = str(latest_version)
        LOGGER.info("Loaded %s assets into Blender panel", len(items))
        return {'FINISHED'}


class GAME_ASSET_DB_OT_import(bpy.types.Operator):  # type: ignore[misc]
    bl_idname = "game_asset_db.import"
    bl_label = "Import Selected Asset"

    def execute(self, context):
        selection = context.scene.game_asset_db_assets
        if not selection:
            self.report({'WARNING'}, "No assets available to import")
            return {'CANCELLED'}
        active = selection[selection.active_index]
        config = load_config()
        project_id = config.get("project_id")
        if not project_id:
            self.report({'ERROR'}, "Set project_id in the Game Asset DB add-on preferences.")
            return {'CANCELLED'}

        client = GameAssetDbClient(config)
        try:
            detail = client.import_asset(active.asset_id)
        except Exception as exc:  # noqa: BLE001 - user feedback
            self.report({'ERROR'}, f"Import failed: {exc}")
            return {'CANCELLED'}
        text_name = f"Asset_{active.asset_name or active.asset_id}"[:64]
        if text_name in bpy.data.texts:
            text_block = bpy.data.texts[text_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(text_name)
        text_block.write(json.dumps(detail, indent=2, default=str))
        self.report({'INFO'}, f"Imported metadata for {active.asset_name}")
        LOGGER.info("Imported metadata for asset %s", active.asset_id)
        return {'FINISHED'}


class GameAssetDbAssetItem(bpy.types.PropertyGroup):  # type: ignore[misc]
    asset_id: bpy.props.StringProperty(name="Asset ID")  # type: ignore[assignment]
    asset_name: bpy.props.StringProperty(name="Name")  # type: ignore[assignment]
    asset_type: bpy.props.StringProperty(name="Type")  # type: ignore[assignment]
    version: bpy.props.StringProperty(name="Version")  # type: ignore[assignment]


class GAME_ASSET_DB_UL_asset_list(bpy.types.UIList):  # type: ignore[misc]
    def draw_item(self, _context, layout, _data, item, _icon, _active_data, _active_propname):
        layout.label(text=f"{item.asset_name} (v{item.version}) — {item.asset_type}")


class GAME_ASSET_DB_PT_panel(bpy.types.Panel):  # type: ignore[misc]
    bl_label = "Game Asset Database"
    bl_idname = "GAME_ASSET_DB_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Game Asset DB'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.template_list(
            "GAME_ASSET_DB_UL_asset_list",
            "asset_list",
            scene,
            "game_asset_db_assets",
            scene,
            "game_asset_db_assets_index",
        )
        col = row.column()
        col.operator(GAME_ASSET_DB_OT_refresh.bl_idname, text="Refresh")
        col.operator(GAME_ASSET_DB_OT_import.bl_idname, text="Import")


CLASSES = (
    GameAssetDbSettings,
    GameAssetDbAssetItem,
    GAME_ASSET_DB_OT_refresh,
    GAME_ASSET_DB_OT_import,
    GAME_ASSET_DB_UL_asset_list,
    GAME_ASSET_DB_PT_panel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.game_asset_db_assets = bpy.props.CollectionProperty(type=GameAssetDbAssetItem)  # type: ignore[assignment]
    bpy.types.Scene.game_asset_db_assets_index = bpy.props.IntProperty(default=0)  # type: ignore[assignment]
    LOGGER.info("Registered Game Asset DB Blender add-on")


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.game_asset_db_assets
    del bpy.types.Scene.game_asset_db_assets_index
    LOGGER.info("Unregistered Game Asset DB Blender add-on")
