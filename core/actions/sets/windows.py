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


def _tile(p):
    """Split a monitor between the named windows (or every window on it), without taking the focus."""
    from core.tiling import grid
    d = _desktop()
    mons = d.monitors()
    mon = next((m for m in mons if m.index == p.get("monitor")), None) or next((m for m in mons if m.primary), mons[0])
    if p.get("windows"):
        wins = [d.find_window(name) for name in p["windows"]]
    else:
        wins = d.windows_on(mon.index)
    wins = [w for w in wins if not w.minimized][:9]
    if not wins:
        return ActionResult(False, error="There are no windows to arrange on that monitor.", code="NOT_FOUND")
    left, top, right, bottom = mon.work
    rects = grid(len(wins), (left, top, right - left, bottom - top))
    before = []
    for w, (x, y, cw, ch) in zip(wins, rects):
        before.append({"hwnd": w.hwnd, "rect": [w.left, w.top, w.width, w.height]})
        d._wm.set_pos(w.hwnd, x, y, cw, ch, activate=False)
    return ActionResult(True, f"Split the screen between {len(wins)} windows.", undo={"windows": before})


def _untile(t):
    d = _desktop()
    for item in t.get("windows", []):
        x, y, w, h = item["rect"]
        try:
            d._wm.set_pos(item["hwnd"], x, y, w, h, activate=False)
        except Exception:
            continue
    return "Put the windows back where they were."


def register(registry):
    window = P("string", "app or window title")
    for a in [
        Action("windows.focus", "Bring a window to the front", _focus, {"window": window},
               keywords="switch show raise", preview=lambda p: f"Bring {p['window']} to the front."),
        Action("windows.arrange", "Maximise, minimise or snap a window", _arrange,
               {"window": window, "how": P("string", enum=_ARRANGE)}, keywords="tile split half side resize",
               preview=lambda p: f"{p['how'].replace('_', ' ').capitalize()}: {p['window']}."),
        Action("windows.tile", "Split the screen between windows", _tile,
               {"windows": P("array", "window titles; empty = every window on the monitor", required=False),
                "monitor": P("integer", "1-based", required=False, minimum=1, maximum=8)},
               undo=_untile, keywords="tile split side by side arrange grid snap all",
               preview=lambda p: "Split the screen between " + (", ".join(p["windows"]) if p.get("windows")
                                                               else "the open windows") + "."),
        Action("windows.close", "Close a window", _close, {"window": window}, risk=RISKY,
               keywords="quit exit", preview=lambda p: f"Close {p['window']} (unsaved work may be lost)."),
    ]:
        registry.register(a, replace=True)
