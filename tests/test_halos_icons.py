"""The HalOS icon theme: every icon is valid SVG, the theme index lists its folders, the main logos aren't
replaced, and HalOS uses it by default (dark and light)."""
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "packaging/linux/rootfs/usr/share/icons/HalOS"


def test_every_icon_is_valid_svg_and_listed():
    icons = list(THEME.glob("scalable/*/*.svg"))
    assert len(icons) >= 75
    for f in icons:
        root = ET.fromstring(f.read_text(encoding="utf-8"))
        assert root.tag.endswith("svg") and root.get("viewBox") == "0 0 64 64", f.name
    index = (THEME / "index.theme").read_text(encoding="utf-8")
    for d in {f.parent.name for f in icons}:
        assert f"scalable/{d}" in index and f"[scalable/{d}]" in index
    assert "Inherits=breeze-dark,breeze,hicolor" in index


def test_logos_are_not_redrawn():
    names = {f.stem for f in THEME.glob("scalable/*/*.svg")}
    assert not names & {"saint", "halo", "halos", "aide", "firefox", "steam", "com.spotify.Client", "discord"}


def test_halos_uses_it_by_default():
    lnf = ROOT / "packaging/linux/rootfs/usr/share/plasma/look-and-feel"
    assert "[kdeglobals][Icons]\nTheme=HalOS\n" in (lnf / "org.saintos.desktop/contents/defaults").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "Theme=HalOS-light" in (lnf / "org.saintos.desktop.light/contents/defaults").read_text(encoding="utf-8")
    assert "Inherits=breeze,hicolor" in (THEME.parent / "HalOS-light/index.theme").read_text(encoding="utf-8")
    pkg = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert 'cp -a "$fs/usr/share/icons/HalOS"' in pkg and 'ln -s ../HalOS/scalable' in pkg
