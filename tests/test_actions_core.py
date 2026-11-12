"""The OS action registry: validation, trust gating, confirmation, log + undo, plans, and SAINT's bridge."""
import pytest

from core import actions
from core.actions import (ASK, ASK_RISKY, DESTRUCTIVE, RISKY, SAFE, TRUSTED, Action, ActionLog, ActionResult, P,
                          Plan, Registry, execute, registry)
from core.actions import executor, log as log_mod, trust
from core.config import config
from core.events import EventType, event_bus


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    """A private log, default trust, and three throwaway actions (one per risk)."""
    fresh = ActionLog(tmp_path / "log.jsonl")
    monkeypatch.setattr(log_mod, "action_log", fresh)
    monkeypatch.setattr(executor, "action_log", fresh)
    monkeypatch.setattr(actions, "action_log", fresh)
    old = config.get("actions.trust", {})
    config.set("actions.trust", {}, persist=False)
    state = {"value": 1, "ran": []}

    def setter(p):
        before, state["value"] = state["value"], p["value"]
        state["ran"].append(p["value"])
        return ActionResult(True, f"Value is {p['value']}.", undo={"value": before})

    def unset(t):
        state["value"] = t["value"]
        return "Put it back."

    for risk in (SAFE, RISKY, DESTRUCTIVE):
        registry.register(Action(f"testcat.{risk}.set", f"Set ({risk})", setter,
                                 {"value": P("integer", minimum=0, maximum=10),
                                  "password": P("string", required=False, secret=True)},
                                 risk=risk, undo=unset, preview=lambda p: f"Set the value to {p['value']}."),
                          replace=True)
    yield state, fresh
    for risk in (SAFE, RISKY, DESTRUCTIVE):
        registry.unregister(f"testcat.{risk}.set")
    config.set("actions.trust", old, persist=False)


# --------------------------------------------------------------------------- registry
def test_bad_ids_risks_and_params_are_refused():
    with pytest.raises(ValueError):
        Action("nodots", "x", lambda p: None)
    with pytest.raises(ValueError):
        Action("a.b", "x", lambda p: None, risk="spicy")
    with pytest.raises(ValueError):
        Action("a.b", "x", lambda p: None, params={"n": "integer"})


def test_validation_coerces_and_rejects(clean):
    a = registry.get("testcat.safe.set")
    assert a.validate({"value": "7"}) == {"value": 7}
    for bad in ({}, {"value": 11}, {"value": "many"}, {"value": 1, "extra": 2}):
        r = execute("testcat.safe.set", bad)
        assert not r.ok and r.code == "INVALID_PARAMS", bad
    assert execute("nope.nothing").code == "UNKNOWN_ACTION"


def test_search_and_compact_tool_specs():
    actions.load_builtin()
    ids = [a.id for a in registry.search("make the sound louder", platform=None)]
    assert "settings.sound.volume" in ids
    spec = registry.get("settings.sound.volume").to_tool_spec()
    assert spec["name"] == "settings.sound.volume" and "parameters" in spec
    assert all(set(s) <= {"name", "description", "parameters", "risk"} for s in registry.to_tool_specs())


# --------------------------------------------------------------------------- trust
@pytest.mark.parametrize("level, risk, asks", [
    (ASK, SAFE, True), (ASK, RISKY, True), (ASK, DESTRUCTIVE, True),
    (ASK_RISKY, SAFE, False), (ASK_RISKY, RISKY, True), (ASK_RISKY, DESTRUCTIVE, True),
    (TRUSTED, SAFE, False), (TRUSTED, RISKY, False), (TRUSTED, DESTRUCTIVE, True),
])
def test_trust_levels_gate_each_risk(clean, level, risk, asks):
    state, _ = clean
    trust.set_level("testcat", level, persist=False)
    r = execute(f"testcat.{risk}.set", {"value": 5}, source="saint")
    assert r.needs_confirmation is asks
    assert (state["ran"] == []) is asks                     # nothing ran while it waits for a yes
    if asks:
        assert "Set the value to 5" in r.preview


def test_confirm_callback_yes_no_and_broken(clean):
    state, _ = clean
    seen = []
    yes = execute("testcat.destructive.set", {"value": 2}, confirm=lambda req: seen.append(req) or True)
    assert yes.ok and state["value"] == 2 and seen[0].preview == "Set the value to 2." and seen[0].risk == DESTRUCTIVE
    no = execute("testcat.destructive.set", {"value": 3}, confirm=lambda req: False)
    assert no.code == "DECLINED" and state["value"] == 2

    def broken(_req):
        raise RuntimeError("dialog crashed")
    assert execute("testcat.destructive.set", {"value": 4}, confirm=broken).code == "DECLINED"
    assert state["value"] == 2


def test_safe_automation_mode_blocks_saint_but_not_the_users_own_click(clean, monkeypatch):
    old = config.get("automation.permission_mode", "confirm")
    config.set("automation.permission_mode", "safe", persist=False)
    try:
        assert execute("testcat.risky.set", {"value": 1}, source="saint").code == "DENIED"
        assert execute("testcat.risky.set", {"value": 1}, source="gui", confirm=lambda r: True).ok
    finally:
        config.set("automation.permission_mode", old, persist=False)


# --------------------------------------------------------------------------- log and undo
def test_log_redacts_secrets_and_undo_restores(clean):
    state, log = clean
    r = execute("testcat.safe.set", {"value": 9, "password": "hunter2"})
    assert r.ok and state["value"] == 9
    assert "hunter2" not in log.path.read_text(encoding="utf-8")
    entry = log.entries()[0]
    assert entry["can_undo"] and entry["action"] == "testcat.safe.set"
    back = log.undo_last()
    assert back.ok and state["value"] == 1
    assert log.undo(entry["id"]).code == "ALREADY_UNDONE"
    assert log.undo_last().code == "NOTHING_TO_UNDO"


def test_events_tell_a_ui_what_is_happening(clean):
    seen = []
    kinds = [EventType.ACTION_REQUESTED, EventType.ACTION_STARTED, EventType.ACTION_DONE]
    handler = lambda e: seen.append(e.type) if e.type in kinds else None
    event_bus.subscribe(handler)
    try:
        execute("testcat.safe.set", {"value": 3})
    finally:
        event_bus.unsubscribe(handler)
    assert seen == kinds


# --------------------------------------------------------------------------- plans
def test_plan_runs_in_order_pauses_for_a_yes_and_stops_on_failure(clean):
    state, _ = clean
    plan = Plan("Three steps").add("testcat.safe.set", {"value": 2}).add("testcat.destructive.set", {"value": 3}) \
                              .add("testcat.safe.set", {"value": 4})
    waiting = plan.run()
    assert waiting.needs_confirmation and plan.status == "waiting" and state["ran"] == [2]
    done = plan.resume(True)
    assert done.ok and state["ran"] == [2, 3, 4] and [s.status for s in plan.steps] == ["done"] * 3

    bad = Plan("Fails in the middle").add("testcat.safe.set", {"value": 1}).add("testcat.safe.set", {"value": 99}) \
                                     .add("testcat.safe.set", {"value": 5})
    out = bad.run()
    assert not out.ok and [s.status for s in bad.steps] == ["done", "failed", "skipped"]
    assert "step 2 of 3" in out.error and state["ran"][-1] == 1


def test_plan_declined_step_skips_the_rest(clean):
    state, _ = clean
    plan = Plan("No thanks").add("testcat.destructive.set", {"value": 8}).add("testcat.safe.set", {"value": 9})
    plan.run()
    out = plan.resume(False)
    assert out.code == "DECLINED" and state["ran"] == [] and plan.steps[1].status == "skipped"


# --------------------------------------------------------------------------- SAINT's bridge
def test_saint_bridge_finds_runs_and_parks_confirmations(clean):
    from core.actions import saint
    from modules.agent.confirm import confirmations
    from modules.automation.tools import ToolError
    state, _ = clean
    assert any(a["name"] == "settings.sound.volume" for a in saint.find("volume louder")["actions"])
    assert saint.run("testcat.safe.set", {"value": 6})["ok"] and state["value"] == 6
    parked = saint.run("testcat.destructive.set", {"value": 7})
    assert parked["needs_confirmation"] and state["value"] == 6
    pending = confirmations.take() if hasattr(confirmations, "take") else confirmations._pending
    assert pending and pending.run() == "Value is 7." and state["value"] == 7
    confirmations._pending = None
    with pytest.raises(ToolError):
        saint.run("testcat.safe.set", {"value": 500})
    assert saint.undo()["ok"] and state["value"] == 6


def test_search_does_not_match_a_short_keyword_inside_a_longer_word():
    actions.load_builtin()
    ids = [a.id for a in registry.search("bluetooth", platform=None)]
    assert ids[0] == "network.bluetooth.power" and "settings.display.night_light" not in ids
    assert "settings.display.brightness" in [a.id for a in registry.search("brighter", platform=None)]
