**Version:** 1.9.1  
**Author:** Sunkanwei  
**License:** GPL-3.0-or-later  
**Blender Support:** 4.5 – 5.0+

# NodeLink Navigator

Highlight node categories with theme-aware colors and quickly navigate between connected nodes across Shader, Geometry, and Compositor editors.

- **Author:** Sunkanwei  
- **License:** GPL-3.0-or-later  
- **Blender Support:** 5.0+

## Features
- Theme-aware border colors (reads Blender theme; not hard-coded).
- High-saturation highlighting for better visibility.
- Follow link chains and jump to upstream/downstream nodes with a pie menu.
- Works in **Shader**, **Geometry Nodes**, and **Compositor** editors.

## Installation
1. Download the ZIP that contains:
init.py
blender_manifest.toml
operators.py
colors.py
lang_dict.py
LICENSE
README.md
2. In Blender: **Edit → Preferences → Extensions** (or **Add-ons** on older versions) → **Install from Disk** → select the ZIP → enable **NodeLink Navigator**.

## Usage
- Open a Node Editor (Shader/Geometry/Compositor).
- Press **`C`** to activate the link highlighter.
- **LMB** while hovering a socket to open the pie menu, then jump to upstream/downstream nodes.

## Settings
- **Language:** Preferences → Add-ons → NodeLink Navigator → choose *English* or *简体中文（zh_HANS）*.
- **Keymap:** The default hotkey is `C`; you can remap it in Preferences.

## Permissions
- No network access.
- No external file writes (only in-memory settings).
- Compatible with Blender’s extension sandbox.

## Compatibility Notes
- Colors come from `Preferences → Themes → Node Editor`.  
- High-saturation highlight is applied in HSV space to increase visibility while keeping the base hue.

## Troubleshooting
- If borders look misaligned at extreme UI scales, ensure you are in the Node Editor **Window** region; the add-on draws in `POST_PIXEL` and respects `ui_scale`.
- Press Alt + C (default) to activate the link highlighter.

## Building / Validation (optional)
```bash
blender --command extension validate
blender --command extension build

Changelog

1.9.0 – Theme-aware colors, high-saturation highlight, link pie menu jump, zh_HANS/EN language toggle.