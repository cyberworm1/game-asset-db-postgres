# Game Asset Database Unity Package

This Unity editor extension provides a dockable window for browsing and
importing assets from the Game Asset Database. It targets Unity 2020 LTS
and newer versions.

## Structure

```
plugins/unity/
├── package.json
├── README.md
└── Editor/
    ├── GameAssetDbWindow.cs
    └── GameAssetDb.asmdef
```

## Installation

1. Copy the `plugins/unity` folder into your Unity project's `Packages`
   directory or add it as a local package via the Package Manager.
2. Launch the **Window → Game Asset DB** panel and click **Refresh** to
   automatically scaffold a per-user config file at
   `%APPDATA%/GameAssetDB/config.json` (Windows) or `~/.config/game-asset-db/config.json`
   (macOS/Linux).
3. Edit the generated `config.json` and supply the following fields:
   - `api_base_url`: Base URL of the running FastAPI service.
   - `project_id`: UUID of the project to browse.
   - `username`/`password`: Studio credentials used for `/auth/token`.

Imported assets are written to `Assets/GameAssetDb/<AssetName>/asset.json` so
projects can version-control the retrieved metadata or trigger custom importers.

## Distribution

Publish the folder as a tarball or Git-based UPM package. Ensure the
`package.json` metadata is updated for each release.
