"""Control Center page "Animations": what the saint-star KWin effect plays for each window event (core/window_anim.py)."""

import copy
import threading
import time

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

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
TUNE_SETTLE_MS = 250               # a slider counts this long after it stops moving (drag, wheel, keys or a click)
TRY_MS = 4000                      # "Try on a real window": the draft stays in KWin this long, then the saved one
TRY_DESKTOP_MS = 8000


class _Bridge(QObject):
    applied = Signal(int, bool)    # (which apply, did KWin take it), from the worker thread to the page


def _spawn(work):
    """Run ``work`` off the UI thread: saving is nine kwriteconfig6/qdbus calls, which froze the page."""
    threading.Thread(target=work, daemon=True, name="animations-apply").start()


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


def _test_window(event: str = "close") -> QDialog:
    """A real window that opens and closes by itself (and minimizes first, for that event), so KWin plays
    what's saved."""
    d = QDialog()
    d.setWindowTitle("Animation test")
    d.resize(420, 260)
    QVBoxLayout(d).addWidget(QLabel("This window closes by itself in a moment."), 0, Qt.AlignCenter)
    d.show()
    if event == "minimize":
        QTimer.singleShot(900, d.showMinimized)
        QTimer.singleShot(1900, d.showNormal)
    QTimer.singleShot(2900 if event == "minimize" else 1100, d.close)
    return d


class Page:
    """Edits a draft: every change plays in the preview, and only Save writes it to KWin. Revert puts the draft back
    to what's saved. "Try on real windows" plays the draft on one test window, then puts the saved one back."""

    def __init__(self):
        self.widget, v = scrolling_page("Animations", "How windows open, close, minimize and arrive when you switch "
                                                      "desktops. Changes play in the preview; your windows only "
                                                      "change when you press Save.")
        self.custom, problems = wa.load_custom()
        self.saved = {e: copy.deepcopy(wa.current(e)) for e in wa.EVENTS}       # what KWin plays now
        self.saved_reduced = wa.reduced_motion()
        self.chosen = copy.deepcopy(self.saved)                                  # the draft
        self.builtins = wa.builtin_profiles()
        self.mine, self.active = wa.load_profiles()
        self.burst = bool(self.saved["close"].get("burst"))
        self.loading = False
        self.test_window = None
        self._trying = False                 # the draft is in KWin for a test window, not saved
        self._seq = 0                        # the newest apply(); an older one's result is ignored
        self._then = None
        self._lock = threading.Lock()        # one apply at a time: their kwinrc writes must not interleave
        self._bridge = _Bridge(self.widget)
        self._bridge.applied.connect(self._applied)
        self._settle = QTimer(self.widget)
        self._settle.setSingleShot(True)
        self._settle.setInterval(TUNE_SETTLE_MS)
        self._settle.timeout.connect(self.tune_changed)

        # ---- profiles
        prof_box = QGroupBox("Profile")
        ph = QHBoxLayout(prof_box)
        self.profile = QComboBox()
        self.profile.setToolTip("A profile is one animation and speed for each window event.")
        ph.addWidget(self.profile, 1)
        self.new_btn = QPushButton("New…")
        self.new_btn.setToolTip("A new profile from what's set below")
        self.rename_btn = QPushButton("Rename…")
        self.delete_btn = QPushButton("Delete")
        for b in (self.new_btn, self.rename_btn, self.delete_btn):
            b.setObjectName("Ghost")
            ph.addWidget(b)
        self.new_btn.clicked.connect(self.new_profile_dialog)
        self.rename_btn.clicked.connect(self.rename_profile_dialog)
        self.delete_btn.clicked.connect(self.delete_profile_dialog)
        v.addWidget(prof_box)

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
        real.setToolTip("Opens a window that closes itself so KWin plays this for real, then puts your saved "
                        "animations back. Nothing is saved.")
        real.clicked.connect(self.try_real)
        save_custom = QPushButton("Save animation as…")
        save_custom.setToolTip("Keep this animation (with the sliders) as your own, for any profile")
        save_custom.clicked.connect(self.save_as)
        for b in (play, real, save_custom):
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)

        self.reduced = QCheckBox("Reduced motion: a short fade only, for every window")
        self.reduced.setChecked(self.saved_reduced)
        self.reduced.toggled.connect(lambda _on: self.refresh_dirty())
        v.addWidget(self.reduced)

        self.msg = QLabel("\n".join(f"Skipped {p}" for p in problems))
        self.msg.setObjectName("Muted")
        self.msg.setWordWrap(True)
        v.addWidget(self.msg)

        bar = QHBoxLayout()
        self.state = QLabel("")
        self.state.setObjectName("Muted")
        bar.addWidget(self.state, 1)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.setObjectName("Ghost")
        self.revert_btn.setToolTip("Back to what your windows use now")
        self.revert_btn.clicked.connect(self.revert)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(lambda: self.save())
        bar.addWidget(self.revert_btn)
        bar.addWidget(self.save_btn)
        v.addLayout(bar)
        v.addStretch(1)

        self.event.currentIndexChanged.connect(lambda _i: self.show_event())
        self.preset.activated.connect(lambda _i: self.pick())
        self.profile.activated.connect(lambda _i: self.pick_profile(self.profile.currentData()))
        for s in (self.duration, self.scale, self.rotation, self.brightness):
            # valueChanged, not sliderReleased: that one only fires after a drag, so the wheel, the arrow keys and
            # a click on the groove moved the slider and changed nothing.
            s.valueChanged.connect(self.tune_moved)
        self.fill_profiles(self.active)
        self.show_event()
        self.refresh_dirty()

    # ---- profiles
    def all_profiles(self) -> dict:
        return {**self.builtins, **self.mine}

    def fill_profiles(self, select: str):
        self.profile.clear()
        for name in self.builtins:
            self.profile.addItem(f"{name}  (built-in)", name)
        for name in self.mine:
            self.profile.addItem(name, name)
        self.profile.setCurrentIndex(max(0, self.profile.findData(select)))
        self._profile_buttons()

    def profile_name(self) -> str:
        return self.profile.currentData() or wa.DEFAULT_PROFILE

    def _profile_buttons(self):
        own = self.profile_name() in self.mine
        self.rename_btn.setEnabled(own)
        self.delete_btn.setEnabled(own)
        tip = "" if own else "Built-in profiles can't be changed; make a new one with New…"
        self.rename_btn.setToolTip(tip)
        self.delete_btn.setToolTip(tip)

    def pick_profile(self, name: str):
        """Load a profile into the draft (previewed, not saved)."""
        prof = self.all_profiles().get(name)
        if prof is None:
            return
        self._settle.stop()
        self.chosen = copy.deepcopy(prof)
        self.profile.setCurrentIndex(max(0, self.profile.findData(name)))
        self._profile_buttons()
        self.show_event()
        self.refresh_dirty()
        self.play_preview()

    def _store(self, active=None) -> bool:
        try:
            wa.save_profiles(self.mine, active or self.active)
        except (OSError, ValueError) as e:
            self.msg.setText(f"Profiles not saved: {e}")
            return False
        return True

    def new_profile(self, name: str) -> bool:
        try:
            name = wa.check_profile_name(name, self.mine)
            self.mine[name] = wa.clean_profile(self.chosen)
        except ValueError as e:
            self.msg.setText(f"Not created: {e}")
            return False
        if not self._store():
            del self.mine[name]
            return False
        self.fill_profiles(name)
        self.msg.setText(f"Profile “{name}” created from what's set here. Press Save to use it.")
        self.refresh_dirty()
        return True

    def rename_profile(self, old: str, new: str) -> bool:
        if old not in self.mine:
            return False
        try:
            new = wa.check_profile_name(new, [n for n in self.mine if n != old])
        except ValueError as e:
            self.msg.setText(f"Not renamed: {e}")
            return False
        self.mine = {(new if n == old else n): p for n, p in self.mine.items()}
        if self.active == old:
            self.active = new
        self._store()
        self.fill_profiles(new)
        self.msg.setText(f"Renamed to “{new}”.")
        self.refresh_dirty()
        return True

    def delete_profile(self, name: str) -> bool:
        if name not in self.mine:
            return False
        gone = self.mine.pop(name)
        if self.active == name:
            self.active = wa.DEFAULT_PROFILE
        if not self._store():
            self.mine[name] = gone
            return False
        self.fill_profiles(self.active)
        self.msg.setText(f"Deleted “{name}”. Your windows keep what's saved until you Save something else.")
        self.refresh_dirty()
        return True

    def _ask_name(self, title: str, default: str = ""):
        name, ok = QInputDialog.getText(self.widget, title, "Profile name:", text=default)
        return name.strip() if ok and name.strip() else None

    def new_profile_dialog(self):
        name = self._ask_name("New animation profile", self._free_name())
        if name:
            self.new_profile(name)

    def rename_profile_dialog(self):
        old = self.profile_name()
        name = self._ask_name("Rename profile", old)
        if name and name != old:
            self.rename_profile(old, name)

    def delete_profile_dialog(self):
        name = self.profile_name()
        if name in self.mine and QMessageBox.question(
                self.widget, "Delete profile", f"Delete the profile “{name}”?") == QMessageBox.Yes:
            self.delete_profile(name)

    def _free_name(self) -> str:
        n, name = 1, "My animations"
        while name in self.mine:
            n += 1
            name = f"My animations {n}"
        return name

    # ---- which presets exist
    def event_key(self) -> str:
        return self.event.currentData()

    def base_presets(self, event: str):
        found = wa.BUILTIN[event] + self.custom.get(event, [])
        mine = self.chosen.get(event) or {}
        if mine.get("id") and all(p["id"] != mine["id"] for p in found):
            # a profile's animation whose custom file is gone: still offered, as the profile keeps it
            found = found + [{k: v for k, v in mine.items() if k != "tune"}]
        return found

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
        segments = self.base_of(preset).get("segments") or []
        self.duration.setEnabled(bool(segments))
        for key, s in (("scale", self.scale), ("rotation", self.rotation), ("brightness", self.brightness)):
            used = any(key in seg for seg in segments)       # a slider that would change nothing is greyed out
            s.setEnabled(used)
            s.setToolTip("" if used else f"This animation has no {key} to change.")

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
        self._settle.stop()
        self.refresh_dirty()
        self.play_preview()

    def tune_moved(self, _value=None):
        if not self.loading:
            self._settle.start()

    def tune_changed(self):
        if self.loading:
            return
        self._settle.stop()
        self.chosen[self.event_key()] = self.build_current()
        self.refresh_dirty()
        self.play_preview()

    # ---- draft vs saved
    def dirty(self) -> bool:
        return (not wa.same(self.chosen, self.saved) or self.reduced.isChecked() != self.saved_reduced
                or self.profile_name() != self.active)

    def refresh_dirty(self):
        d = self.dirty()
        self.save_btn.setEnabled(d)
        self.revert_btn.setEnabled(d)
        self.state.setText("Unsaved changes: your windows still use the saved animations." if d else
                           f"Saved: your windows use “{self.active}”.")

    def save(self, new_name=None) -> bool:
        """Write the draft to the chosen profile and to KWin. A changed built-in profile becomes a new one of yours
        (named ``new_name``, or asked for)."""
        if self._settle.isActive():          # a slider still settling: its value counts
            self.tune_changed()
        name = self.profile_name()
        if name in self.builtins and not wa.same(self.chosen, self.builtins[name]):
            new_name = new_name or self._ask_name("Save as a new profile", self._free_name())
            if not new_name or not self.new_profile(new_name):
                return False
            name = self.profile_name()
        elif name in self.mine:
            self.mine[name] = wa.clean_profile(self.chosen)
        self.active = name
        if not self._store(name):
            return False
        draft, reduced = copy.deepcopy(self.chosen), self.reduced.isChecked()

        def done(ok):
            if ok:
                self.saved, self.saved_reduced = draft, reduced
            self.refresh_dirty()
        self.apply(draft, reduced, done)
        return True

    def revert(self):
        self._settle.stop()
        self.chosen = copy.deepcopy(self.saved)
        self.loading = True
        self.reduced.setChecked(self.saved_reduced)
        self.loading = False
        self.fill_profiles(self.active)
        self.show_event()
        self.refresh_dirty()
        self.msg.setText("Back to your saved animations.")

    def apply(self, chosen=None, reduced=None, then=None):
        """Write a set of animations to KWin, off the UI thread. ``then(ok)`` runs here once KWin answered."""
        self._seq += 1
        seq, self._then = self._seq, then
        chosen = copy.deepcopy(self.saved if chosen is None else chosen)
        reduced = self.saved_reduced if reduced is None else reduced
        burst = bool(chosen["close"].get("burst"))
        reload_shell, self.burst = burst != self.burst, burst     # saint-shell only reads CloseBurst when it loads
        self.msg.setText("Saving…")

        def work():
            with self._lock:
                if seq != self._seq:         # a newer choice is already waiting: only that one is written
                    return
                ok = wa.apply(chosen, reduced)
                try:
                    self._bridge.applied.emit(seq, bool(ok))
                except RuntimeError:         # the page was closed meanwhile
                    return
                if ok and reload_shell:
                    kde.reload_shell_script()
        _spawn(work)

    def _applied(self, seq: int, ok: bool):
        if seq != self._seq:
            return
        self.msg.setText("Saved. New windows use it now." if ok else
                         "KWin didn't take that (it only runs in a Plasma session). The preview still shows it.")
        then, self._then = self._then, None
        if then:
            then(ok)

    # ---- buttons
    def play_preview(self):
        preset = self.build_current()
        self.preview.play(preset)
        self.widget.ensureWidgetVisible(self.preview)        # the page scrolls: the preview may be out of view
        if not preset.get("segments"):
            self.msg.setText(f"“{preset.get('name', 'This one')}” doesn't animate, so there's nothing to preview.")

    def try_real(self):
        """Play the draft on one test window, then put the saved animations back (nothing is saved)."""
        event = self.event_key()
        self._settle.stop()
        self.chosen[event] = self.build_current()
        self._trying = True

        def show(ok):                        # held on self: without a parent, Python would delete it right away
            self.test_window = _test_window(event)
            self.msg.setText("Playing on a test window. Your saved animations come back after it."
                             if ok else "KWin didn't take that (it only runs in a Plasma session).")
            if event == "desktop" and ok:
                self.msg.setText("Switch to another desktop and back within a few seconds to see it.")
            QTimer.singleShot(TRY_MS if event != "desktop" else TRY_DESKTOP_MS, self.end_try)
        self.apply(self.chosen, self.reduced.isChecked(), show)

    def end_try(self):
        if not self._trying:
            return
        self._trying = False

        def back(_ok):
            self.msg.setText("Test over: your windows use the saved animations again.")
            self.refresh_dirty()
        self.apply(None, None, back)

    def save_as(self):
        name, ok = QInputDialog.getText(self.widget, "Save animation as", "Name:")
        if not ok or not name.strip():
            return
        self.save_named(name.strip())

    def save_named(self, name: str):
        """Keep the current event's animation as a custom file. It goes in the draft; Save puts it on windows."""
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
        self.refresh_dirty()
        self.msg.setText(f"Kept as {path}. Press Save to use it on your windows.")


def build() -> QWidget:
    page = Page()
    page.widget._page = page                 # kept alive with its widget (and for tests)
    return page.widget
