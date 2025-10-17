# Game Asset Database Maya Plugin

This Maya module provides dockable UI panels and commands for browsing,
importing, and publishing assets via the Game Asset Database REST API.

## Structure

```
plugins/maya/
├── module.mel            # Maya module descriptor
├── plug-ins/
│   └── game_asset_db_loader.py
├── scripts/
│   └── game_asset_db/
│       ├── __init__.py
│       ├── client.py
│       └── ui.py
└── icons/
    └── (icon assets go here)
```

## Installation

1. Copy the `plugins/maya` directory to a location on Maya's module path.
2. Add the folder to `MAYA_MODULE_PATH` or place `module.mel` in one of the
   standard module directories.
3. Launch Maya and enable the "Game Asset DB" module from the Plug-in
   Manager. A "Game Asset DB" shelf and menu item will be created on load.

## Packaging

Use Autodesk's `mayapkg` or internal installer scripts to bundle the module
for Windows, macOS, and Linux distributions.
