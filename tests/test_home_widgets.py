"""Home (Overview) widgets: reminder buckets + snooze, task groups, quick actions, panels build."""
import os
import time
from datetime import datetime
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.pages import overview as ov


def test_bucket_reminders():
    now = datetime(2026, 11, 12, 12, 0).timestamp()
    autos = [NS(status="missed", next_run=None), NS(status="active", next_run=now - 60),
             NS(status="active", next_run=now + 3600), NS(status="active", next_run=now + 86400 * 2),
             NS(status="cancelled", next_run=now + 10)]
    b = ov.bucket_reminders(autos, now)
    assert [len(b[k]) for k in ("overdue", "today", "upcoming")] == [2, 1, 1]


def test_snooze_brings_back_missed_reminder(tmp_path, monkeypatch):
    from modules.automation import scheduler as sch
    s = sch.Scheduler()
    monkeypatch.setattr(s, "_store", sch.AutomationStore(str(tmp_path / "a.db")), raising=False)
    monkeypatch.setattr(type(s), "store", property(lambda self: self._store))
    a = s.create("reminder", "stretch", {"type": "once", "at": time.time() + 60})
    a.status = sch.MISSED
    s.store.save(a)
    b = s.snooze(a.id, 10)
    assert b.status == sch.ACTIVE and abs(b.next_run - time.time() - 600) < 5 and b.schedule["type"] == "once"
    s.cancel(a.id)
    assert s.snooze(a.id, 10) is None


def test_task_groups():
    ts = [NS(status="executing"), NS(status="waiting_for_user"), NS(status="paused"), NS(status="failed"),
          NS(status="completed")]
    g = ov.task_groups(ts)
    assert [len(g[k]) for k in ("active", "pending", "failed")] == [1, 2, 1]


def test_quick_actions_run_real_targets(monkeypatch):
    calls = []
    shell = NS(navigate=lambda n: calls.append(("page", n)))
    monkeypatch.setattr(ov, "open_system_overview", lambda: calls.append(("system",)))
    ov.run_quick("page:Tasks", shell)
    ov.run_quick("system", shell)
    assert calls == [("page", "Tasks"), ("system",)]
    assert ov.quick_label("app:firefox") == "Open firefox" and ov.quick_label("system") == "System Overview"


def test_panels_build_and_quick_actions_persist(monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.config import config
    store = {}
    monkeypatch.setattr(config, "get", lambda k, d=None: store.get(k, d))
    monkeypatch.setattr(config, "set", lambda k, v, persist=True: store.__setitem__(k, v))
    shell = NS(navigate=lambda n: None, page_map={"Overview": 1, "Tasks": 2, "Music": 3})
    q = ov.QuickActionsPanel(shell)
    assert q.grid.count() == len(ov.DEFAULT_QUICK)
    q._save(["page:Music"])
    assert store["layout.quick_actions"] == ["page:Music"] and q.grid.count() == 1
    assert [a.text() for a in q._add_menu().actions() if a.text()][:2] == ["System Overview", "Tasks"]
    r = ov.RemindersPanel()
    r._show({"overdue": [NS(id="x", title="stretch", recurring=False, next_run=None)], "today": [], "upcoming": []})
    assert r.hint.text() == "1 overdue"
    t = ov.TasksPanel(shell)
    t.refresh()
    s = ov.SystemSummaryPanel()
    s._show(ov.system_summary())
    assert "CPU" in s.text.text()
    assert {"reminders", "quick", "tasks", "summary"} <= {k for k, _t, _c in ov.PANELS}
