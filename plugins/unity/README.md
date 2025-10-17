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
2. Configure the Game Asset Database settings under **Edit → Project Settings
   → Game Asset Database**.

## Distribution

Publish the folder as a tarball or Git-based UPM package. Ensure the
`package.json` metadata is updated for each release.
