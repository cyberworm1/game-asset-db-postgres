# Plugin Development Guide

The repository now ships with working reference plugins (Unity editor package plus language-agnostic REST client) that authenticate against the service and interact with the expanded API surface. This guide outlines how to build additional DCC integrations that match Helix parity while reusing the shared components provided here.

## Common Requirements

All plugins should share the following traits:

- **Language preference:** Python where possible. For tools without Python SDK access (primarily some Windows-only hosts), use the vendor-recommended language or bridge technology.
- **Transport:** Communicate with the Game Asset Database via the REST API (preferred) or GraphQL endpoints once available.
- **Authentication:** Use the shared REST client in `plugins/common` or mirror its `/auth/token` workflow directly within your host.
- **Configuration:** Store host-agnostic settings (API base URL, client ID, cache directory) in a per-user config file under the host application's standard preferences location.
- **Logging:** Write structured logs to the host application's logging facility, with an option to forward diagnostic bundles to the central ops team.
- **Packaging:** Provide signed installers or extension bundles for Windows, macOS, and Linux when the host application supports the platform.

### REST Endpoints Ready for Plugins

The FastAPI service exposes the endpoints below. All routes require bearer authentication via `/auth/token`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/token` | Retrieve a bearer token using studio credentials. |
| `GET` | `/projects/{project_id}/assets` | List accessible assets plus their versions (RLS enforced). |
| `GET` | `/projects` | List projects visible to the caller (optionally including archived records). |
| `POST` | `/projects` | Provision a project (admin only). |
| `PATCH` | `/projects/{project_id}` | Update metadata, storage quotas, or archive state (admin only). |
| `GET` | `/projects/{project_id}/assets` | List accessible assets plus their versions (RLS enforced). |
| `GET` | `/assets/{asset_id}` | Retrieve full asset metadata and version history. |
| `POST` | `/assets` | Create a new asset record. |
| `POST` | `/assets/{asset_id}/versions/upload` | Upload a binary payload, automatically storing to the depot volume and creating a new version. |
| `GET` | `/reviews/pending` | Fetch pending reviews for dashboards or DCC overlays. |
| `PATCH` | `/reviews/{review_id}` | Update review status/comments from tool UIs. |
| `POST` | `/locks` | Claim an asset lock for binary editing workflows. |
| `DELETE` | `/locks/{asset_id}` | Release an existing lock (admins can override any lock). |
| `GET` | `/projects/{project_id}/branches` | Enumerate streams/branches for workspace targeting. |
| `POST` | `/projects/{project_id}/branches` | Create a new branch (records creator and parent). |
| `PATCH` | `/branches/{branch_id}` | Rename or describe an existing branch. |
| `GET` | `/projects/{project_id}/shelves` | List shelved changelists for review or restoration. |
| `POST` | `/shelves` | Create a shelf linked to a workspace and asset version. |
| `DELETE` | `/shelves/{shelf_id}` | Remove a shelf (owner or admin only). |
| `GET` | `/projects/{project_id}/permissions` | Inspect explicit grants on a project (admin only). |
| `POST` | `/projects/{project_id}/permissions` | Create or update project-level permissions (admin only). |
| `PUT` | `/permissions/{permission_id}` | Adjust an existing permission record (admin only). |
| `DELETE` | `/permissions/{permission_id}` | Revoke a permission grant (admin only). |

Plugins should set the `Authorization: Bearer <token>` header on all requests. The service automatically calls `set_app_user` so database RLS policies apply without additional plugin logic. The shared Python REST client and Unity editor script demonstrate this handshake end-to-end.

### Reference Implementations Updated

- **Unity Editor package** (under `plugins/unity`): now authenticates via `/auth/token`, queries `/projects/{project_id}/assets`, and writes imported asset manifests to the local project. Artists can browse and pull latest versions without leaving the editor.
- **Common REST client** (under `plugins/common`): handles token caching, project-scoped asset queries, branch management, shelf creation, and permission management so new host integrations can focus on UI concerns.

## Autodesk Maya

- **Languages:** Python 2/3 (via `maya.cmds` and `PySide2`), with optional C++ nodes for performance-critical tasks.
- **UI Toolkit:** Qt (PySide2) for dockable panels.
- **Key Features:**
  - Browse/search the Game Asset Database.
  - Import geometry, rigs, and materials directly into the current scene.
  - Publish updated assets with version metadata and preview renders.
- **Build Steps:**
  1. Create a Maya module directory containing `plug-ins`, `scripts`, and `icons` folders.
  2. Implement commands in Python leveraging the REST client and Maya's scene graph APIs.
  3. Package with `mayapkg` or custom installer scripts for Windows/macOS/Linux.
  4. Provide shelf buttons and a menu entry for quick access.

## Adobe Illustrator

- **Languages:** JavaScript (ExtendScript/UXP) with Python-side helper service if deeper integration is required.
- **UI Toolkit:** UXP panels for modern versions; CEP extensions for legacy support.
- **Key Features:**
  - Pull vector assets, palettes, and templates from the database.
  - Push exported SVG/AI versions with tagging and metadata.
- **Build Steps:**
  1. Scaffold a UXP plugin using Adobe's UDT (Unified Developer Tools).
  2. Implement REST calls via fetch/XHR; if unavailable, bridge to a local Python helper using WebSockets.
  3. Package with Adobe's signing tools and distribute through internal plugin manager.
  4. Test on Windows and macOS (Illustrator does not run on Linux).

## Blender

- **Languages:** Python 3 (`bpy`).
- **UI Toolkit:** Blender's `bpy.types.Panel` and operators.
- **Key Features:**
  - Asset browser integration with previews.
  - Synchronize materials and texture libraries.
  - Publish scene or collection snapshots to the database.
- **Build Steps:**
  1. Create an add-on folder with `__init__.py` defining `bl_info` and registration hooks.
  2. Implement operators for import/export using the REST client.
  3. Expose settings in the Add-on preferences panel.
  4. Package as a `.zip` for installation on Windows/macOS/Linux.

## Unity

- **Languages:** C# (Editor scripts) with optional Python via Unity Python package (for tooling only).
- **UI Toolkit:** UI Toolkit (UITK) or IMGUI for editor windows.
- **Key Features:**
  - Project asset browser panel linked to the database.
  - Prefab/material sync with version awareness.
  - Automated import pipelines triggered on asset updates.
- **Build Steps:**
  1. Create an Editor assembly definition targeting Unity 2020 LTS and newer.
  2. Implement REST/GraphQL clients in C# (use `HttpClient`).
  3. Provide ScriptableObject-based settings stored under `ProjectSettings`.
  4. Package with Unity's Package Manager (UPM) for distribution across Windows/macOS.

## Adobe Photoshop

- **Languages:** JavaScript (UXP) or TypeScript with React for UXP panels; CEP for legacy versions.
- **UI Toolkit:** UXP/React.
- **Key Features:**
  - Browse texture libraries, drag-and-drop into documents.
  - Publish layered PSDs with thumbnails and metadata.
  - Sync brushes and patterns associated with assets.
- **Build Steps:**
  1. Scaffold a UXP plugin via Adobe UDT.
  2. Implement REST calls with OAuth2 token handling.
  3. Package and sign the plugin for Windows/macOS distribution.
  4. Document installation steps for artists (manual copy or CC deployment).

## Adobe Substance 3D Painter/Designer

- **Languages:** Python (Painter's plugin API) and JavaScript (Designer), with C++ hooks where required.
- **UI Toolkit:** Qt for Designer, custom panels for Painter.
- **Key Features:**
  - Download/upload material presets, smart masks, and procedural graphs.
  - Maintain texture set versions linked to assets.
  - Automate export presets aligned with engine requirements.
- **Build Steps:**
  1. For Painter, create a Python plugin using the `substance_painter` module.
  2. For Designer, use the Automation Toolkit with Python or JavaScript scripts.
  3. Implement REST client wrappers and local caching for offline usage.
  4. Package using Adobe's plugin packaging guides; target Windows/macOS.

## Autodesk 3ds Max

- **Languages:** Python (`pymxs`) or MaxScript; C# via the .NET SDK for advanced scenarios (Windows-only).
- **UI Toolkit:** Qt for Python-based UIs.
- **Key Features:**
  - Asset browser for geometry and animation data.
  - Versioned publishing with metadata validation.
  - Batch processing tools for material updates.
- **Build Steps:**
  1. Develop Python scripts using `pymxs` to manipulate scenes.
  2. Wrap functionality in a 3ds Max plugin package (`.mzp` or signed installer).
  3. Integrate REST client and auth flow with cached credentials.
  4. Provide Windows installers; macOS/Linux not supported.

## Testing & CI Recommendations

- Establish automated smoke tests within each host environment (e.g., headless Blender, Unity batch mode).
- Use the Game Asset Database's staging environment for integration testing.
- Configure CI pipelines (GitHub Actions, Azure DevOps) to lint and package plugins per platform.

## Distribution & Support

- Host plugins in an internal package registry with version metadata.
- Provide release notes and migration guides for each update.
- Maintain a shared troubleshooting guide covering authentication, network connectivity, and host-specific issues.

