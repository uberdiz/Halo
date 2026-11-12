"""Quick settings: built from the action registry, every control runs the real action (logged, undoable), and plain
requests in the search box become one button."""
import os
import sys

import pytest

from core import actions
from core.actions import ActionLog, executor, log as log_mod, proc


@pytest.fixture
def page(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    calls = []
    monkeypatch.setattr(proc, "run", lambda argv, **kw: calls.append(list(argv)) or "")
    monkeypatch.setattr(proc, "try_run", lambda argv, default="", timeout=15: default)
    from ui.settings_pages import quick_settings
    p = quick_settings.QuickSettingsPage(confirm=lambda req: True)
    p.calls, p.log = calls, fresh
    return p


def test_rows_come_from_the_registry_under_plain_headings(page):
    ids = {r.action.id for r in page.rows}
    assert {"settings.appearance.theme", "settings.sound.volume", "network.wifi.power", "settings.power.profile"} <= ids
    assert set(page.headings) >= {"Display", "Look", "Sound", "Power", "Network"}
    assert not any(i.startswith(("files.", "shell.", "power.")) for i in ids)          # not settings


def test_apply_runs_the_real_action_and_logs_it(page):
    row = next(r for r in page.rows if r.action.id == "settings.power.profile")
    row.readers["profile"] = lambda: "performance"
    result = row.run()
    assert result.ok and ["powerprofilesctl", "set", "performance"] in page.calls
    assert page.log.entries()[0]["source"] == "gui" and row.said.text()


def test_search_filters_and_a_known_phrase_is_one_button(page):
    page.search.setText("dark mode")
    assert page.suggestion.count() == 1
    suggestion = page.suggestion.itemAt(0).widget()
    assert suggestion.action.id == "settings.appearance.theme" and suggestion.params() == {"mode": "dark"}
    assert "dark theme" in suggestion.apply.text()
    page.search.setText("bluetooth")
    visible = [r.action.id for r in page.rows if not r.isHidden()]
    assert visible == ["network.bluetooth.power"] and page.suggestion.count() == 0
    page.search.setText("")
    assert all(not r.isHidden() for r in page.rows)


def test_the_page_is_first_in_halos_settings():
    from ui import settings_pages
    mods = settings_pages.discover()
    assert mods[0].TITLE == "Quick settings" and getattr(mods[0], "GROUP", "HalOS") != "SAINT"
