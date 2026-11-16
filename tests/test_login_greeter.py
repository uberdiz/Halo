"""Login: SDDM's greeter runs on KWin Wayland (no X server, no VT switch + mode-set to black before Plasma)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_sddm_greeter_is_kwin_wayland_with_layer_shell():
    pkg = (ROOT / "packaging/arch/pkgbuilds/halo-branding/PKGBUILD").read_text(encoding="utf-8")
    conf = pkg[pkg.index("etc/sddm.conf.d/10-halo.conf"):]
    conf = conf[:conf.index("\nEOF")]
    assert "DisplayServer=wayland" in conf and "Current=breeze" in conf
    assert "CompositorCommand=kwin_wayland --drm" in conf
    assert "QT_WAYLAND_SHELL_INTEGRATION=layer-shell" in conf
    pkgs = (ROOT / "packaging/arch/profile/packages.x86_64").read_text(encoding="utf-8").split()
    assert "layer-shell-qt" in pkgs and "sddm" in pkgs
