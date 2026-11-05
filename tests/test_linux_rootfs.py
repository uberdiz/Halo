"""
Linux files shared by the Halo OS image (packaging/linux/rootfs, branding): static checks that run on any
OS. They catch a desktop entry KDE would reject, a unit file typo or a script that would fail on CRLF
line endings — before a long image build does. (The Fedora/KIWI SAINTOS image these were first written
for was removed; it lives on at the tag saintos-fedora-0.1.0.)
"""

import configparser
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FS = ROOT / "packaging" / "linux" / "rootfs"


@pytest.mark.parametrize("name", ["saint.desktop", "saintos-control.desktop"])
def test_desktop_entries(name):
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read(FS / "usr" / "share" / "applications" / name, encoding="utf-8")
    e = cp["Desktop Entry"]
    assert e["Type"] == "Application" and e["Name"] and e["Icon"]
    assert e["Exec"].split()[0].startswith("/usr/bin/")
    assert (FS / e["Exec"].split()[0].lstrip("/")).exists(), "Exec points at a file the image doesn't ship"
    assert e["Categories"].endswith(";")


def test_units_reference_shipped_files():
    for unit in (FS / "usr" / "lib" / "systemd").rglob("*.service"):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        cp.read(unit, encoding="utf-8")
        exe = cp["Service"]["ExecStart"].split()[0]
        assert (FS / exe.lstrip("/")).exists(), f"{unit.name}: {exe} isn't in the rootfs"
        assert "WantedBy" in cp["Install"]
    user = (FS / "usr/lib/systemd/user/saint.service").read_text()
    assert "User=" not in user and "sudo" not in user                       # user service, no root


def test_scripts_are_lf_with_shebang():
    scripts = [p for p in (FS / "usr" / "bin").iterdir()] + [p for p in (FS / "usr" / "libexec" / "saintos").iterdir()]
    for s in scripts:
        data = s.read_bytes()
        assert data.startswith(b"#!"), s.name
        assert b"\r\n" not in data, f"{s.name} has CRLF line endings"


def test_gitattributes_keep_image_files_lf():
    attrs = (ROOT / ".gitattributes").read_text()
    assert "packaging/linux/rootfs/** text eol=lf" in attrs and "packaging/arch/** text eol=lf" in attrs


def test_fedora_pipeline_is_gone():
    assert not (ROOT / "packaging/linux/image").exists()
    assert not (ROOT / ".github/workflows/saintos-image.yml").exists()


def test_wallpaper_metadata_and_plasma_script():
    meta = json.loads((FS / "usr/share/wallpapers/SAINTOS/metadata.json").read_text())
    assert meta["KPlugin"]["Id"] == "SAINTOS"
    js = (FS / "usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/saintos-defaults.js").read_text()
    assert "/usr/share/wallpapers/SAINTOS/" in js and "saint.desktop" in js


def test_branding_generator_runs(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    import importlib.util
    spec = importlib.util.spec_from_file_location("mb", ROOT / "packaging/linux/branding/make_branding.py")
    mb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mb)
    mb.WALLPAPER_SIZES = [(640, 360)]
    assert mb.main(["x", str(tmp_path)]) == 0
    assert Image.open(tmp_path / "wallpaper" / "SAINTOS-640x360.png").size == (640, 360)
    assert Image.open(tmp_path / "logo" / "saintos-logo-256.png").mode == "RGBA"
    assert (tmp_path / "plymouth" / "watermark.png").exists()


def test_boot_report_selftest_is_offline():
    text = (FS / "usr/libexec/saintos/boot-report").read_text()
    assert "SAINT_SELFTEST_NO_VOICE=1" in text, "the boot test must not download voice models"
    assert "SAINT_DATA_DIR=" in text and "timeout " in text
