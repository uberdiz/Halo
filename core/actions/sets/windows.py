"""
core/actions/sets/windows.py

Window actions (focus, maximise, snap left/right for tiling, close) through SAINT's existing desktop backend
(modules/desktop/controller.py), which already works on Windows and on KWin.
"""

from __future__ import annotations

from ..registry import RISKY, Action, ActionResult, P

_ARRANGE = ["maximize", "minimize", "restore", "snap_left", "snap_right", "center"]


def _desktop():
    from modules.desktop.controller import desktop
    return desktop


def _focus(p):
    w = _desktop().focus(p["window"])
    return ActionResult(True, f"{w.title} is in front.")


def _arrange(p):
    w = _desktop().arrange(p["window"], p["how"])
    return ActionResult(True, f"{w.title}: {p['how'].replace('_', ' ')}.")


def _close(p):
    _desktop().close(p["window"])
    return ActionResult(True, f"Closed {p['window']}.")


def register(registry):
    window = P("string", "app or window title")
    for a in [
        Action("windows.focus", "Bring a window to the front", _focus, {"window": window},
               keywords="switch show raise", preview=lambda p: f"Bring {p['window']} to the front."),
        Action("windows.arrange", "Maximise, minimise or snap a window", _arrange,
               {"window": window, "how": P("string", enum=_ARRANGE)}, keywords="tile split half side resize",
               preview=lambda p: f"{p['how'].replace('_', ' ').capitalize()}: {p['window']}."),
        Action("windows.close", "Close a window", _close, {"window": window}, risk=RISKY,
               keywords="quit exit", preview=lambda p: f"Close {p['window']} (unsaved work may be lost)."),
    ]:
        registry.register(a, replace=True)
