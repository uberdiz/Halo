"""
core/actions/sets/background.py

SAINT working on the hidden background desktop (core/background_session.py): open apps there, type, press keys,
click, look. Nothing reaches your own keyboard, mouse or windows. Opening an app is risky (it runs a program); the
rest only affects apps already opened there.
"""

from __future__ import annotations

import shlex

from ..registry import RISKY, SAFE, Action, ActionError, ActionResult, P

LINUX = ("linux",)


def _bg():
    from core.background_session import shared
    return shared()


def _wrap(fn):
    def run(p):
        from core.background_session import BackgroundError
        try:
            return fn(p)
        except BackgroundError as e:
            raise ActionError(str(e), "FAILED")
    return run


def _open(p):
    argv = shlex.split(p["command"])
    pid = _bg().open(argv)
    return ActionResult(True, f"Opened {argv[0]} on the background desktop (you can keep working).", data={"pid": pid})


def _type(p):
    if p.get("window"):
        _bg().focus(p["window"])
    _bg().type(p["text"])
    return f"Typed {len(p['text'])} characters on the background desktop."


def _key(p):
    _bg().key(p["keys"])
    return f"Pressed {p['keys']} on the background desktop."


def _click(p):
    _bg().click(p["x"], p["y"])
    return f"Clicked at {p['x']}, {p['y']} on the background desktop."


def _look(p):
    import tempfile
    path = tempfile.mktemp(prefix="saint-bg-", suffix=".png")
    _bg().screenshot(path)
    return ActionResult(True, "Took a picture of the background desktop.", data={"path": path,
                                                                                 "windows": _bg().windows()})


def _stop(p):
    _bg().stop()
    return "Closed the background desktop and everything SAINT opened there."


def register(registry):
    for a in [
        Action("background.open", "Open an app on the background desktop", _wrap(_open),
               {"command": P("string", "the app's command, e.g. firefox https://example.com")}, risk=RISKY,
               platforms=LINUX, keywords="hidden behind the scenes without disturbing me",
               preview=lambda p: f"Open “{p['command']}” on SAINT's background desktop (not on your screen)."),
        Action("background.type", "Type on the background desktop", _wrap(_type),
               {"text": P("string"), "window": P("string", "window title to type into", required=False)},
               platforms=LINUX, keywords="keyboard enter text",
               preview=lambda p: f"Type {len(p['text'])} characters on the background desktop."),
        Action("background.key", "Press keys on the background desktop", _wrap(_key),
               {"keys": P("string", "e.g. ctrl+s Return", pattern=r"[A-Za-z0-9_+ ]{1,80}")}, platforms=LINUX,
               keywords="shortcut press", preview=lambda p: f"Press {p['keys']} on the background desktop."),
        Action("background.click", "Click on the background desktop", _wrap(_click),
               {"x": P("integer", minimum=0, maximum=4000), "y": P("integer", minimum=0, maximum=4000)},
               platforms=LINUX, keywords="mouse", preview=lambda p: f"Click at {p['x']}, {p['y']} there."),
        Action("background.look", "Look at the background desktop", _wrap(_look), {}, risk=SAFE, platforms=LINUX,
               keywords="screenshot see check", preview=lambda p: "Take a picture of the background desktop."),
        Action("background.stop", "Close the background desktop", _wrap(_stop), {}, platforms=LINUX,
               keywords="end finish", preview=lambda p: "Close everything SAINT opened on the background desktop."),
    ]:
        registry.register(a, replace=True)
