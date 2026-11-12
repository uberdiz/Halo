"""The plan panel: a multi-step command shows its steps live, and never takes focus or clicks."""
import os

import pytest

from core.events import EventType


@pytest.fixture
def panel(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui import motion, plan_panel
    monkeypatch.setattr(motion, "enabled", lambda: False)
    p = plan_panel.PlanPanel()
    yield p
    p.close()


def _steps(*statuses):
    return [{"index": i, "action": f"a.b{i}", "title": f"Step {i + 1}", "status": s, "message": ""}
            for i, s in enumerate(statuses)]


def _event(kind, payload):
    return type("Ev", (), {"type": kind, "payload": payload})()


def test_it_follows_a_plan_from_start_to_finish(panel):
    panel._on_event(_event(EventType.PLAN_STARTED, {"plan": "p1", "title": "Movie mode", "steps": _steps("pending", "pending", "pending")}))
    assert panel.isVisible() and panel.title.text() == "Movie mode"
    panel._on_event(_event(EventType.PLAN_STEP, dict(_steps("running")[0], plan="p1", total=3)))
    assert panel._labels[0].text().startswith("●") and "0 of 3 done" in panel.footer.text()
    panel._on_event(_event(EventType.PLAN_STEP, dict(_steps("done")[0], plan="p1", total=3)))
    assert panel._labels[0].text().startswith("✓")
    panel._on_event(_event(EventType.PLAN_DONE, {"plan": "p1", "ok": True, "steps": _steps("done", "done", "done")}))
    assert panel._state == "done" and all(l.text().startswith("✓") for l in panel._labels[:3])
    assert panel._hide.isActive()                                       # it goes away on its own


def test_a_failed_step_says_why_and_the_rest_show_as_skipped(panel):
    panel._on_event(_event(EventType.PLAN_STARTED, {"plan": "p2", "title": "Tidy up", "steps": _steps("pending", "pending", "pending")}))
    steps = _steps("done", "failed", "skipped")
    steps[1]["message"] = "The folder doesn't exist."
    panel._on_event(_event(EventType.PLAN_DONE, {"plan": "p2", "ok": False, "steps": steps,
                                                 "message": "Stopped at step 2 of 3 (Step 2): The folder doesn't exist."}))
    assert panel._state == "failed" and "The folder doesn't exist." in panel._labels[1].text()
    assert panel._labels[2].text().startswith("–") and "Stopped at step 2" in panel.footer.text()


def test_a_step_waiting_for_a_yes_is_shown_as_waiting(panel):
    panel._on_event(_event(EventType.PLAN_STARTED, {"plan": "p3", "title": "Clean up", "steps": _steps("pending", "pending")}))
    waiting = dict(_steps("pending")[0], plan="p3", message="Move report.txt to the trash (it can be restored).")
    panel._on_event(_event(EventType.PLAN_STEP, waiting))
    assert panel._state == "waiting" and "Waiting for your OK" in panel.footer.text()
    assert "Move report.txt" in panel._labels[0].text()


def test_other_plans_single_steps_and_long_plans(panel):
    from ui import plan_panel
    panel._on_event(_event(EventType.PLAN_STARTED, {"plan": "solo", "title": "One thing", "steps": _steps("pending")}))
    assert not panel.isVisible()                                        # one step is the action notice's job
    panel._on_event(_event(EventType.PLAN_STARTED, {"plan": "p4", "title": "Big", "steps": _steps(*["pending"] * 3)}))
    panel._on_event(_event(EventType.PLAN_STEP, dict(_steps("done")[0], plan="someone-else")))
    assert panel._labels[0].text().startswith("○")                      # another plan's event changes nothing
    many = _steps(*(["done"] * 10 + ["running"] + ["pending"] * 9))
    shown = plan_panel.visible_steps(many)
    assert len(shown) == plan_panel.MAX_ROWS and any(s["status"] == "running" for s in shown)


def test_it_never_takes_focus_or_clicks(panel):
    from PySide6.QtCore import Qt
    flags = panel.windowFlags()
    assert flags & Qt.WindowTransparentForInput and flags & Qt.WindowDoesNotAcceptFocus
    assert panel.testAttribute(Qt.WA_ShowWithoutActivating) and panel.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_a_real_plan_drives_it_through_the_event_bus(panel, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from core import actions
    from core.actions import Action, ActionLog, P, Plan, executor, log as log_mod, registry
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    registry.register(Action("testplan.note.add", "Add a note", lambda p: f"Noted {p['n']}.", {"n": P("integer")}),
                      replace=True)
    try:
        plan = Plan("Two notes").add("testplan.note.add", {"n": 1}).add("testplan.note.add", {"n": 2})
        assert plan.run().ok
        QApplication.processEvents()
        assert panel.title.text() == "Two notes" and panel._state == "done"
        assert [l.text()[0] for l in panel._labels[:2]] == ["✓", "✓"]
    finally:
        registry.unregister("testplan.note.add")


def test_halo_progress_goes_clockwise_round_the_edge():
    pytest.importorskip("PySide6")
    from ui.halo import progress_line
    W, H = 1000, 500                                     # perimeter 3000
    assert progress_line("top", 0.0, W, H, 1000, 30).width() == 0
    assert progress_line("top", 1 / 6, W, H, 1000, 30).width() == 500       # half the top
    assert progress_line("right", 1 / 6, W, H, 30, 440).height() == 0       # not round the corner yet
    half = progress_line("right", 0.5, W, H, 30, 440)                       # top and right full
    assert half.height() == 440 and half.x() == 27
    bottom = progress_line("bottom", 2 / 3, W, H, 1000, 30)                 # bottom half done, from the right
    assert bottom.width() == 500 and bottom.right() == 999
    assert progress_line("left", 1.0, W, H, 30, 440).height() == 440


def test_halo_follows_a_plan(panel):
    from ui.halo import Halo
    h = Halo()
    ev = lambda t, p: type("E", (), {"type": t, "payload": p})()
    h._on_event(ev(EventType.PLAN_STARTED, {"plan": "p1", "steps": _steps("pending", "pending", "pending", "pending")}))
    assert h.progress == 0.0
    h._on_event(ev(EventType.PLAN_STEP, {"plan": "p1", "index": 0, "status": "done"}))
    h._on_event(ev(EventType.PLAN_STEP, {"plan": "other", "index": 1, "status": "done"}))
    assert h.progress == 0.25
    h._on_event(ev(EventType.PLAN_DONE, {"plan": "p1", "ok": True}))
    assert h.progress == 1.0 and h._clear.isActive()


def test_highlight_outlines_the_target_without_taking_focus(panel):
    from PySide6.QtCore import Qt
    from ui.act_highlight import ActHighlight, PAD, bounds
    assert bounds([[100, 100, 200, 100], [400, 50, 100, 100]]).getRect() == (100 - PAD, 50 - PAD, 400 + 2 * PAD, 150 + 2 * PAD)
    hl = ActHighlight()
    assert hl.windowFlags() & Qt.WindowTransparentForInput and hl.windowFlags() & Qt.WindowDoesNotAcceptFocus
    hl.show_rects([[10, 20, 0, 0]])                      # nothing real to outline
    assert not hl.isVisible()
    hl.show_rects([[10, 20, 300, 200]])
    assert hl.isVisible() and hl.rects[0].getRect() == (PAD, PAD, 300, 200)
    hl.close()
