"""The living wallpaper: safe settings into Plasma, a live preview, the audio feed's numbers, and the image wiring."""
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from core import audio_feed
from ui.settings_pages import wallpaper as wp

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "packaging/linux/rootfs/usr/share/plasma/wallpapers/org.halos.living"


def test_values_are_checked_and_clamped():
    v = wp.clean({"Color": "red'); evil(); ('", "Color2": "#ABCDEF", "LogoScale": 5, "LogoX": -1, "Fps": "999",
                  "Source": "camera", "Background": "solid", "Glow": "0.4", "Bars": 0})
    assert v["Color"] == wp.DEFAULTS["Color"] and v["Color2"] == "#abcdef"
    assert v["LogoScale"] == 0.8 and v["LogoX"] == 0 and v["Fps"] == 60 and v["Source"] == "saint"
    assert v["Background"] == "solid" and v["Glow"] == 0.4 and v["Bars"] is False


def test_plasma_script_only_carries_clean_values():
    script = wp.plasma_script({"Color": "#123456", "LogoX": 0.25, "Source": "desktop", "Bars": False}, screen=1)
    assert "d.wallpaperPlugin = 'org.halos.living';" in script and "d.screen !== 1" in script
    assert "d.writeConfig('Color', '#123456');" in script and "d.writeConfig('LogoX', 0.25);" in script
    assert "d.writeConfig('Bars', false);" in script and "d.writeConfig('Source', 'desktop');" in script
    evil = wp.plasma_script({"Color": "#000000'); x('", "Source": "x'); y('"})
    assert "x(" not in evil and "y(" not in evil


def test_apply_falls_back_to_qdbus():
    calls = []

    def run(argv, **kw):
        calls.append(argv[0])
        if argv[0] == "qdbus6":
            raise FileNotFoundError
        return type("R", (), {"returncode": 0})()
    assert wp.apply(wp.DEFAULTS, run=run) and calls == ["qdbus6", "qdbus"]


def test_every_setting_the_qml_reads_is_declared():
    qml = (PLUGIN / "contents/ui/main.qml").read_text(encoding="utf-8")
    xml = (PLUGIN / "contents/config/main.xml").read_text(encoding="utf-8")
    used = set(re.findall(r"cfg\.([A-Z]\w+)", qml))
    declared = set(re.findall(r'<entry name="(\w+)"', xml))
    assert used <= declared and declared == set(wp.DEFAULTS)
    assert json.loads((PLUGIN / "metadata.json").read_text())["KPlugin"]["Id"] == "org.halos.living"
    assert "ws://127.0.0.1:47812/" in qml and "running: root.moving" in qml       # one clock, only while moving


def test_audio_analysis_hears_loud_and_quiet_and_pitch():
    rate = audio_feed.RATE
    quiet = audio_feed.analyse([0] * 512)
    assert quiet["level"] == 0 and max(quiet["bands"]) == 0
    tone = lambda f, amp: [int(amp * math.sin(2 * math.pi * f * t / rate)) for t in range(512)]
    low, high = audio_feed.analyse(tone(150, 20000)), audio_feed.analyse(tone(3000, 20000))
    assert low["level"] > 0.7 and high["level"] > 0.7
    assert low["bands"].index(max(low["bands"])) < high["bands"].index(max(high["bands"]))
    assert audio_feed.analyse(tone(150, 300))["level"] < low["level"]
    assert len(low["bands"]) == audio_feed.BANDS


def test_audio_feed_captures_only_while_someone_listens(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    started, stopped = [], []

    class Proc:
        def __init__(self, source):
            import io
            self.stdout = io.BytesIO(b"")
            started.append(source)

        def terminate(self):
            stopped.append(True)
    feed = audio_feed.AudioFeed(port=0, capture=lambda s: Proc(s))
    assert started == []                                                  # nothing until a wallpaper connects
    feed._start("mic")
    feed._start("mic")
    assert started == ["mic"]
    sock = type("S", (), {"deleteLater": lambda self: None})()
    feed._clients[sock] = "mic"
    feed._drop(sock)
    assert stopped == [True]
    feed.close()


def test_settings_page_previews_and_applies(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    applied = []
    page = wp.WallpaperPage(applier=lambda values, screen: applied.append((dict(values), screen)) or True)
    page.preset.setCurrentText("Top right")
    page.size.setValue(40)
    page.source.setCurrentIndex([k for k, _l in wp.SOURCES].index("breathing"))
    assert page.values["LogoX"] == 0.82 and page.values["LogoScale"] == 0.4 and page.preview.timer.isActive()
    page.source.setCurrentIndex([k for k, _l in wp.SOURCES].index("still"))
    assert not page.preview.timer.isActive()                              # still: nothing redraws
    assert page.use() and applied[0][0]["LogoY"] == 0.22 and applied[0][1] == -1
    img = page.preview.grab()
    assert img.width() >= 480


def test_halos_desktop_uses_it_by_default():
    js = (ROOT / "packaging/linux/rootfs/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/saintos-defaults.js").read_text(encoding="utf-8")
    assert 'd.wallpaperPlugin = "org.halos.living";' in js


@pytest.mark.skipif(not shutil.which("pyside6-qmllint") and not (Path(os.sys.executable).parent / "pyside6-qmllint.exe").exists(),
                    reason="needs qmllint")
def test_qml_parses():
    exe = shutil.which("pyside6-qmllint") or str(Path(os.sys.executable).parent / "pyside6-qmllint.exe")
    res = subprocess.run([exe, str(PLUGIN / "contents/ui/main.qml")], capture_output=True, text=True, timeout=60)
    assert "SyntaxError" not in (res.stdout + res.stderr) and "Expected token" not in (res.stdout + res.stderr)


def test_bar_style_is_checked_offered_and_previewed():
    assert wp.clean({})["BarStyle"] == "bars" and wp.clean({"BarStyle": "ring"})["BarStyle"] == "ring"
    assert wp.clean({"BarStyle": "x'); y('"})["BarStyle"] == "bars"
    assert "d.writeConfig('BarStyle', 'bars');" in wp.plasma_script({})
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    page = wp.WallpaperPage(applier=lambda values, screen: "")
    page.bar_style.setCurrentIndex(page.bar_style.findData("ring"))
    assert page.values["BarStyle"] == "ring" and not page.preview.grab().isNull()
    page._load({"BarStyle": "bars", "Source": "breathing"})
    assert page.bar_style.currentData() == "bars" and not page.preview.grab().isNull()
    assert page.use()


@pytest.mark.skipif(not shutil.which("node"), reason="node isn't installed")
def test_visualizer_rises_fast_falls_slowly_and_is_symmetric():
    js = (PLUGIN / "contents/ui/visualizer.js").read_text(encoding="utf-8").replace(".pragma library", "")
    qml = (PLUGIN / "contents/ui/main.qml").read_text(encoding="utf-8")
    assert 'import "visualizer.js" as Viz' in qml and "Viz.step(" in qml and 'barStyle === "ring"' in qml
    code = js + """
var s = [];
for (var f = 0; f < 6; f++) s = step(s, [1, 1, 1, 1], 4, 0, 0, 1 / 60, 1);
var peak = s.slice();
for (var f = 0; f < 6; f++) s = step(s, [0, 0, 0, 0], 4, 0, 0, 1 / 60, 1);
var spike = step([], [0, 0, 1, 0, 0], 5, 0, 0, 1, 1);
var a = step([], [1], 1, 0, 0, 1 / 20, 1)[0];
var b = step(step(step([], [1], 1, 0, 0, 1 / 60, 1), [1], 1, 0, 0, 1 / 60, 1), [1], 1, 0, 0, 1 / 60, 1)[0];
var bands = []; for (var i = 0; i < 48; i++) bands.push(bandFor(i, 48, 32));
console.log(JSON.stringify({peak: peak[0], after: s[0], spike: spike, a: a, b: b, bands: bands}));
"""
    res = subprocess.run([shutil.which("node"), "-e", code], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["peak"] > 0.95 and 0.4 < out["after"] < out["peak"]       # up in ~0.1 s, down gently
    assert out["spike"][2] < 0.6 and out["spike"][1] > 0                  # a lone spike is spread to its neighbours
    assert abs(out["a"] - out["b"]) < 1e-9                                 # 20 fps and 60 fps move the same
    assert out["bands"] == out["bands"][::-1] and out["bands"][23] == 0 and max(out["bands"]) == 31
