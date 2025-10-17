# Game Asset Database Substance Plugins

This directory houses integration scripts for Adobe Substance 3D Painter
and Designer. Painter relies on Python automation, while Designer
supports both Python and JavaScript via the Automation Toolkit.

## Painter Plugin

Located under `painter/`, the plugin registers a dedicated shelf with
buttons for syncing materials, downloading smart masks, and publishing
texture sets.

## Designer Automation

Located under `designer/`, the scripts expose commands for fetching and
submitting procedural graphs. They can be registered via the Automation
Toolkit or executed manually for batch processing.
