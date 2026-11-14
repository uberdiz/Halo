"""Control Center page "Sound": every output (the monitor's HDMI/DisplayPort ones too, even when its card is off),
per-device and per-app volume, which output each app plays on, playing on several outputs at once, and the sound
fix that says what it did (core/sound.py, core/audio_doctor.py; pactl, nothing slow on the GUI thread)."""

import shutil
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QVBoxLayout, QWidget)

from core import audio_doctor, sound
from ui.settings_pages.desktop import scrolling_page
from ui.widgets import clear_layout, run_async

TITLE = "Sound"
ICON = "volume"
ORDER = 22


def _slider(value, on_change) -> QSlider:
    s = QSlider(Qt.Horizontal)
    s.setRange(0, 150)
    s.setValue(int(value if value is not None else 0))
    s.setTracking(False)                    # one pactl call when you let go, not one per pixel
    s.setFixedWidth(130)
    s.setToolTip("Volume (over 100% boosts quiet sources)")
    s.valueChanged.connect(on_change)
    return s


class Page:
    def __init__(self):
        self.widget, v = scrolling_page("Sound", "Where sound plays, how loud each app is, and the fix for no "
                                                 "sound. Outputs that are switched off (like a monitor's HDMI or "
                                                 "DisplayPort speakers) are listed too.")
        self.available = sys.platform.startswith("linux") and bool(shutil.which("pactl"))
        self.msg = QLabel("" if self.available else "Sound settings need PipeWire (HalOS), so nothing here works "
                                                    "on this system.")
        self.msg.setObjectName("Muted")
        self.msg.setWordWrap(True)
        self.msg.setTextInteractionFlags(Qt.TextSelectableByMouse)

        fix_row = QHBoxLayout()
        self.fix = QPushButton("Fix the sound")
        self.fix.setToolTip("Turn on a switched-off sound card, restart PipeWire if needed, pick a working output, "
                            "unmute, and move what's playing to it")
        self.fix.clicked.connect(self.repair)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        fix_row.addWidget(self.fix)
        fix_row.addWidget(refresh)
        fix_row.addStretch(1)
        v.addLayout(fix_row)
        v.addWidget(self.msg)

        self.outs_box = QGroupBox("Outputs")
        self.outs = QGridLayout(self.outs_box)
        self.outs.setColumnStretch(0, 1)
        v.addWidget(self.outs_box)

        self.multi_box = QGroupBox("Play on several outputs at once")
        mv = QVBoxLayout(self.multi_box)
        self.multi = QVBoxLayout()
        mv.addLayout(self.multi)
        row = QHBoxLayout()
        self.combine_btn = QPushButton("Play on the checked outputs")
        self.combine_btn.clicked.connect(self.combine)
        self.uncombine_btn = QPushButton("Stop playing on several")
        self.uncombine_btn.setObjectName("Ghost")
        self.uncombine_btn.clicked.connect(lambda: self.run(sound.uncombine, "Back to one output."))
        row.addWidget(self.combine_btn)
        row.addWidget(self.uncombine_btn)
        row.addStretch(1)
        mv.addLayout(row)
        v.addWidget(self.multi_box)

        self.apps_box = QGroupBox("Apps")
        self.apps = QGridLayout(self.apps_box)
        self.apps.setColumnStretch(0, 1)
        v.addWidget(self.apps_box)
        v.addStretch(1)

        self._outputs, self._apps = [], []
        for w in (self.fix, refresh, self.outs_box, self.multi_box, self.apps_box):
            w.setEnabled(self.available)
        if self.available:
            self.refresh()

    # ------------------------------------------------------------------ reading
    def refresh(self):
        run_async(lambda: (sound.outputs(), sound.apps()), self.show_state,
                  lambda e: self.msg.setText(f"Couldn't read the sound setup: {e}"))

    def show_state(self, state):
        self._outputs, self._apps = state
        self._fill_outputs()
        self._fill_multi()
        self._fill_apps()

    def _fill_outputs(self):
        clear_layout(self.outs)
        if not self._outputs:
            self.outs.addWidget(QLabel("No outputs found. Try Fix the sound."), 0, 0)
        for i, o in enumerate(self._outputs):
            name = QLabel(o["label"])
            name.setMinimumWidth(160)
            name.setWordWrap(True)
            name.setStyleSheet("font-weight: 600;" if o["default"] else "")
            if o["kind"] == "profile":
                state = "Switched off" + ("" if o["available"] else " · no screen detected")
            else:
                state = "In use" if o["default"] else ("Plugged in" if o["available"] else "Unplugged")
            st = QLabel(state)
            st.setObjectName("Muted")
            self.outs.addWidget(name, i, 0)
            self.outs.addWidget(st, i, 1)
            if o["kind"] == "sink":
                self.outs.addWidget(_slider(o["percent"], lambda p, n=o["name"]: self.run(
                    lambda: sound.set_volume(n, p))), i, 2)
                mute = QCheckBox("Mute")
                mute.setChecked(o["mute"])
                mute.toggled.connect(lambda m, n=o["name"]: self.run(lambda: sound.set_mute(n, m)))
                self.outs.addWidget(mute, i, 3)
                test = QPushButton("Test")
                test.setObjectName("Ghost")
                test.setToolTip("Play a short chime on this output")
                test.clicked.connect(lambda _c=False, n=o["name"]: sound.test_sound(n) or self.msg.setText(
                    "There's no sound file or player to test with."))
                self.outs.addWidget(test, i, 4)
            if not o["default"]:
                use = QPushButton("Turn on and use" if o["kind"] == "profile" else "Use")
                use.clicked.connect(lambda _c=False, o=o: self.use(o))
                self.outs.addWidget(use, i, 5)

    def _fill_multi(self):
        clear_layout(self.multi)
        self._checks = []
        sinks = [o for o in self._outputs if o["kind"] == "sink" and not o["combined"]]
        for o in sinks:
            c = QCheckBox(o["label"])
            c.setProperty("sink", o["name"])
            self._checks.append(c)
            self.multi.addWidget(c)
        hint = QLabel("Check two or more, e.g. the monitor and Bluetooth headphones. Switched-off outputs need "
                      "“Turn on and use” first." if len(sinks) > 1 else "This needs at least two outputs.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        self.multi.addWidget(hint)
        self.combine_btn.setEnabled(len(sinks) > 1)
        self.uncombine_btn.setVisible(any(o["combined"] for o in self._outputs))

    def _fill_apps(self):
        clear_layout(self.apps)
        if not self._apps:
            self.apps.addWidget(QLabel("Nothing is playing right now."), 0, 0)
        sinks = [o for o in self._outputs if o["kind"] == "sink"]
        for i, a in enumerate(self._apps):
            name = QLabel(a["app"] + (f" · {a['media']}" if a["media"] else ""))
            name.setWordWrap(True)
            where = QComboBox()
            for o in sinks:
                where.addItem(o["label"], o["name"])
            where.setCurrentIndex(max(0, where.findData(a["sink"])))
            where.activated.connect(lambda idx, a=a, w=where: self.run(lambda: sound.move_app(a["id"], w.itemData(idx)),
                                                                     f"{a['app']} now plays on {w.itemText(idx)}."))
            self.apps.addWidget(name, i, 0)
            self.apps.addWidget(where, i, 1)
            self.apps.addWidget(_slider(a["percent"], lambda p, a=a: self.run(
                lambda: sound.set_app_volume(a["id"], p))), i, 2)
            mute = QCheckBox("Mute")
            mute.setChecked(a["mute"])
            mute.toggled.connect(lambda m, a=a: self.run(lambda: sound.set_app_mute(a["id"], m)))
            self.apps.addWidget(mute, i, 3)

    # ------------------------------------------------------------------ changing
    def run(self, fn, done_text: str = ""):
        def done(_r):
            if done_text:                  # a change that alters the lists (route, combine): read them again
                self.msg.setText(done_text)
                self.refresh()
        run_async(fn, done, lambda e: self.msg.setText(f"That didn't work: {e}"))

    def use(self, o):
        self.msg.setText(f"Switching to {o['label']}…")

        def done(sink_name):
            self.msg.setText(f"Sound now plays on {o['label']}." if sink_name else
                             f"{o['label']} didn't turn into an output. If it's your monitor, check its speakers "
                             "are on and its input is this PC, then try the next HDMI/DisplayPort output.")
            self.refresh()
        run_async(lambda: sound.use_output(o), done, lambda e: self.msg.setText(f"That didn't work: {e}"))

    def combine(self):
        names = [c.property("sink") for c in self._checks if c.isChecked()]
        if len(names) < 2:
            self.msg.setText("Check at least two outputs.")
            return
        self.run(lambda: sound.combine(names), f"Sound now plays on {len(names)} outputs at once.")

    def repair(self):
        self.fix.setEnabled(False)
        self.msg.setText("Checking the sound…")

        def done(r):
            self.fix.setEnabled(True)
            self.msg.setText(r["message"])
            self.refresh()

        def failed(e):
            self.fix.setEnabled(True)
            self.msg.setText(f"The sound fix stopped: {e}")
        run_async(audio_doctor.repair, done, failed)


def build() -> QWidget:
    page = Page()
    page.widget._page = page
    return page.widget
