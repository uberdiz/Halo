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


def register(registry):
    registry.register(
        Action("wallpaper.apply_engine", "Use a Wallpaper Engine wallpaper", _apply_engine,
               {"item": P("string", "workshop id or words from the title; empty for any", required=False),
                "screen": P("integer", "monitor number from 0, or -1 for all", required=False, minimum=-1,
                            maximum=16)},
               risk=SAFE, platforms=LINUX, keywords="wallpaper engine steam workshop animated live background desktop",
               preview=lambda p: f"Set the Wallpaper Engine wallpaper {p.get('item') or '(any)'}."), replace=True)
