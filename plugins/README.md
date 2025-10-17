# Game Asset Database Plugin Suite

This directory contains cross-application plugins that integrate the Game Asset Database with popular DCC and game production tools. Each plugin follows the guidance in `docs/plugins.md` and shares a common configuration and REST client implementation.

## Shared Components

The `common` package provides utilities for reading plugin configuration, authenticating with the Game Asset Database service, and issuing REST requests. Python-based plugins import these helpers directly. Non-Python plugins replicate the same configuration layout for consistency.

## Available Plugins

- Autodesk Maya (Python module package)
- Adobe Illustrator (UXP extension)
- Blender (Python add-on)
- Unity Editor (C# package)
- Adobe Photoshop (UXP extension)
- Adobe Substance 3D Painter/Designer (Python/JavaScript scripts)
- Autodesk 3ds Max (Python/MaxScript hybrid)

Refer to each plugin folder for installation and packaging instructions specific to the host application.
