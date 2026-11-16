"""SAINT's own global shortcuts (Alt+`, Meta+N, Meta+A) are added back to an older account and work at once."""

from core import kde_desktop


def test_missing_shortcuts_added_old_note_key_freed_and_kglobalaccel_restarted(monkeypatch):
    cfg = {"services/saint-overlay.desktop": {"_launch": "Alt+`"},
           "services/halos-note.desktop": {"_launch": "Meta+N"}}
    monkeypatch.setattr(kde_desktop, "available", lambda: True)
    monkeypatch.setattr(kde_desktop, "read_config", lambda name, dirs=None: cfg)
    monkeypatch.setattr(kde_desktop, "_install_note_launcher", lambda: True)
    ran = []
    kde_desktop.ensure_app_shortcuts(run=lambda argv: ran.append(argv) or (True, ""))
    flat = [" ".join(a) for a in ran]
    assert any("halos-note.desktop" in a and "--delete" in a for a in flat)
    assert any("saint-note.desktop" in a and a.endswith("Meta+N") for a in flat)
    assert not any("saint-overlay.desktop" in a for a in flat)          # set already: left alone
    assert ran[-1] == ["systemctl", "--user", "restart", "plasma-kglobalaccel.service"]


def test_nothing_missing_nothing_restarted(monkeypatch):
    cfg = {f"services/{d}": {"_launch": k} for d, k in kde_desktop.APP_SHORTCUTS}
    monkeypatch.setattr(kde_desktop, "available", lambda: True)
    monkeypatch.setattr(kde_desktop, "read_config", lambda name, dirs=None: cfg)
    ran = []
    assert kde_desktop.ensure_app_shortcuts(run=lambda argv: ran.append(argv) or (True, "")) == []
    assert ran == []


def test_taskbar_height_and_edge_read_and_set_live():
    ran = []

    def run(argv):
        ran.append(argv)
        return True, "44 bottom"
    assert kde_desktop.panel(run) == (44, "bottom")
    assert kde_desktop.set_panel(500, "top", run)
    script = ran[-1][-1]
    assert ran[-1][1:4] == ["org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript"]
    assert 'p.location = "top"' in script and f"p.height = {kde_desktop.PANEL_MAX}" in script     # clamped
    import pytest
    with pytest.raises(ValueError):
        kde_desktop.set_panel(40, "middle", run)
    assert kde_desktop.panel(lambda a: (False, "")) == (0, "")
