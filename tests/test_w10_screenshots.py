"""Screenshots on HalOS: capture tools never get SAINT's window animations or burst, and Spectacle saves to
Pictures/Screenshots and quits after a copy or save instead of flashing its editor."""
import configparser
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FS = ROOT / "packaging/linux/rootfs"
STAR = (FS / "usr/share/kwin/effects/saint-star/contents/code/main.js").read_text(encoding="utf-8")
SHELL = (FS / "usr/share/kwin/scripts/saint-shell/contents/code/main.js").read_text(encoding="utf-8")


def _capture_regex(js: str) -> re.Pattern:
    m = re.search(r"CAPTURE = /(.+?)/i", js)
    assert m, "no CAPTURE list"
    return re.compile(m.group(1), re.I)


def test_capture_tools_are_left_out_of_animations_and_burst():
    for js in (STAR, SHELL):
        rx = _capture_regex(js)
        for cls in ("spectacle org.kde.spectacle", "org.kde.spectacle", "flameshot", "xdg-desktop-portal-kde"):
            assert rx.search(cls), cls
        for cls in ("dolphin org.kde.dolphin", "firefox", "saint"):
            assert not rx.search(cls), cls
    assert "!CAPTURE.test(String(w.windowClass" in STAR          # in eligible(): no open/close animation
    assert "CAPTURE.test(String(w.resourceClass" in SHELL        # in windowRemoved: no burst


def test_spectacle_defaults_ship_and_are_installed():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(FS / "etc/xdg/spectaclerc", encoding="utf-8")
    assert cfg["General"]["autoSaveImage"] == "true"
    assert cfg["General"]["clipboardGroup"] == "PostScreenshotCopyImage"
    assert cfg["GuiConfig"]["quitAfterSaveCopyExport"] == "true"
    pkgbuild = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert '"$fs/etc/xdg/spectaclerc" "$pkgdir/etc/xdg/spectaclerc"' in pkgbuild
