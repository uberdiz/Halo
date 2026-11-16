"""Avatar notes from the PC: dropped on a window in front she stays on it (not the bigger one behind), and on Wayland
her eyes follow the pointer from where her window really is."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint

ROOT = Path(__file__).resolve().parent.parent
MAIN_JS = ROOT / "packaging/linux/rootfs/usr/share/kwin/scripts/saint-shell/contents/code/main.js"


def _window_under_feet(windows, avatar):
    src = MAIN_JS.read_text(encoding="utf-8")
    start = src.index("function windowUnderFeet(g)")
    end = src.index("\n}\n", start) + 3
    harness = (f"const workspace = {{stackingOrder: {json.dumps(windows)}}};\n"
               "function isSaint(w) { return false; }\nfunction onThisDesktop(w) { return true; }\n"
               + src[start:end] + f"\nconst w = windowUnderFeet({json.dumps(avatar)});\n"
               "console.log(w ? w.name : 'none');\n")
    return subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True).stdout.strip()


def _win(name, x, y, w, h, **kw):
    return {"name": name, "normalWindow": True, "minimized": False, "fullScreen": False,
            "frameGeometry": {"x": x, "y": y, "width": w, "height": h}, **kw}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node to run the KWin script")
def test_dropped_on_the_front_window_she_stays_on_it_not_the_one_behind():
    behind = _win("behind", 0, 300, 1920, 780)          # bigger, its top edge a little higher
    front = _win("front", 400, 360, 900, 500)
    she = {"x": 700, "y": 360 - 400 + 20, "width": 260, "height": 414}     # feet just inside front's title bar
    assert _window_under_feet([behind, front], she) == "front"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node to run the KWin script")
def test_fullscreen_or_nothing_under_her_is_no_perch():
    full = _win("full", 0, 0, 1920, 1080, fullScreen=True)
    she = {"x": 700, "y": 200, "width": 260, "height": 414}
    assert _window_under_feet([full], she) == "none"


def test_gaze_uses_her_window_position_not_mapToGlobal():
    from ui.avatar import AvatarView

    class Win:
        def current_pos(self):
            return QPoint(1000, 500)                  # where SAINT put her (Wayland: Qt itself thinks 0,0)

    class View:
        cfg = {"view": "portrait"}
        look = None

        def window(self):
            return win

        def mapTo(self, _w, p):
            return QPoint(0, 0)

        def mapToGlobal(self, p):
            return QPoint(0, 0)

        def width(self):
            return 200

        def height(self):
            return 300

        def _holo(self):
            return False

    win, v = Win(), View()
    AvatarView.look_at(v, 1400, 500 + 300 * 0.42)        # her eyes are at x=1100: this is to her right
    yaw_right, _ = v.look
    AvatarView.look_at(v, 900, 500 + 300 * 0.42)
    yaw_left, _ = v.look
    assert yaw_right * yaw_left < 0                      # left of her and right of her turn opposite ways
