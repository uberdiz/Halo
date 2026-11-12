"""Settings > What SAINT may do: trust per category is shown and saved, and the log can undo."""
import os

import pytest

from core import actions
from core.actions import Action, ActionLog, ActionResult, P, executor, log as log_mod, registry, trust
from core.config import config


@pytest.fixture
def page(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    old = config.get("actions.trust", {})
    config.set("actions.trust", {}, persist=False)
    monkeypatch.setattr(trust, "set_level", lambda c, l, persist=True, _real=trust.set_level: _real(c, l, persist=False))
    state = {"v": 1}

    def run(p):
        before, state["v"] = state["v"], p["v"]
        return ActionResult(True, f"Value is {p['v']}.", undo={"v": before})
    registry.register(Action("testpage.value.set", "Set the value", run, {"v": P("integer")},
                             undo=lambda t: state.update(v=t["v"]) or "Put back."), replace=True)
    from ui.settings_pages import ai_control
    yield ai_control.AIControlPage(), state
    registry.unregister("testpage.value.set")
    config.set("actions.trust", old, persist=False)


def test_the_page_is_discovered_under_saint():
    from ui import settings_pages
    mods = {m.TITLE: m for m in settings_pages.discover()}
    assert "What SAINT may do" in mods and mods["What SAINT may do"].GROUP == "SAINT"


def test_every_category_has_a_plainly_named_trust_choice(page):
    p, _ = page
    from ui.settings_pages import ai_control
    assert {"settings", "files", "shell", "power", "packages", "network"} <= set(p.boxes)
    assert all(c in ai_control.CATEGORY_LABEL for c in p.boxes if c != "testpage")
    box = p.boxes["shell"]
    assert [box.itemText(i) for i in range(box.count())] == ["Ask every time", "Ask for risky", "Trusted"]
    assert box.currentData() == "ask_risky"                                # the default
    box.setCurrentIndex(0)
    assert trust.get_level("shell") == "ask" and "asks before every action" in p.said.text()


def test_the_log_lists_what_ran_and_undo_puts_it_back(page):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    p, state = page
    assert "Nothing yet" in p.log.item(0).text() and not p.undo_btn.isEnabled()
    assert actions.execute("testpage.value.set", {"v": 7}, source="saint").ok
    QApplication.processEvents()                                            # the page follows the event bus
    assert p.log.count() == 1 and "SAINT: Set the value  (done)" in p.log.item(0).text()
    p.log.setCurrentRow(0)
    assert p.undo_btn.isEnabled()
    p._undo()
    assert state["v"] == 1 and "(undone)" in p.log.item(0).text()
    p.log.setCurrentRow(0)
    assert not p.undo_btn.isEnabled() and p.log.item(0).data(Qt.UserRole) == ""
