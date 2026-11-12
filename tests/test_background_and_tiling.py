"""SAINT works without taking your focus: a hidden background desktop (Xvfb + xdotool, faked here), and windows
split across the screen without being activated."""
import sys

import pytest

from core import actions, tiling
from core.actions import ActionLog, executor, log as log_mod
from core.background_session import BackgroundDesktop, BackgroundError


# --------------------------------------------------------------------------- tiling
@pytest.mark.parametrize("n, expect", [
    (1, [(0, 0, 1920, 1040)]),
    (2, [(0, 0, 957, 1040), (963, 0, 957, 1040)]),
    (3, [(0, 0, 957, 1040), (963, 0, 957, 517), (963, 523, 957, 517)]),
    (4, [(0, 0, 957, 517), (963, 0, 957, 517), (0, 523, 957, 517), (963, 523, 957, 517)]),
])
def test_grid_layouts(n, expect):
    assert tiling.grid(n, (0, 0, 1920, 1040)) == expect


def test_grid_fills_the_area_without_overlap_for_many():
    rects = tiling.grid(7, (100, 50, 1800, 1000))
    assert len(rects) == 7
    for i, a in enumerate(rects):
        assert a[0] >= 100 and a[1] >= 50 and a[0] + a[2] <= 1900 and a[1] + a[3] <= 1050
        for b in rects[i + 1:]:
            assert a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]


class FakeWM:
    def __init__(self):
        self.placed = []

    def set_pos(self, h, x, y, w, hh, move=True, activate=True):
        self.placed.append((h, x, y, w, hh, activate))


def test_tile_action_never_activates_and_can_be_undone(tmp_path, monkeypatch):
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    from modules.desktop import controller
    W = lambda h, t: type("W", (), {"hwnd": h, "title": t, "minimized": False, "left": 10 * h, "top": 5, "width": 800,
                                    "height": 600})()
    mon = type("M", (), {"index": 1, "primary": True, "work": (0, 0, 1920, 1040)})()
    wm = FakeWM()
    fake = type("D", (), {"monitors": lambda self: [mon], "windows_on": lambda self, i: [W(1, "Firefox"), W(2, "AIDE")],
                          "find_window": lambda self, q: W(3, q), "_wm": wm})()
    monkeypatch.setattr(controller, "desktop", fake)
    r = actions.execute("windows.tile", {}, source="saint")
    assert r.ok and "2 windows" in r.message
    assert [p[0] for p in wm.placed] == [1, 2] and not any(p[5] for p in wm.placed)      # never activated
    assert actions.undo(r.entry_id).ok and wm.placed[-1][1:5] == (20, 5, 800, 600)


# --------------------------------------------------------------------------- background desktop
class Proc:
    def __init__(self, argv):
        self.argv, self.pid, self.alive = argv, 4242, True

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive = False


def fake_desktop(tmp_path, xdotool_out=""):
    calls, started = [], []

    def popen(argv, **kw):
        started.append((argv, kw.get("env", {})))
        if argv[0] == "Xvfb":
            (tmp_path / f"X{argv[1][1:]}").write_text("")
        return Proc(argv)

    def run(argv, **kw):
        calls.append((argv, kw.get("env", {})))
        return type("R", (), {"returncode": 0, "stdout": xdotool_out, "stderr": ""})()
    d = BackgroundDesktop(run=run, popen=popen, which=lambda t: f"/usr/bin/{t}", sockets=str(tmp_path))
    return d, calls, started


def test_background_desktop_is_a_separate_display_and_apps_never_see_wayland(tmp_path, monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    d, calls, started = fake_desktop(tmp_path)
    display = d.start()
    assert display == ":42" and started[0][0][:2] == ["Xvfb", ":42"] and "-nolisten" in started[0][0]
    d.open(["firefox", "https://example.com"])
    env = started[1][1]
    assert env["DISPLAY"] == ":42" and "WAYLAND_DISPLAY" not in env and env["QT_QPA_PLATFORM"] == "xcb"
    d.type("hello")
    d.key("ctrl+s")
    d.click(400, 300)
    argvs = [c[0] for c in calls]
    assert argvs[0][:2] == ["xdotool", "type"] and argvs[0][-1] == "hello"
    assert argvs[1] == ["xdotool", "key", "--", "ctrl+s"] and argvs[2][:4] == ["xdotool", "mousemove", "400", "300"]
    assert all(c[1]["DISPLAY"] == ":42" for c in calls)                     # never your display
    d.stop()
    assert not d.running


def test_missing_tools_and_apps_are_explained(tmp_path):
    d = BackgroundDesktop(which=lambda t: None, sockets=str(tmp_path))
    with pytest.raises(BackgroundError, match="needs Xvfb"):
        d.start()
    d2, _calls, _started = fake_desktop(tmp_path)
    d2._which = lambda t: None if t == "nonsense-app" else f"/usr/bin/{t}"
    with pytest.raises(BackgroundError, match="isn't installed"):
        d2.open(["nonsense-app"])


def test_background_actions_go_through_trust(tmp_path, monkeypatch):
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    d, calls, started = fake_desktop(tmp_path)
    from core import background_session
    monkeypatch.setattr(background_session, "_shared", d)
    r = actions.execute("background.open", {"command": "firefox https://example.com"}, source="saint")
    assert r.needs_confirmation and "not on your screen" in r.preview          # opening a program asks by default
    ok = actions.execute("background.open", {"command": "firefox https://example.com"}, source="saint", confirmed=True)
    assert ok.ok and started[-1][0] == ["firefox", "https://example.com"]
    assert actions.execute("background.type", {"text": "hi"}, source="saint").ok


@pytest.mark.parametrize("text, name", [("tile my windows", "os.windows.tile"), ("split the screen", "os.windows.tile"),
                                        ("show me what you're doing in the background", "os.background.show")])
def test_saint_phrases(text, name, monkeypatch):
    from modules.agent import os_intents
    monkeypatch.setattr(os_intents, "_available", lambda a: True)
    intent = os_intents.parse_os(text)
    assert intent is not None and intent.name == name
