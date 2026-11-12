"""Settings page "Camera presence": off until you turn it on. Lock when you leave, wake the screen when you're
back, pause what's playing when you look away. Everything runs on this PC; no picture is kept or sent."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox

from core import presence
from core.config import config
from ui.widgets import Page

TITLE = "Camera presence"
ICON = "user"
ORDER = 25
GROUP = "SAINT"


class PresencePage(Page):
    def __init__(self, runner_factory=None):
        super().__init__(TITLE, "Let SAINT notice when you sit down and leave. Off until you turn it on.", scroll=True)
        self.factory = runner_factory or (lambda s: presence.PresenceRunner(s))
        self.runner = None
        about = QLabel("How it works: a few small camera frames a second are checked for a face on this PC and thrown "
                       "away at once. No picture is saved or sent anywhere. While it's on, your camera's light is on.\n"
                       "A PC that's asleep has its camera off, so to have it wake when you come back, choose "
                       "\"Turn the screen off\" below instead of \"Sleep\".")
        about.setWordWrap(True)
        about.setObjectName("Muted")
        self.root.addWidget(about)
        self.on = QCheckBox("Use the camera to notice when I'm here")
        self.on.setChecked(bool(config.get("presence.enabled", False)))
        self.on.toggled.connect(self.toggle)
        self.root.addWidget(self.on)
        form = QFormLayout()
        self.lock = self._minutes(config.get("presence.lock_after", 120) // 60, 0, 60)
        form.addRow("Lock when I've been away for (minutes, 0 = never)", self.lock)
        self.long = self._minutes(config.get("presence.long_away_after", 600) // 60, 0, 240)
        form.addRow("Then, after (minutes, 0 = never)", self.long)
        self.long_kind = QComboBox()
        self.long_kind.addItem("Turn the screen off (wakes when I'm back)", "screen_off")
        self.long_kind.addItem("Sleep (needs a key press to wake)", "sleep")
        self.long_kind.setCurrentIndex(0 if config.get("presence.long_away", "screen_off") == "screen_off" else 1)
        self.long_kind.currentIndexChanged.connect(self.save)
        form.addRow("", self.long_kind)
        self.media = QCheckBox("Pause what's playing when I look away, and play it when I look back")
        self.media.setChecked(config.get("presence.pause_media_after", 6) > 0)
        self.media.toggled.connect(self.save)
        form.addRow("", self.media)
        self.wake = QCheckBox("Wake the screen when I come back (it stays locked)")
        self.wake.setChecked(bool(config.get("presence.wake_on_return", True)))
        self.wake.toggled.connect(self.save)
        form.addRow("", self.wake)
        self.focus = self._minutes(config.get("presence.break_after", 0) // 60, 0, 240)
        form.addRow("Focus: suggest a short break after this long at the screen (minutes, 0 = never)", self.focus)
        self.root.addLayout(form)
        self.status = QLabel("Off.")
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)
        self.root.addStretch(1)
        if self.on.isChecked():
            self.toggle(True)

    def _minutes(self, value, lo, hi):
        box = QSpinBox()
        box.setRange(lo, hi)
        box.setValue(int(value))
        box.valueChanged.connect(self.save)
        return box

    def settings(self) -> presence.Settings:
        return presence.Settings(lock_after=self.lock.value() * 60.0, long_away_after=self.long.value() * 60.0,
                                 long_away=self.long_kind.currentData(),
                                 pause_media_after=6.0 if self.media.isChecked() else 0.0,
                                 wake_on_return=self.wake.isChecked(), break_after=self.focus.value() * 60.0)

    def save(self, *_):
        s = self.settings()
        for key, value in (("lock_after", s.lock_after), ("long_away_after", s.long_away_after),
                           ("long_away", s.long_away), ("pause_media_after", s.pause_media_after),
                           ("wake_on_return", s.wake_on_return), ("break_after", s.break_after)):
            config.set(f"presence.{key}", value)
        if self.runner:
            self.runner.presence.settings = s

    def toggle(self, on: bool):
        config.set("presence.enabled", bool(on))
        if not on:
            if self.runner:
                self.runner.stop()
            self.runner = None
            self.status.setText("Off. The camera isn't used.")
            return
        self.runner = self.factory(self.settings())
        if self.runner.start():
            self.status.setText("On. SAINT checks for a face a few times a second, on this PC only.")
        else:
            self.status.setText(self.runner.error)
            self.on.blockSignals(True)
            self.on.setChecked(False)
            self.on.blockSignals(False)
            config.set("presence.enabled", False)
            self.runner = None


def build():
    return PresencePage()
