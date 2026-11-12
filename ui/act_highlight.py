"""
ui/act_highlight.py

A brief outline around what SAINT is acting on (a window it brings forward, snaps or tiles), so you can see where
it's working. It follows the action.target event, never takes focus, and clicks pass through it.
"""

from typing import List

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.events import EventType
from ui import motion, placement
from ui.reactive import ui_bus
from ui.theme import current_palette
from ui.widgets import with_alpha

SHOW_MS = 1400
PAD = 6


def bounds(rects: List[List[int]]) -> QRect:
    """One window covering every target, with room for the outline."""
    out = QRect()
    for x, y, w, h in rects:
        out = out.united(QRect(x, y, w, h))
    return out.adjusted(-PAD, -PAD, PAD, PAD)


class ActHighlight(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("SAINT highlight")
        self.rects: List[QRect] = []
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.hide)
        ui_bus.event.connect(self._on_event)

    def _on_event(self, ev):
        if ev.type == EventType.ACTION_TARGET:
            self.show_rects((ev.payload or {}).get("rects") or [])

    def show_rects(self, rects: List[List[int]]):
        from core.game_mode import game_mode
        rects = [r for r in rects if len(r) == 4 and r[2] > 0 and r[3] > 0]
        if not rects or game_mode.overlays_blocked:
            return
        area = bounds(rects)
        self.rects = [QRect(x - area.x(), y - area.y(), w, h) for x, y, w, h in rects]
        self.setGeometry(area)
        placement.wayland_place(self, area, "SAINT highlight")
        self.setWindowOpacity(1.0)
        self.show()
        self.update()
        self._hide.start(SHOW_MS)
        if motion.enabled():
            QTimer.singleShot(SHOW_MS - 300, lambda: motion.animate(self, b"windowOpacity", 1.0, 0.0, 300))

    def paintEvent(self, _):
        p = current_palette()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        for r in self.rects:
            box = QRectF(r).adjusted(-PAD / 2, -PAD / 2, PAD / 2, PAD / 2)
            g.setPen(QPen(with_alpha(p.accent, 70), 8))
            g.drawRoundedRect(box, 10, 10)
            g.setPen(QPen(with_alpha(p.accent, 230), 2.5))
            g.drawRoundedRect(box, 10, 10)
        g.end()
