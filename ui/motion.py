"""
ui/motion.py

Animation helpers. Every animation in the UI goes through here so the
Appearance > Animations switch turns all of it off in one place.
Opacity effects are removed when an animation finishes — leaving a
QGraphicsEffect on a widget makes Qt re-render it offscreen forever.
"""

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, Qt, QTimer, QVariantAnimation
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect

from core.config import config

FAST, BASE, SLOW = 120, 200, 320
EASE = QEasingCurve.OutCubic
SNAP = QEasingCurve.OutBack


def enabled() -> bool:
    return bool(config.get("appearance.animations", True))


def animate(target, prop: bytes, start, end, ms: int = BASE, curve=EASE, on_done=None):
    """Start a property animation (kept alive by its target). Jumps to the end if animations are off."""
    if not enabled() or ms <= 0:
        target.setProperty(prop.decode(), end)
        if on_done:
            on_done()
        return None
    anim = QPropertyAnimation(target, prop, target)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(curve)
    if on_done:
        anim.finished.connect(on_done)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def fade_in(widget, ms: int = BASE, delay: int = 0, dy: int = 0):
    """Fade (and optionally rise ``dy`` px) into place."""
    if not enabled():
        widget.show()
        return

    def go():
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
        widget.show()
        animate(eff, b"opacity", 0.0, 1.0, ms, on_done=lambda: widget.setGraphicsEffect(None))
        if dy:
            end = widget.pos()
            animate(widget, b"pos", end + QPoint(0, dy), end, ms)
    QTimer.singleShot(delay, go) if delay else go()


def fade_out(widget, ms: int = FAST, on_done=None):
    def finish():
        widget.setGraphicsEffect(None)
        widget.hide()
        if on_done:
            on_done()
    if not enabled():
        finish()
        return
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    animate(eff, b"opacity", 1.0, 0.0, ms, on_done=finish)


def stagger(widgets, ms: int = BASE, step: int = 40, dy: int = 10):
    for i, w in enumerate(widgets):
        fade_in(w, ms, delay=i * step, dy=dy)


class _SmoothWheel(QObject):
    """Mouse-wheel notches glide (ease-out) instead of jumping; touchpads (pixel deltas) keep their own scrolling."""

    def __init__(self, area, ms: int):
        super().__init__(area)
        self.area, self.ms = area, ms
        self.anims = {}

    def eventFilter(self, obj, ev):
        if ev.type() != QEvent.Wheel or not enabled() or not ev.pixelDelta().isNull() \
                or ev.modifiers() & Qt.ControlModifier:
            return False
        d = ev.angleDelta()
        horizontal = bool(d.x()) and not d.y() or bool(ev.modifiers() & Qt.ShiftModifier)
        bar = self.area.horizontalScrollBar() if horizontal else self.area.verticalScrollBar()
        delta = (d.x() or d.y()) if horizontal else d.y()
        if not delta or bar.maximum() <= bar.minimum():
            return False
        anim = self.anims.get(horizontal)
        if anim is None:
            anim = self.anims[horizontal] = QVariantAnimation(self)
            anim.setEasingCurve(EASE)
            anim.valueChanged.connect(lambda v, b=bar: b.setValue(int(v)))
        running = anim.state() == QVariantAnimation.Running
        start = bar.value()
        base = int(anim.endValue()) if running and anim.endValue() is not None else start
        step = max(bar.singleStep(), 20) * QApplication.wheelScrollLines()
        end = max(bar.minimum(), min(bar.maximum(), base - int(delta / 120 * step)))
        anim.stop()
        anim.setDuration(self.ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()
        return True


def smooth_scroll(area, ms: int = 180):
    """Glide a QScrollArea / item view on wheel notches (per-pixel scrolling for item views). Returns ``area``."""
    if hasattr(area, "setVerticalScrollMode"):
        from PySide6.QtWidgets import QAbstractItemView
        area.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        area.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    area.viewport().installEventFilter(_SmoothWheel(area, ms))
    return area
