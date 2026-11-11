"""
core/actions/executor.py

The one way to run an OS action:

    execute("settings.sound.volume", {"percent": 40}, source="saint", confirm=ask)

validates the parameters, applies the trust level, asks for confirmation with
the preview when needed, runs the action, writes the action log and emits
ACTION_* events so any UI can show live status.

``confirm`` is ``(ConfirmRequest) -> bool``. Without one, an action that
needs a yes is NOT run: the result has ``code == "CONFIRM_REQUIRED"`` and the
preview, and the caller asks the user its own way (a dialog, or SAINT's voice
confirmation in modules/agent/actions_adapter.py) and then calls ``execute``
again with ``confirmed=True``.

``Plan`` runs several actions in order, emitting PLAN_* events with the step
list; it stops at the first failure and says so plainly.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.events import EventType, event_bus

from . import trust
from .log import action_log
from .registry import ActionError, ActionResult, registry

log = logging.getLogger("saint.actions")


@dataclass
class ConfirmRequest:
    action_id: str
    title: str
    preview: str                      # what will happen, e.g. the exact shell command
    risk: str
    category: str
    params: Dict[str, Any]            # secrets redacted
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action_id, "title": self.title, "preview": self.preview, "risk": self.risk,
                "category": self.category, "params": self.params, "source": self.source}


ConfirmCallback = Callable[[ConfirmRequest], bool]

_current = threading.local()


def progress(text: str = "", percent: Optional[int] = None):
    """Called by action code while it runs: emits ACTION_PROGRESS for the
    action currently executing on this thread (a no-op outside ``execute``)."""
    ctx = getattr(_current, "ctx", None)
    if ctx is None:
        return
    payload = dict(ctx, text=text)
    if percent is not None:
        payload["percent"] = max(0, min(100, int(percent)))
    event_bus.emit_event(EventType.ACTION_PROGRESS, payload)


def _coerce_result(out: Any, title: str) -> ActionResult:
    if isinstance(out, ActionResult):
        return out
    if isinstance(out, str):
        return ActionResult(True, message=out)
    if isinstance(out, dict):
        return ActionResult(True, message=str(out.get("message") or f"{title}: done."), data=out)
    return ActionResult(True, message=f"{title}: done.")


def execute(action_id: str, params: Optional[Dict[str, Any]] = None, source: str = "gui",
            confirm: Optional[ConfirmCallback] = None, confirmed: bool = False,
            plan_id: str = "", step: Optional[int] = None) -> ActionResult:
    """Validate, gate, run and log one action. Never raises."""
    from . import load_builtin
    load_builtin()
    if source not in trust.SOURCES:
        return ActionResult(False, error=f"unknown source {source!r}", code="INVALID_PARAMS", action=action_id)
    action = registry.get(action_id)
    if action is None:
        return ActionResult(False, error=f"There's no action called '{action_id}'.", code="UNKNOWN_ACTION",
                            action=action_id)
    ctx: Dict[str, Any] = {"action": action.id, "title": action.title, "category": action.category,
                           "source": source}
    if plan_id:
        ctx.update(plan=plan_id, step=step)

    def fail(error: str, code: str, event=EventType.ACTION_FAILED, **extra) -> ActionResult:
        event_bus.emit_event(event, dict(ctx, error=error, code=code))
        return ActionResult(False, error=error, code=code, action=action.id, **extra)

    if not action.available():
        return fail(f"“{action.title}” isn't available on this system.", "UNAVAILABLE")
    try:
        args = action.validate(params)
    except ActionError as e:
        return fail(f"I can't {action.title[:1].lower() + action.title[1:]}: {e}.", e.code)

    risk = action.risk_for(args)
    preview = action.describe(args)
    shown = action.redact(args)
    ctx["risk"] = risk
    decision = trust.decide(action, risk, source)
    event_bus.emit_event(EventType.ACTION_REQUESTED, dict(ctx, params=shown, preview=preview, decision=decision))

    if decision == trust.DENY:
        result = fail(f"“{action.title}” is blocked by your permission settings.", "DENIED",
                      EventType.ACTION_DENIED, preview=preview, risk=risk)
        result.entry_id = action_log.record(action, args, result, source, risk, plan_id)
        return result
    if decision == trust.CONFIRM and not confirmed:
        request = ConfirmRequest(action.id, action.title, preview, risk, action.category, shown, source)
        event_bus.emit_event(EventType.ACTION_CONFIRM_REQUIRED, dict(ctx, params=shown, preview=preview))
        if confirm is None:
            return ActionResult(False, error=f"This needs your OK first: {preview}", code="CONFIRM_REQUIRED",
                                action=action.id, preview=preview, risk=risk)
        try:
            approved = bool(confirm(request))
        except Exception:
            log.exception("action.confirm_callback_failed %s", action.id)
            approved = False                         # a broken dialog is a "no", never a "yes"
        if not approved:
            result = fail("Okay, I won't.", "DECLINED", EventType.ACTION_DENIED, preview=preview, risk=risk)
            result.entry_id = action_log.record(action, args, result, source, risk, plan_id)
            return result

    event_bus.emit_event(EventType.ACTION_STARTED, dict(ctx, params=shown, preview=preview))
    log.info("action.start %s source=%s risk=%s %s", action.id, source, risk, shown)
    started = time.perf_counter()
    previous = getattr(_current, "ctx", None)
    _current.ctx = ctx
    try:
        result = _coerce_result(action.run(args), action.title)
    except ActionError as e:
        result = ActionResult(False, error=str(e), code=e.code)
    except Exception as e:
        code = getattr(e, "code", None)              # ToolError from wrapped SAINT code
        if code:
            result = ActionResult(False, error=str(e), code=str(code))
        else:
            log.exception("action.error %s", action.id)
            result = ActionResult(False, error=f"{action.title} failed: {e}", code="ERROR")
    finally:
        _current.ctx = previous
    ms = round((time.perf_counter() - started) * 1000, 1)
    if not result.ok and not result.code:
        result.code = "FAILED"
    result.action, result.preview, result.risk = action.id, preview, risk
    if action.undo is None or not result.ok:
        result.undo = None
    result.entry_id = action_log.record(action, args, result, source, risk, plan_id)
    if result.ok:
        log.info("action.ok %s (%.0f ms)", action.id, ms)
        event_bus.emit_event(EventType.ACTION_DONE, dict(ctx, message=result.message, entry_id=result.entry_id,
                                                         can_undo=result.undo is not None, duration_ms=ms))
    else:
        log.info("action.failed %s code=%s %s", action.id, result.code, result.error)
        event_bus.emit_event(EventType.ACTION_FAILED, dict(ctx, error=result.error, code=result.code,
                                                           entry_id=result.entry_id, duration_ms=ms))
    return result


def preview(action_id: str, params: Optional[Dict[str, Any]] = None, source: str = "gui") -> Dict[str, Any]:
    """What ``execute`` would do, without doing it: {"ok", "preview", "risk",
    "decision" (allow|confirm|deny), "error"}."""
    from . import load_builtin
    load_builtin()
    action = registry.get(action_id)
    if action is None:
        return {"ok": False, "error": f"There's no action called '{action_id}'."}
    try:
        args = action.validate(params)
    except ActionError as e:
        return {"ok": False, "error": str(e)}
    risk = action.risk_for(args)
    return {"ok": True, "action": action.id, "title": action.title, "preview": action.describe(args),
            "risk": risk, "decision": trust.decide(action, risk, source), "available": action.available()}


# ---------------------------------------------------------------------- #
# Multi-step plans
# ---------------------------------------------------------------------- #
PENDING, RUNNING, DONE, FAILED, SKIPPED = "pending", "running", "done", "failed", "skipped"


@dataclass
class PlanStep:
    action_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    title: str = ""
    status: str = PENDING
    message: str = ""
    entry_id: str = ""

    def to_dict(self, index: int) -> Dict[str, Any]:
        return {"index": index, "action": self.action_id, "title": self.title, "status": self.status,
                "message": self.message, "entry_id": self.entry_id}


class Plan:
    """An ordered list of actions run one after another.

    ``run(confirm)`` returns the plan's ActionResult. If a step needs a yes
    and there is no ``confirm`` callback the plan pauses (``status ==
    "waiting"``, result code CONFIRM_REQUIRED, the step stays pending); call
    ``resume(approved=True)`` to carry on or ``resume(approved=False)`` to stop."""

    def __init__(self, title: str, source: str = "saint", steps: Optional[List[PlanStep]] = None):
        self.id = uuid.uuid4().hex[:10]
        self.title = title
        self.source = source
        self.steps: List[PlanStep] = list(steps or [])
        self.status = PENDING              # pending | running | waiting | done | failed
        self.message = ""
        self._confirm: Optional[ConfirmCallback] = None

    def add(self, action_id: str, params: Optional[Dict[str, Any]] = None, title: str = "") -> "Plan":
        if not title:
            action = registry.get(action_id)
            title = action.title if action else action_id
        self.steps.append(PlanStep(action_id, dict(params or {}), title))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {"plan": self.id, "title": self.title, "source": self.source, "status": self.status,
                "message": self.message, "steps": [s.to_dict(i) for i, s in enumerate(self.steps)]}

    def previews(self) -> List[str]:
        """One line per step, for showing the whole plan before it starts."""
        out = []
        for s in self.steps:
            p = preview(s.action_id, s.params, self.source)
            out.append(p.get("preview") or f"{s.title}: {p.get('error', '')}")
        return out

    # ------------------------------------------------------------------ #
    def _emit_step(self, index: int):
        event_bus.emit_event(EventType.PLAN_STEP, dict(self.steps[index].to_dict(index), plan=self.id,
                                                       total=len(self.steps)))

    def _finish(self, ok: bool, message: str, code: str = "") -> ActionResult:
        self.status, self.message = (DONE if ok else FAILED), message
        event_bus.emit_event(EventType.PLAN_DONE, dict(self.to_dict(), ok=ok))
        return ActionResult(ok, message=message if ok else "", error="" if ok else message,
                            code=code, action="plan", data=self.to_dict())

    def _stop(self, index: int, why: str, code: str) -> ActionResult:
        rest = self.steps[index + 1:]
        for offset, later in enumerate(rest, start=index + 1):
            later.status = SKIPPED
            self._emit_step(offset)
        step, n = self.steps[index], len(self.steps)
        tail = "" if not rest else (" The 1 step after it was not run." if len(rest) == 1
                                    else f" The {len(rest)} steps after it were not run.")
        return self._finish(False, f"Stopped at step {index + 1} of {n} ({step.title}): {why}{tail}", code)

    def run(self, confirm: Optional[ConfirmCallback] = None) -> ActionResult:
        if self.status not in (PENDING,):
            return ActionResult(False, error="This plan has already been started.", code="INVALID", action="plan")
        if not self.steps:
            return self._finish(True, "Nothing to do.")
        self._confirm = confirm
        self.status = RUNNING
        event_bus.emit_event(EventType.PLAN_STARTED, self.to_dict())
        return self._run_from(0)

    def resume(self, approved: bool = True) -> ActionResult:
        """Answer the step a waiting plan paused on."""
        if self.status != "waiting":
            return ActionResult(False, error="This plan isn't waiting for an answer.", code="INVALID",
                                action="plan")
        index = next(i for i, s in enumerate(self.steps) if s.status == PENDING)
        self.status = RUNNING
        if not approved:
            self.steps[index].status, self.steps[index].message = SKIPPED, "You said no."
            self._emit_step(index)
            return self._stop(index, "you said no.", "DECLINED")
        return self._run_from(index, confirmed=True)

    def _run_from(self, start: int, confirmed: bool = False) -> ActionResult:
        for index in range(start, len(self.steps)):
            step = self.steps[index]
            step.status = RUNNING
            self._emit_step(index)
            result = execute(step.action_id, step.params, source=self.source, confirm=self._confirm,
                             confirmed=confirmed and index == start, plan_id=self.id, step=index)
            step.entry_id = result.entry_id
            if result.needs_confirmation:
                step.status, step.message = PENDING, result.preview
                self.status = "waiting"
                self._emit_step(index)
                return ActionResult(False, error=result.error, code="CONFIRM_REQUIRED", action="plan",
                                    preview=result.preview, risk=result.risk, data=self.to_dict())
            step.message = result.text
            if not result.ok:
                step.status = SKIPPED if result.code == "DECLINED" else FAILED
                self._emit_step(index)
                why = "you said no." if result.code == "DECLINED" else result.text
                return self._stop(index, why, result.code)
            step.status = DONE
            self._emit_step(index)
        n = len(self.steps)
        return self._finish(True, f"Done: {self.title} ({n} step{'s' if n != 1 else ''}).")
