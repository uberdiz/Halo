"""
ui/supernova.py

The burst at the end of the Supernova close animation, modelled on the SAINT logo: a radial flash, an expanding
shockwave ring and eight star-tip rays in SAINT orange. KWin's scripted effects can only transform a window, so
the saint-star effect collapses the window and SAINT paints this in a short-lived click-through window, placed by
the saint-shell script like the Halo. It never takes focus and the effect leaves it alone (the SAINT:place: mark).
"""

import logging
import math
import time

from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

from core import window_anim
from ui import placement

log = logging.getLogger("saint.ui.supernova")

ORANGE = "#feaa34"
LIFE_MS = 450
FRAME_MS = 16
SIDE = 360                         # logical pixels; everything is painted inside it
MAX_LIVE = 6                       # closing many windows at once doesn't stack up without limit
_live = []


def paint_burst(g: QPainter, cx: float, cy: float, radius: float, t: float):
    """The burst at progress t (0-1). A few gradient and polygon fills: cheap, and on no window but its own."""
    if not 0.0 <= t < 1.0:
        return
    g.setRenderHint(QPainter.Antialiasing)
    center = QPointF(cx, cy)
    orange = QColor(ORANGE)
    fade = (1.0 - t) ** 1.5

    # flash: white-hot core into orange, gone by 40% of the way
    flash = max(0.0, 1.0 - t / 0.4)
    if flash > 0:
        r = radius * (0.25 + 0.3 * t / 0.4)
        grad = QRadialGradient(center, r)
        # cools from white towards orange as it fades: faint white over a dark desktop would read as grey
        grad.setColorAt(0.0, QColor(255, int(170 + 85 * flash), int(52 + 203 * flash), int(255 * flash)))
        grad.setColorAt(0.35, QColor(orange.red(), orange.green(), orange.blue(), int(220 * flash)))
        grad.setColorAt(1.0, QColor(orange.red(), orange.green(), orange.blue(), 0))
        g.setPen(Qt.NoPen)
        g.setBrush(grad)
        g.drawEllipse(center, r, r)

    # rays: eight tapered star tips, the long ones on the axes like the logo
    reach = radius * (0.2 + 0.75 * (1.0 - (1.0 - t) ** 3))
    g.setPen(Qt.NoPen)
    tip = QColor(orange)
    tip.setAlpha(int(235 * fade))
    g.setBrush(tip)
    for k in range(8):
        a = k * math.pi / 4
        length = reach if k % 2 == 0 else reach * 0.55
        side = radius * 0.035
        along, across = QPointF(math.cos(a), math.sin(a)), QPointF(-math.sin(a), math.cos(a))
        base = center + along * (length * 0.25)
        g.drawPolygon(QPolygonF([base + across * side, center + along * length, base - across * side]))

    # shockwave ring
    ring = QColor(orange)
    ring.setAlpha(int(200 * fade))
    g.setBrush(Qt.NoBrush)
    g.setPen(QPen(ring, max(1.0, radius * 0.035 * (1.0 - t))))
    r = radius * (0.1 + 0.88 * (1.0 - (1.0 - t) ** 2))
    g.drawEllipse(center, r, r)


class Burst(QWidget):
    def __init__(self, x: int, y: int):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        rect = QRect(x - SIDE // 2, y - SIDE // 2, SIDE, SIDE)
        self.setGeometry(rect)
        self.setFixedSize(SIDE, SIDE)
        placement.wayland_place(self, rect, "SAINT burst")
        self._start = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._start = time.monotonic()
        self.show()
        self._timer.start()

    def progress(self) -> float:
        return (time.monotonic() - self._start) * 1000.0 / LIFE_MS

    def _tick(self):
        if self.progress() >= 1.0:
            self.finish()
        else:
            self.update()

    def finish(self):
        self._timer.stop()
        self.hide()
        if self in _live:
            _live.remove(self)
        self.deleteLater()

    def paintEvent(self, _):
        g = QPainter(self)
        paint_burst(g, SIDE / 2, SIDE / 2, SIDE / 2 - 2, self.progress())
        g.end()


def _spawn(x: int, y: int):
    if len(_live) >= MAX_LIVE:
        return
    b = Burst(x, y)
    _live.append(b)
    b.start()


def play(x: int, y: int):
    """A window closed at (x, y): paint the burst when its collapse ends, if the settings want one."""
    try:
        from core.game_mode import game_mode
        if game_mode.overlays_blocked:          # never over a game (core/game_mode.py), like the Halo
            return
        delay = window_anim.burst_delay_ms()
        if delay is not None:
            QTimer.singleShot(delay, lambda: _spawn(int(x), int(y)))
    except Exception:
        log.exception("supernova.failed")
