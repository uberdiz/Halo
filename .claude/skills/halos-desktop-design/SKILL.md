---
name: halos-desktop-design
description: Use when working on HalOS Settings, HalOS Files (search), the icon theme, the living wallpaper/SAINT visualizer, animations, or any HalOS-made UI.
---
# Rules
- Keep one design language across SAINT, Store, Settings and Files: reuse the existing theme tokens in `ui/`; don't start a new visual system.
- Icons: redesign everything except the main HalOS/Orbit logo. SVG, light and dark, installed as the default icon theme.
- Wallpaper: a user-chosen colour or gradient plus a movable, resizable SAINT logo that visualises mic, desktop audio or idle animation, configurable per monitor, with an FPS cap and under 2% GPU when idle.
- Settings and Files call the shared action registry (see halos-ai-shell), so everything is also available to SAINT.
- Files search: a local index plus a semantic layer; type-ahead intent ("the app for claude"); under 100 ms for indexed queries (measure it).
- Before any UI work is marked done, screenshot it in the VM and check light and dark themes.
