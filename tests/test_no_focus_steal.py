"""SAINT never takes the keyboard or the desktop away from what the person is doing."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL_JS = ROOT / "packaging/linux/rootfs/usr/share/kwin/scripts/saint-shell/contents/code/main.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")

# Windows appear and get focused the way KWin does it: windowAdded, then windowActivated.
HARNESS = r"""
const vm = require('vm');
const added = [], activated = [], log = [];
let active = null;
const ws = {
  windowList: () => wins, windowAdded: {connect(f) { added.push(f); }}, windowRemoved: {connect() {}},
  windowActivated: {connect(f) { activated.push(f); }}, currentDesktop: 'd1', cursorPos: {x: 0, y: 0},
  screenAt: () => null,
  get activeWindow() { return active; },
  set activeWindow(w) { active = w; log.push(w.caption); activated.forEach(f => f(w)); }
};
function win(caption, cls, extra) {
  return Object.assign({caption, resourceClass: cls, internalId: caption, pid: 1, normalWindow: true,
                        desktops: ['d1'], frameGeometry: {x: 0, y: 0, width: 1, height: 1},
                        captionChanged: {connect() {}}}, extra || {});
}
const wins = [];
vm.runInNewContext(__SOURCE__, {KWin: {}, workspace: ws, readConfig: (k, d) => d, registerScreenEdge() {},
                                callDBus() {}, console});
function show(w, focus) {           // map a window; KWin focuses it if `focus`
  wins.push(w);
  added.forEach(f => f(w));
  if (focus) { active = w; activated.forEach(f => f(w)); }
}
const steps = __STEPS__;
const out = {};
for (const s of steps) {
  const w = win(s.caption, s.cls || 'saint', s.extra);
  show(w, s.focus !== false);
  out[s.caption] = active ? active.caption : null;
}
console.log(JSON.stringify({out, log}));
"""


def _run(steps):
    code = HARNESS.replace("__SOURCE__", json.dumps(SHELL_JS.read_text(encoding="utf-8"))) \
                  .replace("__STEPS__", json.dumps(steps))
    res = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


@needs_node
def test_the_avatar_appearing_gives_the_keyboard_back_to_the_store():
    r = _run([{"caption": "SAINT Store", "cls": "saint-store"},
              {"caption": "SAINT Avatar SAINT:place:10,10,200,300"}])
    assert r["out"]["SAINT Avatar SAINT:place:10,10,200,300"] == "SAINT Store"


@needs_node
@pytest.mark.parametrize("caption", ["SAINT notice SAINT:place:0,0,9,9", "SAINT plan SAINT:place:0,0,9,9",
                                     "SAINT mini player SAINT:helper"])
def test_no_helper_window_keeps_focus_when_it_appears(caption):
    r = _run([{"caption": "Game", "cls": "steam_app_1"}, {"caption": caption}])
    assert r["out"][caption] == "Game"


@needs_node
def test_the_overlay_and_saints_own_window_do_get_focus():
    r = _run([{"caption": "Firefox", "cls": "firefox"}, {"caption": "SAINT overlay SAINT:place:0,0,1920,1080"},
              {"caption": "SAINT", "cls": "saint"}])
    assert r["out"]["SAINT overlay SAINT:place:0,0,1920,1080"] == "SAINT overlay SAINT:place:0,0,1920,1080"
    assert r["out"]["SAINT"] == "SAINT"


@needs_node
def test_focus_never_goes_back_to_a_window_on_another_desktop():
    r = _run([{"caption": "Game", "cls": "steam_app_1", "extra": {"desktops": ["d2"]}},
              {"caption": "SAINT Avatar SAINT:place:1,1,1,1"}])
    assert r["log"] == []                                  # nothing switched the person to desktop 2


def test_activating_a_window_elsewhere_only_happens_when_asked():
    from modules.desktop.linux import kwin
    here = kwin.action_body("abc", "activate_here")
    assert "workspace.currentDesktop" in here and "if (here)" in here
    assert "currentDesktop" not in kwin.action_body("abc", "activate")


def test_unasked_steps_activate_on_this_desktop_only(monkeypatch):
    from core.focus_guard import focus_guard
    from modules.desktop import controller as ctl
    calls = []

    class WM:
        def activate(self, handle, switch_desktop=True):
            calls.append(switch_desktop)

    import modules.desktop.backend as backend
    monkeypatch.setattr(backend, "window_manager", lambda: WM())
    d = ctl.DesktopController.__new__(ctl.DesktopController)
    monkeypatch.setattr(ctl, "HAS_WIN32", False)
    monkeypatch.setattr(d, "_info", lambda h: type("I", (), {"foreground": False})(), raising=False)
    w = type("W", (), {"title": "Discord", "hwnd": "h1"})()
    focus_guard.begin("check my downloads in the background", explicit=False)
    with pytest.raises(ctl.ToolError, match="another desktop"):
        d._activate(w)
    focus_guard.begin("switch to Discord")
    with pytest.raises(ctl.ToolError, match="didn't bring"):
        d._activate(w)
    assert calls == [False, True]
