"""
core/avatar

What SAINT's avatar shows. No Qt here: the avatar state is derived from the one authoritative
AssistantState (core/assistant_state.py) plus a few events (plans, failures) that the assistant
state doesn't carry. ui/avatar renders it.

Settings live under ``avatar.*`` in core/config.py.
"""

import time
from enum import Enum

from core.assistant_state import AssistantState
from core.events import EventType


STYLES = ("realistic", "hologram")
VIEWS = ("full", "portrait")          # whole body (with task props) or head and shoulders


def _clamp(v, lo, hi):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return 1.0


class AvatarState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    PLANNING = "planning"
    SPEAKING = "speaking"
    WORKING = "working"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    OFFLINE = "offline"


_FROM_ASSISTANT = {
    AssistantState.OFFLINE: AvatarState.OFFLINE,
    AssistantState.IDLE: AvatarState.IDLE,
    AssistantState.WAKE_LISTENING: AvatarState.IDLE,
    AssistantState.WAKE_DETECTED: AvatarState.LISTENING,
    AssistantState.COMMAND_LISTENING: AvatarState.LISTENING,
    AssistantState.LISTENING: AvatarState.LISTENING,
    AssistantState.PROCESSING: AvatarState.THINKING,
    AssistantState.EXECUTING: AvatarState.WORKING,
    AssistantState.OBSERVING: AvatarState.WORKING,
    AssistantState.SPEAKING: AvatarState.SPEAKING,
    AssistantState.ERROR: AvatarState.ERROR,
}

# Ring colour per state; IDLE uses the configured accent instead.
COLORS = {
    AvatarState.IDLE: "#feaa34", AvatarState.LISTENING: "#4fc3f7", AvatarState.THINKING: "#b388ff",
    AvatarState.PLANNING: "#7c8cff", AvatarState.SPEAKING: "#feaa34", AvatarState.WORKING: "#26c6da",
    AvatarState.SUCCESS: "#66bb6a", AvatarState.WARNING: "#ffca28", AvatarState.ERROR: "#ef5350",
    AvatarState.OFFLINE: "#78797d",
}

TRANSIENT_SEC = 2.0


def from_assistant(value: str) -> AvatarState:
    try:
        return _FROM_ASSISTANT[AssistantState(value)]
    except ValueError:
        return AvatarState.IDLE


class AvatarStateMachine:
    """Feed it events; ``current()`` is what to show. Transient states (success, warning, error)
    show for TRANSIENT_SEC, then the avatar returns to the assistant's state. A running plan shows
    PLANNING while SAINT is otherwise only thinking/working on it."""

    def __init__(self, assistant_value: str = "offline"):
        self.base = from_assistant(assistant_value)
        self.planning = False
        self._flash = None            # (state, until)

    def feed(self, ev_type, payload=None, now=None) -> AvatarState:
        p, now = payload or {}, time.monotonic() if now is None else now
        if ev_type == EventType.ASSISTANT_STATE:
            self.base = from_assistant(str(p.get("state", "idle")))
        elif ev_type in (EventType.PLAN_STARTED, EventType.PLAN_STEP):
            self.planning = True
        elif ev_type == EventType.PLAN_DONE:
            self.planning = False
            self._flash = (AvatarState.SUCCESS if p.get("ok") else AvatarState.WARNING, now + TRANSIENT_SEC)
        elif ev_type in (EventType.TOOL_FAILED, EventType.WARNING):
            self._flash = (AvatarState.WARNING, now + TRANSIENT_SEC)
        elif ev_type in (EventType.AI_ERROR, EventType.ERROR):
            self._flash = (AvatarState.ERROR, now + TRANSIENT_SEC)
        return self.current(now)

    def current(self, now=None) -> AvatarState:
        now = time.monotonic() if now is None else now
        if self._flash and now < self._flash[1] and self.base not in (AvatarState.SPEAKING, AvatarState.LISTENING):
            return self._flash[0]
        if self.planning and self.base in (AvatarState.THINKING, AvatarState.WORKING, AvatarState.IDLE):
            return AvatarState.PLANNING
        return self.base


# ---------------------------------------------------------------- settings
PLACEMENTS = ("floating", "widget", "off")
SIZE_MIN, SIZE_MAX = 80, 480


def settings(cfg=None) -> dict:
    """The avatar settings, clamped to valid values (a hand-edited config can't break the widget)."""
    if cfg is None:
        from core.config import config as cfg
    s = dict(cfg.get("avatar", {}) or {})
    try:
        size = int(s.get("size", 160))
    except (TypeError, ValueError):
        size = 160
    pos = s.get("pos")
    return {
        "enabled": bool(s.get("enabled", True)),
        "name": str(s.get("name") or "SAINT")[:40],
        "id": str(s.get("id") or "default"),
        "accent": str(s.get("accent") or ""),
        "size": max(SIZE_MIN, min(SIZE_MAX, size)),
        "placement": s.get("placement") if s.get("placement") in PLACEMENTS else "floating",
        "pos": [int(v) for v in pos] if isinstance(pos, (list, tuple)) and len(pos) == 2 else None,
        "reduce_motion": bool(s.get("reduce_motion", False)),
        "style": s.get("style") if s.get("style") in STYLES else "realistic",
        "view": s.get("view") if s.get("view") in VIEWS else "full",
        "props": bool(s.get("props", True)),
        "motion": _clamp(s.get("motion", 1.0), 0.0, 1.5),
        "behaviors": bool(s.get("behaviors", True)),
        "shy": bool(s.get("shy", False)),
        "presence": s.get("presence") if s.get("presence") in ("always", "pop") else "always",
    }
