"""
core/actions/sets/wallpaper.py

Wallpapers beyond a solid colour: a Wallpaper Engine wallpaper from the Steam workshop (core/wallpaper_engine.py),
by workshop id or by words from its title.
"""

from __future__ import annotations

from ..registry import SAFE, Action, ActionError, ActionResult, P

LINUX = ("linux",)


def _apply_engine(p):
    from core import wallpaper_engine as we
    found = we.items()
    if not found:
        raise ActionError("I didn't find any Wallpaper Engine wallpapers. Subscribe to some in Wallpaper Engine on "
                          "Steam first.", "NOT_FOUND")
    query = (p.get("item") or "").strip()
    if query:
        item = we.find(query, found)
        if item is None:
            raise ActionError(f"No Wallpaper Engine wallpaper matches “{query}”.", "NOT_FOUND")
    else:                                   # "a Wallpaper Engine wallpaper": a different one each time, no model
        import random
        item = random.choice(found)
    try:
        msg = we.apply(item, screen=int(p.get("screen", -1)))
    except we.EngineError as e:
        raise ActionError(str(e), "MISSING_TOOL" if "Install support" in str(e) else "FAILED")
    return ActionResult(True, msg, data={"id": item["id"], "title": item["title"], "type": item["type"]})


def _sync_accent(p):
    from core import accent
    color = accent.sync()
    if color is None:
        raise ActionError("I couldn't read which wallpaper is on the desktop.", "FAILED")
    return ActionResult(True, f"The accent colour now matches the wallpaper ({color}).", data={"color": color})


def _slideshow(p):
    from ui.settings_pages import wallpaper as wp
    try:
        script = wp.slideshow_script(p["folder"], p.get("minutes", 10), int(p.get("screen", -1)))
    except ValueError as e:
        raise ActionError(str(e), "INVALID_PARAMS")
    why = wp.run_script(script)
    if why:
        raise ActionError(why, "FAILED")
    return f"The wallpaper is now a slideshow of {p['folder']}, changing every {p.get('minutes', 10):g} minutes."


def _open_app(p):
    from ui.settings_pages.wallpaper import open_wallpapers_app
    open_wallpapers_app()
    return "Here are your wallpapers."


def _add_visualizer(p):
    from ui.settings_pages import wallpaper as wp
    why = wp.run_script(wp.widget_script(int(p.get("screen", -1))))
    if why:
        raise ActionError(why, "FAILED")
    return "The SAINT Visualizer widget is on your desktop."


def register(registry):
    registry.register(
        Action("wallpaper.open_app", "Open HalOS Wallpapers (Wallpaper Engine, SAINT's wallpaper, pictures)", _open_app,
               {}, risk=SAFE, platforms=LINUX,
               keywords="wallpapers app wallpaper engine change background desktop picture choose",
               preview=lambda p: "Open HalOS Wallpapers."), replace=True)
    registry.register(
        Action("wallpaper.add_visualizer", "Put the SAINT Visualizer widget on the desktop", _add_visualizer,
               {"screen": P("integer", "monitor number from 0, or -1 for all", required=False, minimum=-1,
                            maximum=16)},
               risk=SAFE, platforms=LINUX, keywords="visualizer widget saint logo bars audio desktop add",
               preview=lambda p: "Add the SAINT Visualizer widget to the desktop."), replace=True)
    registry.register(
        Action("wallpaper.sync_accent", "Match the accent colour to the wallpaper", _sync_accent, {},
               risk=SAFE, platforms=LINUX, keywords="accent colour color theme match wallpaper background tint",
               preview=lambda p: "Pick the accent colour from the wallpaper."), replace=True)
    registry.register(
        Action("wallpaper.slideshow", "Make the wallpaper a slideshow of a folder", _slideshow,
               {"folder": P("string", "absolute path of a folder of pictures"),
                "minutes": P("number", "minutes per picture", required=False, minimum=0.2, maximum=1440),
                "screen": P("integer", "monitor number from 0, or -1 for all", required=False, minimum=-1,
                            maximum=16)},
               risk=SAFE, platforms=LINUX, keywords="wallpaper slideshow rotate change pictures photos folder playlist",
               preview=lambda p: f"Show the pictures in {p['folder']} as a wallpaper slideshow."), replace=True)
    registry.register(
        Action("wallpaper.apply_engine", "Use a Wallpaper Engine wallpaper", _apply_engine,
               {"item": P("string", "workshop id or words from the title; empty for any", required=False),
                "screen": P("integer", "monitor number from 0, or -1 for all", required=False, minimum=-1,
                            maximum=16)},
               risk=SAFE, platforms=LINUX, keywords="wallpaper engine steam workshop animated live background desktop",
               preview=lambda p: f"Set the Wallpaper Engine wallpaper {p.get('item') or '(any)'}."), replace=True)
