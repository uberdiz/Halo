"""Control Center page "Animations": what the saint-star KWin effect plays for each window event (core/window_anim.py)."""

import copy
import threading
import time

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

from core import kde_desktop as kde
from core import window_anim as wa
from ui.settings_pages.desktop import scrolling_page
from ui.supernova import paint_burst
from ui.theme import current_palette

TITLE = "Animations"
ICON = "sparkles"
ORDER = 31

TUNE_DEFAULT = {"scale": 100, "rotation": 100, "brightness": 100}
BURST_MS = 450


def _ease(name: str, x: float) -> float:
    return QEasingCurve(getattr(QEasingCurve, name, QEasingCurve.Linear)).valueForProgress(x)


class Preview(QWidget):
    """A small window playing the preset the way the effect will, burst included. No KWin needed."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(190)
        self._preset = None
        self._start = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)

    def play(self, preset: dict):
        self._preset = preset
        self._start = time.monotonic()
        self._timer.start()

    def _elapsed(self) -> float:
        return (time.monotonic() - self._start) * 1000.0

    def paintEvent(self, _):
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        p = current_palette()
        c = QPointF(self.width() / 2, self.height() / 2)
        state = dict(wa.NEUTRAL)
        burst_t = None
        if self._preset:
            duration = max(1, self._preset.get("duration", 0))
            elapsed = self._elapsed()
            if self._preset.get("segments"):
                state = wa.sample(self._preset, elapsed / duration, _ease)
            burst_end = duration + (BURST_MS if self._preset.get("burst") else 0)
            if self._preset.get("burst") and elapsed >= duration * 0.92:
                burst_t = (elapsed - duration * 0.92) / BURST_MS
            if elapsed > burst_end + 300:        # back to rest, ready for the next Preview
                self._preset = None
                self._timer.stop()
                state = dict(wa.NEUTRAL)
                burst_t = None
        g.save()
        g.translate(c)
        g.rotate(state["rotation"])
        g.scale(state["scale"], state["scale"])
        g.setOpacity(max(0.0, min(1.0, state["opacity"])))
        rect = QRectF(-90, -58, 180, 116)
        g.setPen(QColor(p.border_strong))
        g.setBrush(QColor(p.raised))
        g.drawRoundedRect(rect, 8, 8)
        g.setBrush(QColor(p.accent))
        g.setPen(Qt.NoPen)
        g.drawRoundedRect(QRectF(-90, -58, 180, 20), 8, 8)
        if state["brightness"] > 1.0:            # the effect's brightness flash
            alpha = int(min(1.0, (state["brightness"] - 1.0) / 2.0) * 255)
            g.setBrush(QColor(255, 255, 255, alpha))
            g.drawRoundedRect(rect, 8, 8)
        g.restore()
        if burst_t is not None:
            paint_burst(g, c.x(), c.y(), min(self.width(), self.height()) / 2 - 4, burst_t)
        g.end()


def _slider(low: int, high: int, value: int, suffix: str):
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    s = QSlider(Qt.Horizontal)
    s.setRange(low, high)
    s.setValue(value)
    label = QLabel(f"{value}{suffix}")
    label.setMinimumWidth(56)
    s.valueChanged.connect(lambda n: label.setText(f"{n}{suffix}"))
    h.addWidget(s, 1)
    h.addWidget(label)
    return row, s


def _test_window() -> QDialog:
    """A real window that closes by itself, so KWin plays what's saved."""
    d = QDialog()
    d.setWindowTitle("Animation test")
    d.resize(420, 260)
    QVBoxLayout(d).addWidget(QLabel("This window closes by itself in a moment."), 0, Qt.AlignCenter)
    d.show()
    QTimer.singleShot(1100, d.close)
    return d


class Page:
    def __init__(self):
        self.widget, v = scrolling_page("Animations", "How windows open, close, minimize and arrive when you switch "
                                                      "desktops. Plasma's animation speed still scales all of them.")
        self.custom, problems = wa.load_custom()
        self.chosen = {e: copy.deepcopy(wa.current(e)) for e in wa.EVENTS}
        self.burst = bool(self.chosen["close"].get("burst"))
        self.loading = False

        form_box = QGroupBox("Animation")
        form = QFormLayout(form_box)
        self.event = QComboBox()
        for key, title in wa.EVENT_TITLES.items():
            self.event.addItem(title, key)
        self.preset = QComboBox()
        form.addRow("Window event", self.event)
        form.addRow("Plays", self.preset)
        duration_row, self.duration = _slider(wa.MIN_MS, wa.MAX_MS, 280, " ms")
        scale_row, self.scale = _slider(0, 200, 100, " %")
        rotation_row, self.rotation = _slider(0, 200, 100, " %")
        brightness_row, self.brightness = _slider(0, 200, 100, " %")
        form.addRow("Duration", duration_row)
        form.addRow("Scale", scale_row)
        form.addRow("Rotation", rotation_row)
        form.addRow("Brightness", brightness_row)
        v.addWidget(form_box)

        self.preview = Preview()
        v.addWidget(self.preview)

        row = QHBoxLayout()
        play = QPushButton("Preview")
        play.clicked.connect(self.play_preview)
        real = QPushButton("Try on a real window")
        real.setToolTip("Saves, then opens a window that closes itself, so KWin plays it for real.")
        real.clicked.connect(self.try_real)
        save = QPushButton("Save as custom…")
        save.clicked.connect(self.save_as)
        for b in (play, real, save):
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)

        self.reduced = QCheckBox("Reduced motion: a short fade only, for every window")
        self.reduced.setChecked(wa.reduced_motion())
        self.reduced.toggled.connect(lambda _on: self.apply())
        v.addWidget(self.reduced)

        self.msg = QLabel("\n".join(f"Skipped {p}" for p in problems))
        self.msg.setObjectName("Muted")
        self.msg.setWordWrap(True)
        v.addWidget(self.msg)
        v.addStretch(1)

        self.event.currentIndexChanged.connect(lambda _i: self.show_event())
        self.preset.activated.connect(lambda _i: self.pick())
        for s in (self.duration, self.scale, self.rotation, self.brightness):
            s.sliderReleased.connect(self.tune_changed)
        self.show_event()

    # ---- which presets exist
    def event_key(self) -> str:
        return self.event.currentData()

    def base_presets(self, event: str):
        return wa.BUILTIN[event] + self.custom.get(event, [])

    def base_of(self, preset: dict) -> dict:
        """The unmodified preset behind a configured one (sliders apply to this)."""
        event = self.event_key()
        for p in self.base_presets(event):
            if p["id"] == preset.get("id"):
                return p
        return wa.default_preset(event)

    # ---- controls <-> state
    def show_event(self):
        self.loading = True
        event = self.event_key()
        current = self.chosen[event]
        self.preset.clear()
        for p in self.base_presets(event):
            self.preset.addItem(p["name"], p["id"])
        i = self.preset.findData(current.get("id", wa.default_preset(event)["id"]))
        self.preset.setCurrentIndex(max(0, i))
        self.show_tune(current)
        self.loading = False

    def show_tune(self, preset: dict):
        tune = {**TUNE_DEFAULT, **(preset.get("tune") or {})}
        self.duration.setValue(int(preset.get("duration") or self.base_of(preset).get("duration") or 280))
        self.scale.setValue(tune["scale"])
        self.rotation.setValue(tune["rotation"])
        self.brightness.setValue(tune["brightness"])
        animated = bool(self.base_of(preset).get("segments"))
        for s in (self.duration, self.scale, self.rotation, self.brightness):
            s.setEnabled(animated)

    def build_current(self) -> dict:
        base = self.base_of({"id": self.preset.currentData()})
        out = wa.tuned(base, self.duration.value(), self.scale.value() / 100, self.rotation.value() / 100,
                       self.brightness.value() / 100)
        out["id"] = base["id"]
        out["tune"] = {"scale": self.scale.value(), "rotation": self.rotation.value(),
                       "brightness": self.brightness.value()}
        return out

    def pick(self):
        if self.loading:
            return
        event = self.event_key()
        base = self.base_of({"id": self.preset.currentData()})
        self.chosen[event] = copy.deepcopy(base)
        self.loading = True
        self.show_tune(base)
        self.scale.setValue(100)
        self.rotation.setValue(100)
        self.brightness.setValue(100)
        self.loading = False
        self.apply()
        self.play_preview()

    def tune_changed(self):
        if self.loading:
            return
        self.chosen[self.event_key()] = self.build_current()
        self.apply()

    def apply(self) -> bool:
        ok = wa.apply(self.chosen, self.reduced.isChecked())
        burst = bool(self.chosen["close"].get("burst"))
        if burst != self.burst:              # saint-shell only reads CloseBurst when it loads
            self.burst = burst
            threading.Thread(target=kde.reload_shell_script, daemon=True).start()
        self.msg.setText("Saved. New windows use it now." if ok else
                         "KWin didn't take that (it only runs in a Plasma session). The preview still shows it.")
        return ok

    # ---- buttons
    def play_preview(self):
        self.preview.play(self.build_current())

    def try_real(self):
        self.chosen[self.event_key()] = self.build_current()
        self.apply()
        self.test_window = _test_window()    # held here: without a parent, Python would delete it right away

    def save_as(self):
        name, ok = QInputDialog.getText(self.widget, "Save as custom", "Name:")
        if not ok or not name.strip():
            return
        self.save_named(name.strip())

    def save_named(self, name: str):
        event = self.event_key()
        try:
            current = self.build_current()
            if not current.get("segments"):
                raise ValueError("This one doesn't animate anything, so there's nothing to save.")
            path = wa.save_custom(current, name, event)
        except (OSError, ValueError) as e:
            self.msg.setText(f"Not saved: {e}")
            return
        self.custom, _problems = wa.load_custom()
        self.chosen[event] = copy.deepcopy(next(p for p in self.custom[event] if p["id"] == f"custom:{path.stem}"))
        self.show_event()
        self.apply()
        self.msg.setText(f"Saved as {path}")


def build() -> QWidget:
    page = Page()
    page.widget._page = page                 # kept alive with its widget (and for tests)
    return page.widget
