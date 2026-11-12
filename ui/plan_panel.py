"""
ui/plan_panel.py

The step list for a multi-step command, shown at the top right of the main screen while SAINT works through a
plan (core/actions/executor.Plan): each step with its state (waiting, running, done, failed, skipped) and the
line it reported. Like the action notice it never takes focus and clicks pass through it, so SAINT can work
while you carry on. It follows the plan.started / plan.step / plan.done events and nothing else.
"""

from typing import Dict, List

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.events import EventType
from ui import motion, placement
from ui.reactive import ui_bus
from ui.theme import current_palette
from ui.widgets import with_alpha

WIDTH = 360
MARGIN = 24
LINGER_MS = 5000
MAX_ROWS = 8
GLYPH = {"pending": "○", "running": "●", "done": "✓", "failed": "✕", "skipped": "–"}


def step_line(step: Dict) -> str:
    """One row's text: the glyph, the step's title, and what it said (when it said something worth showing)."""
    status = step.get("status", "pending")
    text = f"{GLYPH.get(status, '○')}  {step.get('title') or step.get('action', '')}"
    message = (step.get("message") or "").strip()
    if message and status in ("failed", "skipped", "pending"):       # a failure's reason, or the question asked
        text += f"\n     {message[:140]}"
    return text


def visible_steps(steps: List[Dict], limit: int = MAX_ROWS) -> List[Dict]:
    """At most ``limit`` rows, keeping the running step in view in a long plan."""
    if len(steps) <= limit:
        return steps
    current = next((i for i, s in enumerate(steps) if s.get("status") in ("running", "pending")), len(steps) - 1)
    start = max(0, min(current - 2, len(steps) - limit))
    return steps[start:start + limit]


class PlanPanel(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("SAINT plan")
        self.setFixedWidth(WIDTH)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(6)
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: 600; background: transparent;")
        lay.addWidget(self.title)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(4)
        lay.addLayout(self.rows)
        self.footer = QLabel("")
        self.footer.setObjectName("Faint")
        self.footer.setWordWrap(True)
        self.footer.setStyleSheet("background: transparent;")
        lay.addWidget(self.footer)
        self.plan_id = ""
        self.steps: List[Dict] = []
        self._state = "running"            # running | waiting | done | failed
        self._labels: List[QLabel] = []
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.leave)
        ui_bus.event.connect(self._on_event)

    # ------------------------------------------------------------------ #
    def _on_event(self, ev):
        t, p = ev.type, ev.payload or {}
        if t == EventType.PLAN_STARTED:
            from ui.action_notice import enabled
            if enabled() and len(p.get("steps") or []) > 1:           # one step is the action notice's job
                self.start(p)
        elif t == EventType.PLAN_STEP and p.get("plan") == self.plan_id:
            self.step(p)
        elif t == EventType.PLAN_DONE and p.get("plan") == self.plan_id:
            self.finish(p)

    def start(self, plan: Dict):
        self._hide.stop()
        self.plan_id = plan.get("plan", "")
        self.steps = [dict(s) for s in plan.get("steps") or []]
        self._state = "running"
        self.title.setText(plan.get("title") or "Working on it")
        self.footer.setText("")
        self._render()
        self.appear()

    def step(self, step: Dict):
        i = step.get("index", -1)
        if not 0 <= i < len(self.steps):
            return
        self.steps[i] = dict(step)
        waiting = step.get("status") == "pending" and bool(step.get("message"))
        self._state = "waiting" if waiting else "running"
        self.footer.setText("Waiting for your OK." if waiting else "")
        self._render()

    def finish(self, plan: Dict):
        self.steps = [dict(s) for s in plan.get("steps") or self.steps]
        ok = bool(plan.get("ok"))
        self._state = "done" if ok else "failed"
        self.footer.setText("" if ok else (plan.get("message") or "It stopped before the end."))
        self._render()
        self._hide.start(LINGER_MS if ok else LINGER_MS * 2)

    # ------------------------------------------------------------------ #
    def _render(self):
        p = current_palette()
        colour = {"done": p.success, "failed": p.danger, "running": p.accent, "skipped": p.muted, "pending": p.muted}
        shown = visible_steps(self.steps)
        while len(self._labels) < len(shown):
            label = QLabel("")
            label.setWordWrap(True)
            self.rows.addWidget(label)
            self._labels.append(label)
        for i, label in enumerate(self._labels):
            if i < len(shown):
                s = shown[i]
                label.setText(step_line(s))
                weight = "600" if s.get("status") == "running" else "400"
                label.setStyleSheet(f"color: {colour.get(s.get('status'), p.muted)}; font-weight: {weight}; "
                                    f"background: transparent;")
                label.show()
            else:
                label.hide()
        hidden = len(self.steps) - len(shown)
        done = sum(s.get("status") == "done" for s in self.steps)
        if self._state in ("running", "waiting") and not self.footer.text():
            self.footer.setText(f"{done} of {len(self.steps)} done" + (f" · {hidden} more steps" if hidden > 0 else ""))
        self.footer.setVisible(bool(self.footer.text()))
        self.adjustSize()
        self._place()
        self.update()

    def _home(self) -> QPoint:
        screen = placement.primary_screen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        return QPoint(area.right() - self.width() - MARGIN, area.top() + MARGIN)

    def _place(self):
        target = self._home()
        self.move(target)
        placement.wayland_place(self, QRect(target, self.size()), "SAINT plan")

    def appear(self):
        self._place()
        if not self.isVisible():
            self.setWindowOpacity(0.0 if motion.enabled() else 1.0)
            self.show()
            motion.animate(self, b"windowOpacity", 0.0, 1.0, motion.BASE)

    def leave(self):
        if not self.isVisible():
            return

        def done():
            self.hide()
            self.plan_id = ""
        motion.animate(self, b"windowOpacity", self.windowOpacity(), 0.0, motion.BASE, on_done=done)

    def paintEvent(self, _):
        p = current_palette()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 16, 16)
        g.fillPath(path, with_alpha(p.raised, 246))
        edge = {"done": p.success, "failed": p.danger, "waiting": p.warning}.get(self._state, p.accent)
        g.setPen(QPen(with_alpha(edge, 120), 1))
        g.drawPath(path)
