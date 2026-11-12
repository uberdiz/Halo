"""The curated Windows-app table and the migration wizard's app step (matching, filters, counts)."""
import os

import pytest

from core import app_match
from core import windows_migration as wm


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_table_is_big_enough_and_well_formed():
    import json
    apps = json.loads(app_match.MAP_PATH.read_text(encoding="utf-8"))["apps"]
    assert len(apps) >= 150
    for e in apps:
        assert e["kind"] in app_match.KINDS, e
        for t in e.get("targets", []):
            assert t.split(":", 1)[0] in ("featured", "repo", "flatpak", "aur", "winget", "url"), (e["name"], t)
        if e["kind"] == "native":
            assert e.get("targets") or e.get("why"), e["name"]


@pytest.mark.parametrize("name", ["Antigravity", "Google Antigravity", "Antigravity (User)"])
def test_antigravity_is_native(name):
    hit = app_match.lookup(name)
    assert hit is not None and hit.kind == "native" and hit.store_target() == ("aur", "antigravity-bin")
    assert hit.link().startswith("https://")


@pytest.mark.parametrize("name, kind", [
    ("Google Chrome", "native"), ("Mozilla Firefox", "native"), ("Brave", "native"), ("Steam", "native"),
    ("Discord", "native"), ("Spotify", "native"), ("VLC media player", "native"), ("OBS Studio", "native"),
    ("Visual Studio Code", "native"), ("Blender", "native"), ("GIMP", "native"), ("Audacity", "native"),
    ("Zoom", "native"), ("Slack", "native"), ("Telegram Desktop", "native"), ("qBittorrent", "native"),
    ("7-Zip", "native"), ("Git", "native"), ("Docker Desktop", "native"), ("LibreOffice", "native"),
])
def test_well_known_apps_have_linux_versions(name, kind):
    hit = app_match.lookup(name)
    assert hit is not None, name
    assert hit.kind == kind, (name, hit.kind)


@pytest.mark.parametrize("name", ["NVIDIA Graphics Driver", "Microsoft Visual C++ 2015-2022 Redistributable (x64)",
                                  "Intel(R) Chipset Device Software", "Realtek Audio Driver",
                                  "Microsoft Edge WebView2 Runtime", "Microsoft .NET Runtime - 8.0.4 (x64)"])
def test_drivers_and_runtimes_are_not_counted_as_failures(name):
    hit = app_match.lookup(name)
    assert hit is not None and hit.kind == "not_needed", name


def test_versions_and_architecture_do_not_stop_a_match():
    assert app_match.plain("7-Zip 24.08 (x64)") == "7-zip"
    assert app_match.lookup("Git version 2.45.1").kind == "native"
    assert app_match.lookup("Some Tool Nobody Has Heard Of") is None


def test_match_apps_uses_the_table_before_the_store():
    calls = []

    def search(q, sources=()):
        calls.append(q)
        return []

    names = ["Antigravity", "NVIDIA Control Panel", "NVIDIA PhysX", "Adobe Photoshop 2024", "Obscure Tool"]
    out = {m.windows_name: m for m in wm.match_apps(names, search, curated=app_match.lookup)}
    assert out["Antigravity"].kind == "native" and out["Antigravity"].result.source == "aur"
    assert out["Antigravity"].confidence >= 0.9 and out["Antigravity"].why
    assert sum(m.kind == "not_needed" for m in out.values()) == 1          # both NVIDIA rows are one row
    assert out["Adobe Photoshop 2024"].kind in ("alternative", "none", "wine") and out["Adobe Photoshop 2024"].why
    assert out["Obscure Tool"].kind == "none"
    assert set(calls) == {"Obscure Tool"}                                   # only the unknown one hit the network
    assert wm.match_counts(list(out.values()))["native"] == 1


def test_apps_step_filters_counts_and_ticks(qapp):
    from PySide6.QtCore import Qt
    from core.store import Result
    from ui.settings_pages import migrate_windows as mw
    page = mw.MigratePage()
    page.show_matches([
        wm.AppMatch("Obscure"),
        wm.AppMatch("Notepad++", Result("windows", "n", "Notepad++"), "wine"),
        wm.AppMatch("NVIDIA software", None, "not_needed", "HalOS installs the driver itself."),
        wm.AppMatch("VS Code", Result("featured", "vscode", "VS Code"), "native"),
        wm.AppMatch("Antigravity", Result("aur", "antigravity-bin", "Google Antigravity"), "native"),
    ])
    texts = [page.app_list.item(i).text() for i in range(page.app_list.count())]
    assert texts[0].startswith("Antigravity") and texts[1].startswith("VS Code")      # what works comes first
    labels = [page.app_filter.itemText(i) for i in range(page.app_filter.count())]
    assert labels == ["All apps (5)", "Works on HalOS (2)", "Works with Wine or Proton (1)", "No match (1)",
                      "Not needed (1)"]
    page.app_filter.setCurrentIndex(1)
    assert [page.app_list.item(i).isHidden() for i in range(5)] == [False, False, True, True, True]
    page.app_filter.setCurrentIndex(0)
    page.app_search.setText("note")
    assert [not page.app_list.item(i).isHidden() for i in range(5)].count(True) == 1
    assert "3 of 4 apps work on HalOS" in page.status.text() and "1 drivers" in page.status.text()
    page.app_list.item(0).setCheckState(Qt.Unchecked)
    page._tick_working()
    assert page.app_list.item(0).checkState() == Qt.Checked and page.app_list.item(2).checkState() == Qt.Unchecked


def test_a_job_shows_it_started_at_once(qapp, monkeypatch):
    from ui.settings_pages import migrate_windows as mw
    page = mw.MigratePage()
    started = []
    monkeypatch.setattr(mw, "run_async", lambda fn, done, failed: started.append((fn, done, failed)))
    page._job(lambda: 1, lambda r: None)
    assert page.status.text() == "Working…" and page.bar.maximum() == 0 and not page.bar.isHidden()
    started[0][1](1)
    assert page.bar.isHidden() and page.bar.maximum() == 100
