# Game Asset Database Photoshop Plugin (UXP)

This UXP-based extension offers Game Asset Database integration inside
Adobe Photoshop. Artists can browse textures, drag-and-drop resources
into open documents, and publish layered PSDs with metadata.

## Development

1. Install Adobe's Unified Developer Tools (UDT).
2. Run `uxp devtools plugin start` pointing to this directory to load the
   plugin into Photoshop.
3. Update the shared configuration file produced by `plugins/common` with
   API credentials before authenticating.

## Packaging

Package and sign the plugin with Adobe's tooling to generate `.ccx`
installers for Windows and macOS.
