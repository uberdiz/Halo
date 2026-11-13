"""The HalOS look: fluid desktop defaults (blur, floating panel, soft shadows, translucent menus, Inter), the
accent colour taken from the wallpaper with plain arithmetic, and wallpaper slideshows."""
import colorsys
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from core import accent
from ui.settings_pages import wallpaper as wp

ROOT = Path(__file__).resolve().parents[1]
FS = ROOT / "packaging/linux/rootfs"
UPDATES = FS / "usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates"


def _hue(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


# --------------------------------------------------------------------------- accent from the wallpaper
def test_pick_follows_the_vivid_colour_not_the_big_dull_one():
    teal, grey, mud = (20, 170, 160), (90, 90, 90), (90, 80, 70)
    c = accent.pick([grey] * 3000 + [mud] * 800 + [teal] * 300)
    h, s, v = _hue(c)
    assert 0.45 < h < 0.52 and s >= 0.55 and v >= 0.87                 # teal, lifted to read on dark
    assert accent.pick([grey] * 3000 + [mud] * 800 + [teal] * 300) == c  # deterministic
    assert accent.pick([grey] * 4000) == accent.DEFAULT and accent.pick([]) == accent.DEFAULT


def test_from_image_reads_a_real_picture(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage(200, 120, QImage.Format_RGB32)
    img.fill(QColor("#101014"))
    g = QPainter(img)
    g.fillRect(40, 30, 90, 60, QColor("#7c3aed"))                         # a violet shape on near-black
    g.end()
    img.save(str(tmp_path / "w.png"))
    h, _s, _v = _hue(accent.from_image(tmp_path / "w.png"))
    assert 0.7 < h < 0.8
    assert accent.from_image(tmp_path / "missing.png") == accent.DEFAULT


def test_current_wallpaper_and_sync(tmp_path, monkeypatch):
    pic = tmp_path / "pkg/contents/images/1920x1080.png"
    pic.parent.mkdir(parents=True)
    pic.write_bytes(b"x" * 10)
    answers = {"out": "org.halos.living||#33AAFF"}
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return types.SimpleNamespace(returncode=0, stdout=answers["out"], stderr="")
    assert accent.current_wallpaper(run) == ("living", "#33aaff")
    answers["out"] = f"org.kde.image|{(tmp_path / 'pkg').as_uri()}|"
    assert accent.current_wallpaper(run) == ("image", str(pic))         # a package: its picture
    from core.config import config
    got = {}
    monkeypatch.setattr(config, "set", lambda k, v, persist=True: got.update({k: v}))
    assert accent.sync(run, image_accent=lambda p: "#123456") == "#123456"
    assert got["appearance.accent"] == "#123456"
    assert calls[-1] == ["plasma-apply-colorscheme", "--accent-color", "#123456"]
    with pytest.raises(ValueError):
        accent.apply("red; rm -rf /", run)


# --------------------------------------------------------------------------- slideshow
def test_slideshow_script(tmp_path):
    s = wp.slideshow_script(tmp_path, 15, screen=0)
    assert "d.wallpaperPlugin = 'org.kde.slideshow';" in s and f"'SlidePaths', '{tmp_path.as_posix()}'" in s
    assert "d.writeConfig('SlideInterval', 900);" in s and "d.reloadConfig();" in s
    with pytest.raises(ValueError):
        wp.slideshow_script(tmp_path / "nope")
    with pytest.raises(ValueError):
        wp.slideshow_script("relative/dir")


def test_actions_and_phrases(tmp_path, monkeypatch):
    from core import actions
    from modules.agent import os_intents
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    scripts = []
    monkeypatch.setattr(wp, "run_script", lambda script, run=None: scripts.append(script) or "")
    monkeypatch.setattr(accent, "sync", lambda: "#abcdef")
    res = actions.registry.get("wallpaper.slideshow").run({"folder": str(tmp_path), "minutes": 5})
    assert "slideshow" in str(res) and "SlideInterval', 300" in scripts[0]
    assert actions.registry.get("wallpaper.sync_accent").run({}).data["color"] == "#abcdef"
    intent = os_intents.parse_os("match the accent colour to my wallpaper")
    assert intent is not None and intent.name == "os.wallpaper.sync_accent"


# --------------------------------------------------------------------------- shipped defaults
def _kwinrc() -> str:
    pkg = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    return pkg.split('"$pkgdir/etc/xdg/kwinrc" <<\'EOF\'', 1)[1].split("\nEOF", 1)[0]


def test_kwin_is_fluid_not_rigid():
    k = _kwinrc()
    for key in ("blurEnabled=true", "contrastEnabled=true", "overviewEnabled=true", "wobblywindowsEnabled=false",
                "saint-starEnabled=true", "BorderSize=None", "Number=4"):
        assert f"\n{key}" in k, key
    assert "magiclampEnabled=true" not in k          # minimise is saint-star's (core/window_anim.py)


def test_breeze_kdeglobals_fonts_and_packages():
    breeze = (FS / "etc/xdg/breezerc").read_text(encoding="utf-8")
    assert "MenuOpacity=" in breeze and "ShadowSize=ShadowLarge" in breeze
    kg = (FS / "etc/xdg/kdeglobals").read_text(encoding="utf-8")
    assert "font=Inter,10," in kg and "fixed=JetBrains Mono," in kg and "AnimationDurationFactor=0.85" in kg
    assert "AccentColor=254,170,52" in kg                                 # one accent, the SAINT amber
    pkgs = (ROOT / "packaging/arch/profile/packages.x86_64").read_text(encoding="utf-8").split()
    assert "inter-font" in pkgs and "ttf-jetbrains-mono" in pkgs
    branding = (ROOT / "packaging/arch/pkgbuilds/halo-branding/PKGBUILD").read_text(encoding="utf-8")
    assert "ksplashrc,breezerc}" in branding
    for lnf in ("org.saintos.desktop", "org.saintos.desktop.light"):
        assert "BorderSize=None" in (FS / f"usr/share/plasma/look-and-feel/{lnf}/contents/defaults").read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("node"), reason="node isn't installed")
def test_update_script_floats_the_taskbar():
    harness = """
const vm = require('vm');
const ps = [{location: 'bottom', height: 36, floating: false}, {location: 'left', height: 30, floating: false},
            {location: 'top', height: 52, floating: false}];
vm.runInNewContext(__SOURCE__, {panels: () => ps});
console.log(JSON.stringify(ps));
"""
    code = harness.replace("__SOURCE__", json.dumps((UPDATES / "saintos-look-1.js").read_text(encoding="utf-8")))
    res = subprocess.run([shutil.which("node"), "-e", code], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    bottom, left, top = json.loads(res.stdout)
    assert bottom == {"location": "bottom", "height": 44, "floating": True}
    assert left["floating"] is False and top == {"location": "top", "height": 52, "floating": True}
