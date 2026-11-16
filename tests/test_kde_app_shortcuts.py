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
