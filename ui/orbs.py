"""
ui/orbs.py

OrbBackground: soft, blurred colour orbs (blue, green, peach) drifting slowly on a light background, the HalOS
welcome look (the installer chooser, the What's new tour). Radial gradients with a long falloff, so no blur pass is
needed. ~30 fps while visible, the timer stops when the widget is hidden, and with Appearance > Animations off
(ui/motion.enabled) it paints one still frame.

    OrbBackground(parent)      # fills ``parent`` and stays behind its other children
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

FPS = 30
BASE = "#f7f8fb"
# colour, centre (fraction of width/height), drift amplitude (fraction), radius (fraction of the long side),
# angular speed (rad/s) and phase
ORBS = (
    ("#7fb0ff", (0.22, 0.30), (0.10, 0.08), 0.55, 0.11, 0.0),      # blue
    ("#8fe0b4", (0.78, 0.25), (0.08, 0.10), 0.48, 0.09, 2.1),      # green
    ("#ffc3a0", (0.60, 0.82), (0.12, 0.07), 0.52, 0.13, 4.2),      # peach
    ("#a9c8ff", (0.05, 0.95), (0.06, 0.06), 0.35, 0.07, 1.3),      # a paler blue to fill the corner
)


class OrbBackground(QWidget):
    def __init__(self, parent: QWidget, base: str = BASE, animate: bool | None = None):
        super().__init__(parent)
        self.base = QColor(base)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setFocusPolicy(Qt.NoFocus)
        if animate is None:
            try:
                from ui.motion import enabled
                animate = enabled()
            except Exception:
                animate = True
        self.animated = bool(animate)
        self._t0 = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(1000 // FPS)
        self.timer.timeout.connect(self.update)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        self.lower()

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
            self.lower()
        return False

    def showEvent(self, ev):
        if self.animated:
            self.timer.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        self.timer.stop()
        super().hideEvent(ev)

    def seconds(self) -> float:
        return time.monotonic() - self._t0 if self.animated else 0.0

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self.base)
        w, h = self.width(), self.height()
        long_side = max(w, h)
        t = self.seconds()
        p.setPen(Qt.NoPen)
        for color, (cx, cy), (ax, ay), r, speed, phase in ORBS:
            x = (cx + ax * math.sin(t * speed + phase)) * w
            y = (cy + ay * math.cos(t * speed * 0.8 + phase)) * h
            radius = r * long_side * (1 + 0.06 * math.sin(t * speed * 1.7 + phase))
            g = QRadialGradient(QPointF(x, y), radius)
            for stop, alpha in ((0.0, 0.62), (0.35, 0.38), (0.7, 0.12), (1.0, 0.0)):
                c = QColor(color)
                c.setAlphaF(alpha)
                g.setColorAt(stop, c)
            p.setBrush(g)
            p.drawEllipse(QPointF(x, y), radius, radius)
        p.end()
