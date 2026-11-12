"""
ui/settings_ui.py

SAINT's settings pages. Every field is bound to a config key; Save writes
them all to data/config.json and emits SETTINGS_CHANGED, which the runtime
applies live (wake word reload, microphone restart, TTS re-init, log level,
appearance) — no restart required for most settings. The pages appear in the
one settings window (ui/saintos_center.py), under SAINT in its rail.
"""

import sys
import os
import threading
from typing import Callable, List, Tuple

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFontComboBox,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.config import config
from core.events import event_bus, EventType
from core.module_manager import module_manager
from core.paths import PROJECT_ROOT, data_dir, display_path, resolve_project_path
from core.permissions import permission_manager
from ui.reactive import ui_bus
from ui.theme import current_palette
from ui.widgets import LevelMeter, Switch, run_async

PROVIDERS = [("Ollama (on this PC)", "ollama"), ("Claude (Anthropic)", "anthropic"),
             ("OpenAI-compatible server", "openai"), ("Mock (testing)", "mock")]
ACCENTS = ["#feaa34", "#f97316", "#2563eb", "#7c3aed", "#db2777", "#dc2626", "#ea580c", "#ca8a04", "#16a34a", "#0891b2", "#64748b"]


def voice_tone(text: str) -> str:
    """A state mark for a voice status line: green when it's proven, red when it's broken or a fallback."""
    low = text.lower()
    if any(w in low for w in ("missing", "failed", "not kokoro", "fallback", "none (", "unavailable",
                              "recorded silence")):
        return "danger"
    if low.startswith(("passed", "kokoro (", "kokoro ready")) or "(present)" in low or "(downloaded)" in low:
        return "success"
    return ""


class SettingsUI(QWidget):
    CATEGORIES = ["General", "Voice", "AI", "Wake Word", "Spotify", "Memory", "Automation",
                  "Desktop Control", "Gaming Mode", "MCP", "Appearance", "Advanced"]

    def __init__(self, on_appearance_changed: Callable = None, on_theme_changed: Callable = None):
        super().__init__()
        self.on_appearance_changed = on_appearance_changed or on_theme_changed
        self._bindings: List[Tuple[str, Callable, Callable]] = []
        self._loading = False
        self.category_pages = {}
        self._page = None
        self._build()
        self.load()
        event_bus.event_occurred.connect(self._on_event)

    # ------------------------------------------------------------------ #
    # Binding helpers
    # ------------------------------------------------------------------ #
    def _bind(self, key, getter, setter):
        self._bindings.append((key, getter, setter))

    def _check(self, key, text, live: str = ""):
        """An on/off switch bound to ``key``. ``live``: applied the moment it's
        flipped (no Save needed) and shown — ``live`` is what to say."""
        w = Switch(text)
        self._bind(key, w.isChecked, lambda v: w.setChecked(bool(v)))
        if live:
            w.toggled.connect(lambda on, k=key, msg=live: self._apply_live(k, on, msg))
        return w

    def _apply_live(self, key, value, message=""):
        """Settings you want to *see* change (the Halo, action notices, the mini
        player) take effect immediately, with a short preview."""
        if self._loading:
            return
        config.set(key, value)
        ui_bus.setting_changed.emit(key)
        if message:
            on = value not in (False, "off", None)
            pal = current_palette()
            self.status.setText(message.format(state="on" if on else "off"))
            self.status.setStyleSheet(f"color:{pal.success if on else pal.muted};")

    def _combo(self, key, items, editable=False, data=None):
        w = QComboBox()
        w.setEditable(editable)
        if data is None:
            w.addItems(items)
            self._bind(key, w.currentText, lambda v: w.setCurrentText(str(v if v is not None else "")))
        else:
            for label, value in zip(items, data):
                w.addItem(label, value)
            self._bind(key, w.currentData,
                       lambda v: w.setCurrentIndex(max(0, w.findData(v))))
        return w

    def _spin(self, key, lo, hi, step=1.0, decimals=0, suffix=""):
        w = QDoubleSpinBox() if decimals else QSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        if decimals:
            w.setDecimals(decimals)
        if suffix:
            w.setSuffix(suffix)
        conv = float if decimals else int
        self._bind(key, lambda: conv(w.value()), lambda v: w.setValue(conv(v if v is not None else lo)))
        return w

    def _line(self, key, placeholder="", password=False):
        w = QLineEdit()
        w.setPlaceholderText(placeholder)
        if password:
            w.setEchoMode(QLineEdit.Password)
        self._bind(key, lambda: w.text().strip(), lambda v: w.setText("" if v is None else str(v)))
        return w

    def _section(self, title, desc=""):
        box = QGroupBox(title.replace("&", "&&"))
        form = QFormLayout(box)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        if desc:
            d = QLabel(desc)
            d.setObjectName("Muted")
            d.setWordWrap(True)
            form.addRow(d)
        return box, form

    def _row(self, form, label, widget, help_text=""):
        if type(widget) is QWidget:
            widget.setObjectName("FormRow")   # transparent container for composite rows
        form.addRow(label, widget)
        if help_text:
            h = QLabel(help_text)
            h.setObjectName("Faint")
            h.setWordWrap(True)
            form.addRow("", h)

    def _new_page(self, name):
        self._page = name
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(4, 0, 12, 12)
        return w, lay

    def _add_page(self, w, lay):
        lay.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(w)
        self.category_pages[self._page] = scroll

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def _build(self):
        """The categories' pages (``category_pages``, placed in the one settings rail by ui/saintos_center.py)
        and, as this widget itself, the Save bar they share."""
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 8, 32, 14)
        for builder in (self._build_general, self._build_voice, self._build_ai, self._build_wake,
                        self._build_spotify, self._build_memory, self._build_automation,
                        self._build_desktop, self._build_gaming, self._build_mcp, self._build_appearance,
                        self._build_advanced):
            builder()

        foot = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        foot.addWidget(self.status, 1)
        revert = QPushButton("Revert")
        revert.clicked.connect(self.load)
        save = QPushButton("Save settings")
        save.setObjectName("Primary")
        save.clicked.connect(self.save)
        foot.addWidget(revert)
        foot.addWidget(save)
        root.addLayout(foot)

    # ---- GENERAL -------------------------------------------------------
    def _build_general(self):
        w, lay = self._new_page("General")
        box, f = self._section("Startup & background",
                               "SAINT's voice loop, reminders and Spotify keep running when the window is "
                               "closed to the tray or not focused.")
        self._row(f, "Start listening on launch", self._check("voice.auto_start", "Enabled"))
        self._row(f, "Close button", self._check("notifications.close_to_tray", "Keep running in the tray"))
        self._row(f, "Start minimized", self._check("notifications.start_minimized", "Start hidden in the tray"))
        self._row(f, "Notifications", self._check("notifications.tray", "Show tray notifications (reminders, errors)"))
        lay.addWidget(box)
        box, f = self._section("Modules", "Turn whole capabilities on or off.")
        for key, label in (("modules.voice", "Voice"), ("modules.memory", "Memory"),
                           ("modules.automation", "Automations"), ("modules.desktop", "Desktop control"),
                           ("modules.vision", "Screen awareness"), ("modules.spotify", "Spotify")):
            self._row(f, label, self._check(key, "Enabled"))
        lay.addWidget(box)
        self._add_page(w, lay)

    # ---- VOICE ------------------------------------------------------------
    def _build_voice(self):
        w, lay = self._new_page("Voice")
        lay.addWidget(self._build_voice_status())
        box, f = self._section("Microphone")
        self.mic_combo = QComboBox()
        self._bind("voice.mic_device", self.mic_combo.currentData,
                   lambda v: self.mic_combo.setCurrentIndex(max(0, self.mic_combo.findData(self._mic_name(v)))))
        self._populate_mics()
        mic_row = QHBoxLayout()
        mic_row.addWidget(self.mic_combo, 1)
        self.mic_test = QPushButton("Test (3 s)")
        self.mic_test.clicked.connect(self._test_mic)
        mic_row.addWidget(self.mic_test)
        mw = QWidget()
        mw.setLayout(mic_row)
        self._row(f, "Input device", mw)
        self._row(f, "Mode", self._combo("voice.mode", ["Always on", "Push to talk"], data=["always_on", "push_to_talk"]))
        self._row(f, "Speech threshold", self._spin("voice.vad_start_threshold", 0.001, 0.2, 0.001, 3),
                  "Raise it if background noise starts utterances; lower it if quiet speech is missed.")
        self._row(f, "End-of-speech silence", self._spin("voice.silence_duration_ms", 200, 3000, 50, 0, " ms"))
        self._row(f, "Noise suppression", self._check("voice.noise_suppression", "Subtract the rolling noise floor"))
        self._row(f, "Speech detector", self._combo("voice.vad_backend", ["Silero (speech vs. music/noise)", "Energy (RMS)"],
                                                    data=["silero", "rms"]),
                  "Silero tells speech from music and TV, so commands end cleanly while music plays.")
        self._row(f, "Longest utterance", self._spin("voice.max_utterance_sec", 5.0, 60.0, 1.0, 0, " s"),
                  "Cut an utterance that never pauses (music vocals, TV) and process what was heard.")
        lay.addWidget(box)

        box, f = self._section("Interruptions (barge-in)",
                               "The microphone stays on while SAINT speaks. SAINT compares what the mic hears "
                               "with what it is playing, so its own voice doesn't interrupt it but yours does.")
        self._row(f, "Allow interrupting", self._check("voice.barge_in_enabled", "Enabled"))
        self._row(f, "Stop words", self._check("voice.barge_in_spotter", "“Stop”, “wait”, “shut up” always cut me off"),
                  "Works even on speakers, where your voice and mine are hard to tell apart by loudness.")
        self._row(f, "Quietest interruption", self._spin("voice.barge_in_min_rms", 0.0, 0.2, 0.005, 3),
                  "Mic level below this never interrupts (music and room noise). It also rises with how loud "
                  "you normally talk.")
        self._row(f, "Speech needed to interrupt", self._spin("voice.barge_in_min_ms", 90, 1500, 30, 0, " ms"))
        self._row(f, "Echo margin", self._spin("voice.barge_in_echo_margin", 1.0, 8.0, 0.1, 1),
                  "Higher = harder to interrupt (use with loud speakers); lower = easier (headphones).")
        lay.addWidget(box)

        box, f = self._section("Knowing it's you")
        # The old "Wake word off" switch here looked like the wake word itself but
        # wasn't (2026-09-30). The wake word lives on the Wake Word page only.
        note = QLabel("Without “Hey SAINT”, SAINT only answers commands, questions and answers to its own "
                      "questions, and ignores quiet voices from videos, games and calls. Turn the wake word "
                      "on or off on the Wake Word page.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self._row(f, "No wake word", note)
        self._row(f, "Learn my voice", self._check("voice.learn_my_voice",
                                                   "Build a voice profile from what I say to SAINT by name"))
        self._row(f, "Only my voice", self._check("voice.speaker_filter",
                                                  "Ignore voices that aren't mine unless they say “SAINT”"),
                  "Uses the voice profile once it has enough samples. Nothing but numbers is stored.")
        prof = QWidget()
        pl = QHBoxLayout(prof)
        pl.setContentsMargins(0, 0, 0, 0)
        self.voice_profile_label = QLabel("")
        self.voice_profile_label.setObjectName("Muted")
        reset = QPushButton("Forget my voice")
        reset.clicked.connect(self._reset_voice_profile)
        pl.addWidget(self.voice_profile_label, 1)
        pl.addWidget(reset)
        self._row(f, "Voice profile", prof)
        self._refresh_voice_profile()
        lay.addWidget(box)

        box, f = self._section("Speech recognition (STT)")
        self._row(f, "Engine", self._combo("voice.stt_backend", ["faster_whisper", "mock"]))
        self._row(f, "Model", self._combo("voice.stt_model", ["tiny.en", "base.en", "small.en", "medium.en", "large-v3-turbo",
                                                              "large-v3", "distil-large-v3"], editable=True),
                  "HalOS picks one for this PC at first boot; what you choose here stays.")
        self._row(f, "Device", self._combo("voice.stt_device", ["cuda", "cpu"]))
        self._row(f, "Precision", self._combo("voice.stt_compute_type", ["float16", "int8_float16", "int8", "float32"]))
        self._row(f, "Language", self._line("voice.stt_language", "en or auto"))
        self._row(f, "Min confidence (no wake word)", self._spin("voice.min_stt_confidence", 0.0, 1.0, 0.05, 2))
        lay.addWidget(box)

        box, f = self._section("Speech output (TTS)")
        self._row(f, "Engine", self._combo("voice.tts_backend", ["kokoro", "qwen", "mock"]))
        from modules.voice.voices import KOKORO_VOICES
        labels = [label for _id, label in KOKORO_VOICES]
        ids = [vid for vid, _label in KOKORO_VOICES]
        self._row(f, "Voice", self._combo("voice.tts_voice", labels, data=ids))
        self._row(f, "Blend with", self._combo("voice.tts_voice_blend", ["Nothing (one voice)"] + labels,
                                               data=[""] + ids),
                  "Mix two Kokoro voices into a new one.")
        self._row(f, "Blend amount", self._combo("voice.tts_voice_blend_pct", ["A touch (25%)", "Half (50%)",
                                                                              "Mostly the blend (75%)"],
                                                 data=[25, 50, 75]))
        self._row(f, "Device", self._combo("voice.tts_device", ["cuda", "cpu", "auto"]))
        self._row(f, "Speed", self._spin("voice.tts_speed", 0.5, 2.0, 0.05, 2))
        from modules.voice.output_policy import VOLUME_MAX, set_voice_volume
        self.voice_volume = QSlider(Qt.Horizontal)
        self.voice_volume.setRange(0, VOLUME_MAX)
        self.voice_volume_label = QLabel("")
        self.voice_volume_label.setMinimumWidth(40)
        self.voice_volume.valueChanged.connect(lambda v: self.voice_volume_label.setText(f"{v}%"))
        # Live: the next thing SAINT says uses it (Save keeps it too).
        self.voice_volume.sliderReleased.connect(lambda: set_voice_volume(self.voice_volume.value()))
        vr = QHBoxLayout()
        vr.setContentsMargins(0, 0, 0, 0)
        vr.addWidget(self.voice_volume, 1)
        vr.addWidget(self.voice_volume_label)
        vw = QWidget()
        vw.setLayout(vr)
        self._bind("voice.volume", lambda: self.voice_volume.value(),
                   lambda v: self.voice_volume.setValue(int(100 if v is None else v)))
        self._row(f, "Volume", vw, "How loud SAINT's own voice is — Spotify and Windows aren't changed. Above "
                                   "100% boosts a quiet voice. You can also say “talk louder” or “voice volume 60”.")
        self.voice_preview = QPushButton("Hear it")
        self.voice_preview.clicked.connect(self._preview_voice)
        self._row(f, "", self.voice_preview, "Saves the voice settings above and says a line with them.")
        self._row(f, "CPU fallback", self._check("voice.tts_allow_cpu_fallback", "Use CPU if CUDA is unavailable"))
        lay.addWidget(box)
        self._add_page(w, lay)

    def _build_voice_status(self):
        """What SAINT really speaks and hears with, from files and tests (core/voice_check.py), never the config alone."""
        sheet = QFrame()
        sheet.setObjectName("Panel")
        outer = QVBoxLayout(sheet)
        outer.setContentsMargins(18, 14, 18, 14)
        self.voice_grid = QGridLayout()
        self.voice_grid.setHorizontalSpacing(18)
        self.voice_grid.setVerticalSpacing(9)
        self.voice_grid.setColumnStretch(2, 1)
        outer.addLayout(self.voice_grid)
        row = QHBoxLayout()
        self.test_tts = QPushButton("Test Kokoro voice")
        self.test_stt = QPushButton("Test Whisper")
        self.test_tts.clicked.connect(lambda: self._run_voice_test("kokoro"))
        self.test_stt.clicked.connect(lambda: self._run_voice_test("whisper"))
        row.addWidget(self.test_tts)
        row.addWidget(self.test_stt)
        row.addStretch()
        outer.addLayout(row)
        self.voice_test_msg = QLabel("")
        self.voice_test_msg.setWordWrap(True)
        outer.addWidget(self.voice_test_msg)
        return sheet

    def _refresh_voice_status(self):
        from core import health, voice_check
        run_async(lambda: voice_check.status(health._tts_service()), self._show_voice_status,
                  lambda e: self.voice_test_msg.setText(f"Couldn't read the voice system: {e}"))

    def _show_voice_status(self, res):
        pal = current_palette()
        while self.voice_grid.count():
            item = self.voice_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for row, (key, val) in enumerate(res.items()):
            tone = voice_tone(str(val))
            dot = QLabel("●" if tone else "○")
            dot.setStyleSheet(f"color: {getattr(pal, tone) if tone else pal.faint}; font-size: 10px;")
            name = QLabel(key.upper())
            name.setObjectName("StatLabel")
            value = QLabel(str(val))
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.voice_grid.addWidget(dot, row, 0)
            self.voice_grid.addWidget(name, row, 1)
            self.voice_grid.addWidget(value, row, 2)

    def _run_voice_test(self, which):
        from core import voice_check
        self.test_tts.setEnabled(False)
        self.test_stt.setEnabled(False)

        def done(res):
            self.test_tts.setEnabled(True)
            self.test_stt.setEnabled(True)
            self.voice_test_msg.setText(("Passed: " if res["ok"] else "FAILED: ") + res["detail"])
            self._refresh_voice_status()

        def fail(e):
            done({"ok": False, "detail": str(e)})
        if which == "kokoro":
            self.voice_test_msg.setText("Synthesising with Kokoro (downloads the voice first if it's missing)…")
            run_async(voice_check.test_kokoro, done, fail)
        else:
            self.voice_test_msg.setText("Recording 4 seconds, say something…")
            run_async(voice_check.test_whisper, done, fail)

    def _refresh_voice_profile(self):
        try:
            from modules.voice.speaker import speaker_profile, MIN_SAMPLES
            n = speaker_profile.samples
            self.voice_profile_label.setText(
                f"Ready ({n} samples)" if n >= MIN_SAMPLES else
                f"Learning — {n} of {MIN_SAMPLES} samples (say “Hey SAINT, …” a few more times)")
        except Exception as e:
            self.voice_profile_label.setText(f"Unavailable ({e})")

    def _reset_voice_profile(self):
        from modules.voice.speaker import speaker_profile
        speaker_profile.reset()
        self._refresh_voice_profile()

    def _preview_voice(self):
        """Apply just the voice settings and have SAINT say something with them."""
        keys = ("voice.tts_voice", "voice.tts_voice_blend", "voice.tts_voice_blend_pct", "voice.tts_speed",
                "voice.tts_device", "voice.tts_backend")
        for key, getter, _ in self._bindings:
            if key in keys:
                config.set(key, getter(), persist=False)
        try:
            config.save()
            from core.runtime import runtime
            runtime.apply_settings()
            tts = runtime.tts
        except Exception as e:
            self.status.setText(f"Couldn't apply the voice: {e}")
            return
        self.status.setText("Loading the voice…")

        def run():
            import time
            deadline = time.time() + 30
            while tts is not None and not tts.is_ready and time.time() < deadline:
                time.sleep(0.2)
            if tts is not None:
                tts.speak("Hi, I'm SAINT. This is how I'll sound from now on.")
        import threading
        threading.Thread(target=run, daemon=True, name="voice-preview").start()

    @staticmethod
    def _mic_name(value):
        """The mic setting is a name; an old config holds a device number."""
        if isinstance(value, int) and not isinstance(value, bool):
            try:
                import sounddevice as sd
                return sd.query_devices(value)["name"]
            except Exception:
                return None
        return value

    def _populate_mics(self):
        # Stored by name: a device's number changes when Windows adds one (AirPods, a webcam).
        from modules.voice.mic_select import is_bluetooth_headset
        self.mic_combo.clear()
        self.mic_combo.addItem("System default", None)
        try:
            import sounddevice as sd
            for dev in sd.query_devices():
                if dev["max_input_channels"] > 0 and dev.get("hostapi", 0) == 0:
                    bt = " — Bluetooth: drops headphones to call quality" if is_bluetooth_headset(dev["name"]) else ""
                    self.mic_combo.addItem(f"{dev['name']}{bt}", dev["name"])
            current = self._mic_name(config.get("voice.mic_device", None))
            if current and self.mic_combo.findData(current) < 0:
                self.mic_combo.addItem(f"{current} (not connected)", current)
        except Exception as e:
            self.mic_combo.addItem(f"(couldn't list devices: {e})", None)

    def _test_mic(self):
        name = self.mic_combo.currentData()
        try:
            import sounddevice as sd
            from modules.voice.mic_select import pick_input
            dev = pick_input(name, sd.query_devices(), None, allow_bluetooth=True)[0] if name else None
        except Exception:
            dev = None
        self.mic_test.setEnabled(False)
        self.mic_test.setText("Recording…")

        def run():
            import sounddevice as sd
            info = sd.query_devices(dev, "input")
            fs = int(info["default_samplerate"])
            rec = sd.rec(int(3 * fs), samplerate=fs, channels=1, dtype="int16", device=dev)
            sd.wait()
            sd.play(rec, fs)
            sd.wait()
            import numpy as np
            return float(np.sqrt(np.mean((rec.astype("float32") / 32768) ** 2)))

        def done(rms):
            self.mic_test.setEnabled(True)
            self.mic_test.setText("Test (3 s)")
            self.status.setText(f"Mic test finished — average level {rms:.3f}"
                                + (" (very quiet — check the input device)" if rms < 0.003 else ""))

        def fail(e):
            self.mic_test.setEnabled(True)
            self.mic_test.setText("Test (3 s)")
            self.status.setText(f"Mic test failed: {e}")
        run_async(run, done, fail)

    # ---- AI --------------------------------------------------------------
    def _build_ai(self):
        w, lay = self._new_page("AI")
        self.pc_label = QLabel("")
        self.pc_label.setObjectName("Muted")
        self.pc_label.setWordWrap(True)
        lay.addWidget(self.pc_label)
        box, f = self._section("Language model", "Local first: Ollama on this PC. Claude and other hosted providers "
                                                 "are optional.")
        self.provider_combo = self._combo("ai.provider", [p[0] for p in PROVIDERS], data=[p[1] for p in PROVIDERS])
        self._row(f, "Provider", self.provider_combo)
        self.model_combo = self._combo("ai.model", [config.get("ai.model", "llama3.1")], editable=True)
        mr = QHBoxLayout()
        mr.setContentsMargins(0, 0, 0, 0)
        mr.addWidget(self.model_combo, 1)
        refresh = QPushButton("Refresh list")
        refresh.clicked.connect(self._refresh_models)
        mr.addWidget(refresh)
        self.pull_btn = QPushButton("Download model")
        self.pull_btn.clicked.connect(self._pull_model)
        mr.addWidget(self.pull_btn)
        mw = QWidget()
        mw.setLayout(mr)
        self._row(f, "Model", mw)
        self.base_url_line = self._line("ai.base_url", "http://localhost:11434")
        self._row(f, "Address", self.base_url_line)
        self.openai_key_line = self._line("ai.api_key", "for this server; kept in the secret store", password=True)
        self._row(f, "API key", self.openai_key_line)
        self.temperature_spin = self._spin("ai.temperature", 0.0, 2.0, 0.1, 2)
        self._row(f, "Temperature", self.temperature_spin)
        self._row(f, "Timeout", self._spin("ai.timeout_seconds", 5, 300, 5, 0, " s"))
        test = QPushButton("Test connection")
        self.test_reply = QPushButton("Test a reply")
        self.ai_status = QLabel("")
        self.ai_status.setWordWrap(True)
        test.clicked.connect(self._test_ai)
        self.test_reply.clicked.connect(self._test_ai_reply)
        tr = QHBoxLayout()
        tr.setContentsMargins(0, 0, 0, 0)
        tr.addWidget(test)
        tr.addWidget(self.test_reply)
        tr.addWidget(self.ai_status, 1)
        tw = QWidget()
        tw.setObjectName("FormRow")
        tw.setLayout(tr)
        f.addRow("", tw)
        self._ai_form = f
        lay.addWidget(box)
        lay.addWidget(self._build_claude())
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        self._pull_timer = QTimer(self)
        self._pull_timer.setInterval(2000)
        self._pull_timer.timeout.connect(self._refresh_ai_progress)
        box, f = self._section("Agent")
        self._row(f, "Command router", self._check("agent.enabled", "Handle common commands directly with tools"))
        self._row(f, "LLM tool calling", self._check("ai.tool_calling", "Let the model call SAINT's tools"))
        self._row(f, "Max tool steps", self._spin("ai.max_tool_steps", 1, 8))
        self._row(f, "Confirmation timeout", self._spin("agent.confirm_timeout_sec", 5, 120, 5, 0, " s"))
        self._row(f, "Context turns", self._spin("voice.max_context_turns", 1, 20))
        self._row(f, "Max reply tokens", self._spin("ai.max_tokens", 0, 2048, 10, 0),
                  "Hard cap on generated tokens. 0 = no cap. Keep low (120–200) for a voice assistant.")
        self.system_prompt = QPlainTextEdit()
        self.system_prompt.setMaximumHeight(120)
        self._bind("voice.system_prompt", lambda: self.system_prompt.toPlainText().strip(),
                   lambda v: self.system_prompt.setPlainText(v or ""))
        self._row(f, "Personality / system prompt", self.system_prompt)
        lay.addWidget(box)

        box, f = self._section("Vision",
                               "SAINT can look at your screen with a local vision model. Windows still "
                               "provides the reliable structured window/UI info; vision fills in what "
                               "isn't exposed to accessibility APIs.")
        self._row(f, "Backend",
                  self._combo("vision.analyzer", ["none", "ollama", "flux"]),
                  "'flux' = FLUX.2 Klein 4B (local). 'ollama' = any vision-capable Ollama model.")
        self._row(f, "Ollama vision model", self._line("vision.model", "e.g. llama3.2-vision"))
        self._row(f, "FLUX model id", self._line("vision.flux_model_id", "black-forest-labs/FLUX.2-Klein-4B"))
        self._row(f, "FLUX weights dir", self._line("vision.flux_model_dir", "data/vision/flux2-klein-4b"),
                  "Download once: hf download black-forest-labs/FLUX.2-Klein-4B --local-dir <this dir>")
        self._row(f, "FLUX device", self._combo("vision.flux_device", ["auto", "cuda", "cpu"]))
        self._row(f, "FLUX dtype", self._combo("vision.flux_dtype", ["float16", "bfloat16", "float32"]))
        self._row(f, "Max image side", self._spin("vision.flux_max_image_side", 256, 2048, 64, 0, " px"))
        self._row(f, "Max reply tokens (vision)", self._spin("vision.flux_max_new_tokens", 32, 512, 16))
        self._row(f, "Allow screen context",
                  self._check("vision.allow_screen_context", "Read windows/controls/text via Windows accessibility APIs"))
        self._row(f, "Keep screenshots", self._spin("vision.keep_screenshots", 0, 200))
        lay.addWidget(box)

        box, f = self._section("Web / current information",
                               "Only used when the user asks about current facts or news. Explicit "
                               "'search Google for X' commands still use browser automation.")
        self._row(f, "Provider", self._combo(
            "web.provider", ["duckduckgo_browser", "duckduckgo", "tavily", "serpapi", "none"]),
                  "'duckduckgo_browser' opens DuckDuckGo in your browser (no key). The others "
                  "return a spoken summary via API.")
        self._row(f, "API key", self._line("web.api_key", "for tavily / serpapi", password=True))
        self._row(f, "Max results", self._spin("web.max_results", 1, 10))
        self._row(f, "Answer style", self._combo("web.answer_style", ["concise", "detailed"]))
        lay.addWidget(box)
        self._add_page(w, lay)

    def _build_claude(self):
        """Claude: the key goes straight to the secret store, not through Save settings and never into a field that
        shows it again."""
        from modules.ai.providers import ANTHROPIC_MODELS
        box, f = self._section("Claude (Anthropic)", "Paste an API key to use Claude as SAINT's provider (choose it "
                                                     "above). Evolve can use the same key for Claude Code.")
        self.claude_key = QLineEdit()
        self.claude_key.setEchoMode(QLineEdit.Password)
        kr = QHBoxLayout()
        kr.setContentsMargins(0, 0, 0, 0)
        kr.addWidget(self.claude_key, 1)
        for label, slot in (("Save key", self._claude_save), ("Test", self._claude_test), ("Remove", self._claude_remove)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            kr.addWidget(b)
        kw = QWidget()
        kw.setLayout(kr)
        self._row(f, "API key", kw, "From console.anthropic.com. Kept in the secret store (KWallet), never in the "
                                    "config file or the logs. Using it is billed to your Anthropic account.")
        self.claude_status = QLabel("")
        self.claude_status.setWordWrap(True)
        self._row(f, "Status", self.claude_status)
        self._row(f, "Model", self._combo("ai.anthropic_model", ANTHROPIC_MODELS, editable=True))
        self._claude_refresh()
        return box

    def _claude_say(self, text, ok=None):
        pal = current_palette()
        self.claude_status.setText(text)
        self.claude_status.setStyleSheet("" if ok is None else f"color:{pal.success if ok else pal.danger};")

    def _claude_refresh(self):
        saved = bool(config.get("ai.anthropic_api_key", ""))
        self.claude_key.setPlaceholderText("A key is saved; paste a new one to replace it" if saved else "sk-ant-…")
        self._claude_say("A key is saved." if saved else "No key saved.")

    def _claude_save(self):
        key = self.claude_key.text().strip()
        if not key:
            self._claude_say("Paste a key first.", False)
            return
        if not config.set_secret("ai.anthropic_api_key", key):
            self._claude_say("No secret store works here (KWallet), so the key wasn't saved.", False)
            return
        self.claude_key.clear()
        self._claude_refresh()
        self._claude_test()

    def _claude_test(self):
        from modules.ai.providers import get_provider
        typed = self.claude_key.text().strip()
        self._claude_say("Asking Anthropic…")
        run_async(lambda: get_provider("anthropic").test_key(typed),
                  lambda r: self._claude_say(f"Working: {r.get('version')} ({r.get('latency_ms')} ms)." if r.get("connected")
                                             else f"Not working: {r.get('error')}.", bool(r.get("connected"))),
                  lambda e: self._claude_say(f"Not working: {type(e).__name__}.", False))

    def _claude_remove(self):
        self.claude_key.clear()
        if config.set_secret("ai.anthropic_api_key", ""):
            self._claude_refresh()
            if self.provider_combo.currentData() == "anthropic":
                self._claude_say("Key removed. SAINT's provider is still Claude: choose another one above.", False)
        else:
            self._claude_say("The secret store didn't answer, so the key is still there.", False)

    def _provider_changed(self, *_):
        """Only the fields the chosen provider uses (Claude's are in its own box)."""
        which = self.provider_combo.currentData()
        for field, on in ((self.model_combo.parentWidget(), which != "anthropic"),
                          (self.base_url_line, which in ("ollama", "openai")),
                          (self.openai_key_line, which == "openai"),
                          (self.temperature_spin, which != "anthropic")):
            self._ai_form.setRowVisible(field, on)
        self.pull_btn.setVisible(which == "ollama")
        self.test_reply.setVisible(which == "ollama")

    def _ai_form_provider(self):
        from modules.ai.providers import get_provider
        return get_provider(self.provider_combo.currentData() or "ollama"), self.base_url_line.text().strip()

    def _refresh_models(self):
        """Ask the provider chosen on the form (nothing here needs SAINT's AI module to be running)."""
        provider, base = self._ai_form_provider()

        def done(models):
            cur = self.model_combo.currentText()
            self.model_combo.clear()
            names = [m.get("name") for m in models if m.get("name")]
            self.model_combo.addItems(names or [cur])
            self.model_combo.setCurrentText(cur)
            self.ai_status.setText(f"{len(names)} models installed" if names else "No models found")

        def listed():
            try:
                return provider.list_models(base, force_refresh=True)
            except TypeError:                         # the OpenAI-compatible provider doesn't cache
                return provider.list_models(base)
        run_async(listed, done, lambda e: self.ai_status.setText(str(e)))

    def _test_ai(self):
        provider, base = self._ai_form_provider()
        self.ai_status.setText("Testing…")
        pal = current_palette()

        def done(r):
            ok = r.get("connected")
            self.ai_status.setText(f"Connected ({r.get('version', r.get('provider', ''))})" if ok
                                   else f"Not reachable: {r.get('error', '')}")
            self.ai_status.setStyleSheet(f"color:{pal.success if ok else pal.danger};")
        run_async(lambda: provider.test_connection(base), done, lambda e: self.ai_status.setText(str(e)))

    def _test_ai_reply(self):
        """A real prompt to the chosen model: running alone doesn't mean the model answers."""
        from core import health
        base, model = self.base_url_line.text().strip(), self.model_combo.currentText().strip()
        if not model:
            self.ai_status.setText("Pick or download a model first.")
            return
        self.test_reply.setEnabled(False)
        self.ai_status.setText(f"Asking {model} for a one-word reply…")

        def done(r):
            self.test_reply.setEnabled(True)
            self.ai_status.setText(("Working: " if r["state"] == health.WORKING else "FAILED: ") + r["detail"])

        def fail(e):
            self.test_reply.setEnabled(True)
            self.ai_status.setText(f"Test failed: {e}")
        run_async(lambda: health.ollama_inference(base, model), done, fail)

    def _pull_model(self):
        """Download the chosen model with its progress (core/model_pull.py; also on SAINT's System page)."""
        from core import model_pull
        model = self.model_combo.currentText().strip()
        if not model:
            self.ai_status.setText("Type the model to download, e.g. llama3.1:8b.")
            return
        if not model_pull.start(self.base_url_line.text().strip(), model):
            self.ai_status.setText("A model is already downloading.")
        self._refresh_ai_progress()

    def _refresh_ai_progress(self):
        """While this window is open: this PC's first-boot setup (core/provision.py) and any model download."""
        from core import model_pull, provision
        line = provision.describe()
        self.pc_label.setText(line)
        self.pc_label.setVisible(bool(line))
        s = model_pull.state()
        if s.get("model"):
            self.ai_status.setText(model_pull.describe(s))
        self.pull_btn.setEnabled(not s.get("running"))

    # ---- WAKE WORD ---------------------------------------------------------
    def _build_wake(self):
        w, lay = self._new_page("Wake Word")
        box, f = self._section("Wake word",
                               "SAINT listens locally for “Hey SAINT” with its own ONNX model (CPU, no "
                               "cloud). Only after hearing it does SAINT transcribe what you say.")
        self._row(f, "Wake word", self._check("voice.wake_word_enabled", "Require “Hey SAINT” before commands"))
        self.wake_status = QLabel("")
        self.wake_status.setWordWrap(True)
        self._row(f, "Status", self.wake_status)
        self.wake_meter = LevelMeter(show_threshold=True)
        self._row(f, "Live score", self.wake_meter)
        path = self._line("voice.wake_word_model_path", "data/wake/hey_saint.onnx")
        pr = QHBoxLayout()
        pr.addWidget(path, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda: self._browse_model(path))
        pr.addWidget(browse)
        pw = QWidget()
        pw.setLayout(pr)
        self._row(f, "Model file", pw, "Relative paths are resolved from the SAINT folder.")
        lay.addWidget(box)

        box, f = self._section("Detection")
        self.sens = QSlider(Qt.Horizontal)
        self.sens.setRange(5, 95)
        self.sens_label = QLabel("")
        self.sens.valueChanged.connect(lambda v: self.sens_label.setText(
            f"{v}%  (score threshold {(100 - v) / 100:.2f})"))
        sr = QHBoxLayout()
        sr.addWidget(self.sens, 1)
        sr.addWidget(self.sens_label)
        sw = QWidget()
        sw.setLayout(sr)
        self._bind("voice.wake_word_threshold", lambda: round((100 - self.sens.value()) / 100, 2),
                   lambda v: self.sens.setValue(int(round(100 - float(v or 0.5) * 100))))
        self._row(f, "Sensitivity", sw, "Higher sensitivity triggers more easily (and more falsely).")
        self._row(f, "Confirmation frames", self._spin("voice.wake_word_trigger_frames", 1, 6),
                  "Frames above the threshold needed within the detection window (1 = most responsive).")
        self._row(f, "Detection window", self._spin("voice.wake_word_window_frames", 1, 12, 1, 0, " × 80 ms"),
                  "Scores are judged over this window, so a short “Hey SAINT” with a dip still counts.")
        self._row(f, "Transcript check", self._check("voice.wake_word_transcript_check",
                                                      "Also recognise “SAINT” from speech-to-text"),
                  "The wake model is strongest on “Hey SAINT”. With this on, a short utterance it missed is "
                  "transcribed once and accepted only if it starts with “SAINT” / “Hey SAINT”.")
        self._row(f, "Transcript check limit", self._spin("voice.wake_word_transcript_max_sec", 2.0, 15.0, 0.5, 1, " s"),
                  "Longer background speech is never transcribed.")
        self._row(f, "Cooldown", self._spin("voice.wake_word_refractory_sec", 0.5, 10.0, 0.5, 1, " s"))
        self._row(f, "Command timeout", self._spin("voice.wake_word_command_timeout_sec", 2.0, 20.0, 0.5, 1, " s"),
                  "How long SAINT waits for a command after hearing its name.")
        self._row(f, "Conversation window", self._spin("voice.wake_word_followup_sec", 0.0, 120.0, 1.0, 0, " s"),
                  "After SAINT answers, keep listening this long for follow-ups (“skip that”, “turn it "
                  "down”) without the wake word. Counted from when SAINT stops talking. 0 = off.")
        self._row(f, "Follow-up confidence", self._spin("voice.followup_min_confidence", 0.0, 1.0, 0.05, 2),
                  "Minimum speech-recognition confidence for follow-ups (short commands score low).")
        self._row(f, "Chime", self._check("voice.wake_word_chime", "Play a short tone when SAINT hears its name"))
        self._row(f, "Debug", self._check("voice.wake_word_debug_scores", "Log every score above 0.1"))
        lay.addWidget(box)
        self._add_page(w, lay)

    def _browse_model(self, line):
        path, _ = QFileDialog.getOpenFileName(self, "Wake-word model", str(PROJECT_ROOT / "data" / "wake"),
                                              "ONNX models (*.onnx)")
        if path:
            line.setText(display_path(path).replace("\\", "/"))

    def _render_wake_status(self):
        pal = current_palette()
        st = module_manager.get("voice").wake_status()
        if not st.get("enabled"):
            self.wake_status.setText("Off")
            self.wake_status.setStyleSheet(f"color:{pal.muted};")
        elif st.get("ready"):
            self.wake_status.setText(f"Ready · {st.get('model_path')} · {st.get('avg_infer_ms', 0)} ms per frame")
            self.wake_status.setStyleSheet(f"color:{pal.success};")
        else:
            self.wake_status.setText(st.get("error") or "Not loaded")
            self.wake_status.setStyleSheet(f"color:{pal.danger};")
        self.wake_meter.set_threshold(config.get("voice.wake_word_threshold", 0.5))

    # ---- SPOTIFY ---------------------------------------------------------------
    def _build_spotify(self):
        w, lay = self._new_page("Spotify")
        box, f = self._section("Account", "SAINT uses Spotify's Web API with your own developer app "
                                          "(Client ID) and a secure PKCE login; tokens are stored in the "
                                          "Windows Credential Manager, never in files.")
        self._row(f, "Spotify", self._check("modules.spotify", "Enable Spotify control"))
        self._row(f, "Client ID", self._line("spotify.client_id", "from developer.spotify.com/dashboard"))
        self._row(f, "Redirect URI", self._line("spotify.redirect_uri", "http://127.0.0.1:8888/callback"),
                  "Add exactly this URI to your Spotify app's Redirect URIs. Using SAINT on your iPhone too? "
                  "Add saint://spotify-callback to the same app as well (and use the same Client ID there) — "
                  "otherwise Spotify says “redirect_uri: Not matching configuration”.")
        self.sp_status = QLabel("")
        self.sp_connect = QPushButton("Connect Spotify")
        self.sp_connect.setObjectName("Primary")
        self.sp_connect.clicked.connect(self._spotify_connect)
        self.sp_disconnect = QPushButton("Disconnect")
        self.sp_disconnect.clicked.connect(self._spotify_disconnect)
        r = QHBoxLayout()
        r.addWidget(self.sp_status, 1)
        r.addWidget(self.sp_disconnect)
        r.addWidget(self.sp_connect)
        rw = QWidget()
        rw.setObjectName("FormRow")
        rw.setLayout(r)
        f.addRow("", rw)
        lay.addWidget(box)

        box, f = self._section("Playback")
        self.sp_device = QComboBox()
        self.sp_device.setEditable(True)
        self._bind("spotify.preferred_device", lambda: self.sp_device.currentText().strip(),
                   lambda v: self.sp_device.setCurrentText(v or ""))
        dr = QHBoxLayout()
        dr.addWidget(self.sp_device, 1)
        ref = QPushButton("Find devices")
        ref.clicked.connect(self._spotify_devices)
        dr.addWidget(ref)
        dw = QWidget()
        dw.setLayout(dr)
        self._row(f, "Preferred device", dw, "Used when no device is active. Leave empty to prefer this PC.")
        self._row(f, "Wake a device", self._check("spotify.auto_device",
                                                   "If nothing is playing anywhere, activate a device (or open Spotify)"))
        self._row(f, "Volume step", self._spin("spotify.volume_step", 5, 50, 5, 0, " %"))
        self._row(f, "Hands-free", self._check("voice.music_hotwords",
                                               "While music plays, “skip”, “pause”, “louder”… need no wake word"),
                  "Only a short playback command on its own counts — lyrics and chatter are ignored.")
        self._row(f, "Mini player", self._check("widgets.spotify", "Show the floating always-on-top player",
                                                live="Mini player {state}."),
                  "Shows whatever is playing — Spotify, a YouTube video, or any app Windows knows about.")
        self._row(f, "Lyrics", self._check("widgets.lyrics", "Show the song's lyrics under the mini player",
                                           live="Lyrics {state}."),
                  "Synced lyrics from LRCLIB (only the song title and artist are sent). "
                  "Or say “turn on the lyrics”.")
        self._row(f, "Keep it going", self._check("spotify.autoqueue",
                                                  "After a song I ask for, queue songs like it — 5 at a time"),
                  "Also used for moods (“I'm feeling chill”) and “queue more songs like this”.")
        lay.addWidget(box)

        box, f = self._section("Music memory", "Used for “play something I'd like” and “what did I listen to today”.")
        self._row(f, "Listening history", self._check("spotify.track_history",
                                                      "Remember what I play, skip and request"))
        self._row(f, "Sync interval", self._spin("spotify.poll_interval_sec", 5, 120, 5, 0, " s"))
        clear = QPushButton("Clear music memory…")
        clear.setObjectName("Danger")
        clear.clicked.connect(self._clear_music_memory)
        f.addRow("", clear)
        lay.addWidget(box)
        self._add_page(w, lay)

    def _refresh_spotify_status(self):
        sp = module_manager.get("spotify")
        pal = current_palette()
        ok, reason = sp.availability()
        self.sp_status.setText("Connected" if ok else reason)
        self.sp_status.setStyleSheet(f"color:{pal.success if ok else pal.muted};")
        self.sp_disconnect.setEnabled(sp.is_connected())

    def _spotify_connect(self):
        sp = module_manager.get("spotify")
        if getattr(self, "_sp_waiting", False):
            # The button says "Cancel sign-in" while the browser is open: a wrong callback or a closed
            # tab no longer locks Connect for three minutes.
            if sp is not None:
                sp.auth.cancel_login()
            return
        config.set("spotify.client_id", self._value("spotify.client_id"), persist=True)
        config.set("spotify.redirect_uri", self._value("spotify.redirect_uri"), persist=True)
        module_manager.set_enabled("spotify", True)
        sp = module_manager.get("spotify")
        self._sp_waiting = True
        self.sp_connect.setText("Cancel sign-in")
        self.sp_status.setText("Waiting for you to log in to Spotify in the browser…")

        def finish():
            self._sp_waiting = False
            self.sp_connect.setText("Connect Spotify")
            self._refresh_spotify_status()

        def done(_):
            finish()

        def fail(e):
            finish()
            if "cancelled" not in str(e):
                QMessageBox.warning(self, "Spotify", str(e))
        run_async(sp.connect, done, fail)

    def _spotify_disconnect(self):
        module_manager.get("spotify").disconnect()
        self._refresh_spotify_status()

    def _spotify_devices(self):
        sp = module_manager.get("spotify")

        def done(d):
            cur = self.sp_device.currentText()
            self.sp_device.clear()
            self.sp_device.addItem("")
            for dev in (d or {}).get("devices", []):
                self.sp_device.addItem(dev.get("name", ""))
            self.sp_device.setCurrentText(cur)
        run_async(sp.client.devices, done, lambda e: self.sp_status.setText(f"Couldn't list devices: {e}"))

    def _clear_music_memory(self):
        if QMessageBox.question(self, "Clear music memory",
                                "Delete SAINT's Spotify listening history, skips, requests and feedback?") \
                == QMessageBox.Yes:
            module_manager.get("spotify").tools.memory.clear()
            self.status.setText("Music memory cleared.")

    # ---- MEMORY ----------------------------------------------------------------
    def _build_memory(self):
        w, lay = self._new_page("Memory")
        box, f = self._section("Long-term memory",
                               "SAINT remembers what you tell it (“my favorite language is Python”) and learns "
                               "from what you mention in passing (“I'm a nurse”, “I hate horror movies”), all in a "
                               "local database. Learned facts that never come up again fade out; anything you "
                               "confirm on the Memory page stays. Your profile is on the Memory page.")
        self._row(f, "Memory", self._check("memory.enabled", "Enabled"))
        self._row(f, "Learn from statements", self._check("memory.auto_extract",
                                                          "Store clear personal statements automatically"))
        self._row(f, "Learn in passing", self._check("memory.learn_passive",
                                                     "Pick up facts you mention while chatting"))
        self._row(f, "Learn with the AI", self._check("memory.learn_with_ai",
                                                      "Let the local model find lasting facts in what you say"),
                  "Runs after SAINT has answered, on your PC — nothing is uploaded.")
        self._row(f, "Forget unconfirmed after", self._spin("memory.learned_ttl_days", 7, 365, 1, 0, " days"),
                  "Only for learned facts that never came up again. Mentioning one again keeps it longer.")
        self._row(f, "Use in answers", self._check("memory.inject_context",
                                                   "Give the language model relevant memories"))
        self._row(f, "Memories per answer", self._spin("memory.max_context_items", 1, 20))
        wipe = QPushButton("Delete all long-term memories…")
        wipe.setObjectName("Danger")
        wipe.clicked.connect(self._wipe_memory)
        f.addRow("", wipe)
        lay.addWidget(box)
        box, f = self._section("History", "A private log of what you asked and what SAINT did, shown on the History "
                                          "page. It is stored only in data/history.jsonl on this PC and never uploaded.")
        self._row(f, "History", self._check("history.enabled", "Keep a local history of requests"))
        self._row(f, "Keep up to", self._spin("history.max_entries", 100, 100000, 500, 0, " entries"))
        lay.addWidget(box)
        self._add_page(w, lay)

    def _wipe_memory(self):
        if QMessageBox.question(self, "Delete memories", "Permanently delete everything SAINT remembers about you?") \
                == QMessageBox.Yes:
            from modules.memory.service import memory_service
            n = memory_service.forget_all()
            self.status.setText(f"Deleted {n} memories.")

    # ---- AUTOMATION -------------------------------------------------------------
    def _build_automation(self):
        w, lay = self._new_page("Automation")
        box, f = self._section("Reminders & automations")
        self._row(f, "Automations", self._check("automation.enabled", "Run scheduled reminders and commands"))
        self._row(f, "Speak reminders", self._check("automation.speak_reminders", "Say reminders out loud"))
        self._row(f, "Missed reminders", self._spin("automation.missed_grace_hours", 0, 72, 1, 0, " h"),
                  "One-time reminders missed while SAINT was closed are delivered on startup if they're "
                  "no older than this.")
        self._row(f, "“Every morning” means", self._line("automation.default_morning_time", "08:00"))
        lay.addWidget(box)
        self._add_page(w, lay)

    # ---- DESKTOP CONTROL -----------------------------------------------------------
    def _build_desktop(self):
        w, lay = self._new_page("Desktop Control")
        box, f = self._section("Permissions",
                               "SAINT controls the desktop only through explicit, validated tools — never "
                               "arbitrary commands. Emergency stop: slam the mouse into a screen corner.")
        self._row(f, "Desktop control", self._check("desktop.enabled", "Enabled"))
        self._row(f, "Open apps", self._check("desktop.allow_app_launch", "Allowed"))
        self._row(f, "Switch / move / close windows", self._check("desktop.allow_window_control", "Allowed"))
        self._row(f, "Keyboard", self._check("desktop.allow_keyboard", "Allowed"))
        self._row(f, "Mouse & clicking", self._check("desktop.allow_mouse", "Allowed"))
        self._row(f, "Closing apps", self._check("desktop.confirm_close_apps", "Ask before closing an app"))
        self._row(f, "Several matching windows", self._combo(
            "desktop.multi_window_policy", ["Ask which one", "Use the most recent"], data=["ask", "recent"]),
                  "e.g. three browser windows are open and none is clearly meant.")
        self._row(f, "Paste text longer than", self._spin("desktop.paste_over", 0, 5000, 20, 0, " chars"))
        lay.addWidget(box)

        box = QGroupBox("App shortcuts")
        v = QVBoxLayout(box)
        d = QLabel("Extra names SAINT can open, e.g. “notes” → C:/Tools/Obsidian.exe or a URI like steam://.")
        d.setObjectName("Muted")
        d.setWordWrap(True)
        v.addWidget(d)
        self.apps_table = QTableWidget(0, 2)
        self.apps_table.setHorizontalHeaderLabels(["Name", "Path or URI"])
        self.apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.apps_table.verticalHeader().setVisible(False)
        self.apps_table.setMaximumHeight(150)
        v.addWidget(self.apps_table)
        br = QHBoxLayout()
        add = QPushButton("Add")
        add.clicked.connect(lambda: self.apps_table.insertRow(self.apps_table.rowCount()))
        rem = QPushButton("Remove")
        rem.clicked.connect(lambda: self.apps_table.removeRow(self.apps_table.currentRow()))
        br.addWidget(add)
        br.addWidget(rem)
        br.addStretch()
        v.addLayout(br)
        self._bind("desktop.apps", self._apps_value, self._apps_load)
        lay.addWidget(box)

        box = QGroupBox("Per-tool access")
        v = QVBoxLayout(box)
        d = QLabel("Override the permission mode for individual tools.")
        d.setObjectName("Muted")
        v.addWidget(d)
        self.perm_table = QTableWidget(0, 3)
        self.perm_table.setHorizontalHeaderLabels(["Tool", "Risk", "Access"])
        self.perm_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.perm_table.verticalHeader().setVisible(False)
        self.perm_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.perm_table.setMinimumHeight(260)
        v.addWidget(self.perm_table)
        self._bind("permissions.overrides", self._perm_value, self._perm_load)
        lay.addWidget(box)
        self._add_page(w, lay)

    def _apps_value(self):
        out = {}
        for r in range(self.apps_table.rowCount()):
            k = self.apps_table.item(r, 0)
            v = self.apps_table.item(r, 1)
            if k and v and k.text().strip() and v.text().strip():
                out[k.text().strip()] = v.text().strip()
        return out

    def _apps_load(self, apps):
        self.apps_table.setRowCount(0)
        for k, v in (apps or {}).items():
            r = self.apps_table.rowCount()
            self.apps_table.insertRow(r)
            self.apps_table.setItem(r, 0, QTableWidgetItem(k))
            self.apps_table.setItem(r, 1, QTableWidgetItem(v))

    def _perm_load(self, overrides):
        from modules.automation.tools import get_tool_registry
        overrides = overrides or {}
        tools = sorted(get_tool_registry().list_tools(), key=lambda t: t.name)
        self.perm_table.setRowCount(0)
        for t in tools:
            r = self.perm_table.rowCount()
            self.perm_table.insertRow(r)
            self.perm_table.setItem(r, 0, QTableWidgetItem(t.name))
            self.perm_table.setItem(r, 1, QTableWidgetItem(t.permission.value))
            combo = QComboBox()
            combo.addItems(["default", "allow", "confirm", "deny"])
            combo.setCurrentText(overrides.get(t.name, "default"))
            self.perm_table.setCellWidget(r, 2, combo)

    def _perm_value(self):
        out = {k: v for k, v in (config.get("permissions.overrides", {}) or {}).items() if "." not in k}
        for r in range(self.perm_table.rowCount()):
            combo = self.perm_table.cellWidget(r, 2)
            if combo and combo.currentText() != "default":
                out[self.perm_table.item(r, 0).text()] = combo.currentText()
        return out

    # ---- APPEARANCE ------------------------------------------------------------------
    def _build_appearance(self):
        w, lay = self._new_page("Appearance")
        box, f = self._section("Theme")
        self._row(f, "Mode", self._combo("appearance.theme", ["Dark", "Light", "System"]))
        self.accent = "#feaa34"
        sw = QHBoxLayout()
        self._swatches = []
        for c in ACCENTS:
            b = QPushButton("")
            b.setObjectName("Swatch")
            b.setStyleSheet(f"background:{c}; border:2px solid transparent;")
            b.clicked.connect(lambda _=False, col=c: self._set_accent(col))
            sw.addWidget(b)
            self._swatches.append((c, b))
        custom = QPushButton("Custom…")
        custom.clicked.connect(self._pick_accent)
        sw.addWidget(custom)
        sw.addStretch()
        swd = QWidget()
        swd.setLayout(sw)
        self._bind("appearance.accent", lambda: self.accent, self._set_accent)
        self._row(f, "Accent colour", swd)
        self.font_combo = QFontComboBox()
        self._bind("appearance.font_family", lambda: self.font_combo.currentFont().family(),
                   lambda v: self.font_combo.setCurrentFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont(v or "Segoe UI")))
        self._row(f, "Font", self.font_combo)
        self._row(f, "Font size", self._spin("appearance.font_size", 10, 20, 1, 0, " px"))
        self._row(f, "Density", self._check("appearance.compact", "Compact"))
        self._row(f, "Animations", self._check("appearance.animations", "Animate the orb, Halo and transitions"))
        if sys.platform.startswith("linux"):
            self._row(f, "Sounds", self._check("appearance.sounds", "Star chimes when the overlay opens and closes"),
                      "HalOS's system sounds and window animations are under HalOS › Plasma settings.")
        lay.addWidget(box)

        box, f = self._section("Window")
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(60, 100)
        self._bind("appearance.opacity", lambda: self.opacity.value() / 100,
                   lambda v: self.opacity.setValue(int(round(float(v or 1.0) * 100))))
        self._row(f, "Opacity", self.opacity)
        self._row(f, "Always on top", self._check("appearance.always_on_top", "Keep SAINT above other windows"))
        self._row(f, "Sidebar", self._check("appearance.sidebar_labels", "Show labels"))
        lay.addWidget(box)

        # ---- layout: what shows where (applies immediately) ------------------------------------
        from ui.components.layout_editor import OrderedChecklist
        from ui.components.sidebar import FIXED, PAGES
        from ui.pages.overview import PANELS
        box, f = self._section("Layout", "Tick what you want to see and drag to reorder. Changes apply right away.")
        self.sidebar_editor = OrderedChecklist([(k, label) for k, label, _i, _s in PAGES if k != "Settings"],
                                               "layout.sidebar_hidden", "layout.sidebar_order", fixed=("Overview",))
        self.sidebar_editor.changed.connect(lambda: ui_bus.setting_changed.emit("layout.sidebar"))
        self._row(f, "Sidebar pages", self.sidebar_editor)
        self.panel_editor = OrderedChecklist([(k, t) for k, t, _c in PANELS], "layout.overview_hidden",
                                             "layout.overview_order", fixed=("task",))
        self.panel_editor.changed.connect(lambda: ui_bus.setting_changed.emit("layout.overview"))
        self._row(f, "Overview panels", self.panel_editor,
                  "On a wide window the task, conversation and activity panels sit on the left, the rest on "
                  "the right; on a narrow one everything is one column in this order.")
        self._row(f, "Status bar", self._check("layout.status_bar", "Show what SAINT is doing at the bottom",
                                               live="Status bar {state}."))
        from PySide6.QtGui import QGuiApplication
        mons = ["Where it was last"] + [f"Monitor {i + 1}" for i in range(len(QGuiApplication.screens()))]
        self._row(f, "Open on", self._combo("layout.start_monitor", mons, data=list(range(len(mons)))),
                  "Takes effect the next time SAINT starts.")
        lay.addWidget(box)

        box, f = self._section("Halo & overlay",
                               "The Halo is a soft light that travels around your screen edge while SAINT works in "
                               "the background. Rest the cursor at the top-centre edge, or press the hotkey, to open "
                               "the overlay.")
        halo_row = QHBoxLayout()
        halo_row.setContentsMargins(0, 0, 0, 0)
        halo_row.setSpacing(14)
        self.halo_switch = Switch("Glow around the screen edge")
        self.halo_when = QComboBox()
        self.halo_when.addItem("while SAINT is minimized", "minimized")
        self.halo_when.addItem("always, even with SAINT open", "always")
        halo_row.addWidget(self.halo_switch)
        halo_row.addWidget(self.halo_when)
        halo_row.addStretch()
        hw = QWidget()
        hw.setLayout(halo_row)

        def halo_value():
            return self.halo_when.currentData() if self.halo_switch.isChecked() else "off"

        def halo_load(v):
            self.halo_switch.setChecked((v or "always") != "off")
            self.halo_when.setCurrentIndex(max(0, self.halo_when.findData(v if v in ("minimized", "always")
                                                                          else "always")))
            self.halo_when.setEnabled(self.halo_switch.isChecked())

        def halo_changed(*_):
            self.halo_when.setEnabled(self.halo_switch.isChecked())
            self._apply_live("overlay.halo", halo_value(),
                             "Halo {state} — it's glowing around your screen for a moment so you can see it."
                             if self.halo_switch.isChecked() else "Halo off.")
        self._bind("overlay.halo", halo_value, halo_load)
        self.halo_switch.toggled.connect(halo_changed)
        self.halo_when.currentIndexChanged.connect(halo_changed)
        self._row(f, "Halo", hw, "Changes apply right away — the Halo shows for a few seconds as a preview.")
        self._row(f, "Screens", self._check("overlay.halo_all_screens", "Show on every monitor",
                                            live="Halo on every monitor: {state}."))
        self._row(f, "Action notifications",
                  self._check("notifications.actions", "Show a small notice at the bottom of the screen when SAINT "
                                                       "does something",
                              live="Action notifications {state}."))
        if not sys.platform.startswith("linux"):     # on Linux: Control Center's Desktop page (ui/halo.py)
            self._row(f, "Edge tab", self._check("overlay.edge_tab", "Reveal a SAINT tab at the top edge"))
        self._row(f, "Over games",
                  self._check("game_mode.protect_overlays", "Hide the Halo and pop-ups while a game runs",
                              live="Overlays over games: {state}."),
                  "Anti-cheat treats see-through windows on top of a game as a cheat overlay, and they stop true "
                  "fullscreen. This applies whether or not Gaming Mode is on (Settings > Gaming Mode).")
        self._row(f, "Overlay hotkey", self._line("overlay.hotkey", "alt+`"),
                  "Works from anywhere. Combine ctrl / alt / shift / win with a key, e.g. alt+` or ctrl+alt+s.")
        lay.addWidget(box)
        self._add_page(w, lay)

    # ---- GAMING MODE ---------------------------------------------------
    def _build_gaming(self):
        from core.game_mode import FEATURE_DEFAULTS, FEATURE_LABELS, game_mode
        w, lay = self._new_page("Gaming Mode")
        box, f = self._section("Gaming Mode",
                               "Gaming Mode is yours to switch: a game running doesn't turn it on unless Auto "
                               "Gaming Mode is on. Say “gaming mode on / off”, use the tray menu, or the switch here.")
        self.gaming_switch = Switch("Gaming Mode")
        self.gaming_switch.setChecked(game_mode.active)
        self.gaming_switch.toggled.connect(lambda on: None if self._loading else game_mode.set_manual(on))
        self._row(f, "Now", self.gaming_switch, "Takes effect immediately.")
        self._row(f, "Auto Gaming Mode",
                  self._check("game_mode.enabled", "Turn Gaming Mode on when a game starts",
                              live="Auto Gaming Mode {state}."))
        self._row(f, "Game detection",
                  self._check("game_mode.detect", "Notice running games (Steam libraries, your games folder, "
                                                  "known games)"),
                  "Needed for Auto Gaming Mode, for keeping overlays off games, and for “what am I playing?”.")
        mons = ["auto"] + [str(i) for i in range(1, 5)]
        self._row(f, "SAINT's monitor",
                  self._combo("game_mode.saint_monitor",
                              ["Automatic (any monitor without the game)"] + [f"Monitor {i}" for i in range(1, 5)],
                              data=mons),
                  "Where SAINT's window, overlay and mini player go while Gaming Mode is on.")
        self._row(f, "Gaming workspace",
                  self._check("game_mode.workspace_spotify", "“Set up my gaming workspace” also opens Spotify"))
        lay.addWidget(box)

        box, f = self._section("While Gaming Mode is on",
                               "Each part of SAINT can stay on or switch off while you play.")
        for key, default in FEATURE_DEFAULTS.items():
            ck = f"game_mode.features.{key}"
            if key == "notifications":
                combo = QComboBox()
                for label, value in (("All", "all"), ("Minimal — errors and reminders", "minimal"), ("Off", "off")):
                    combo.addItem(label, value)
                self._bind(ck, combo.currentData,
                           lambda v, c=combo, d=default: c.setCurrentIndex(max(0, c.findData(v or d))))
                self._row(f, FEATURE_LABELS[key], combo)
                continue
            sw = Switch(FEATURE_LABELS[key])
            self._bind(ck, sw.isChecked, lambda v, s=sw, d=default: s.setChecked(d if v is None else bool(v)))
            self._row(f, "", sw)
        lay.addWidget(box)
        self._add_page(w, lay)

        def sync(ev):
            if ev.type == EventType.GAME_MODE and self.gaming_switch.isChecked() != bool(ev.payload.get("active")):
                self.gaming_switch.blockSignals(True)
                self.gaming_switch.setChecked(bool(ev.payload.get("active")))
                self.gaming_switch.blockSignals(False)
        ui_bus.event.connect(sync)

    def _set_accent(self, color):
        c = QColor(color or "#feaa34")
        self.accent = c.name() if c.isValid() else "#feaa34"
        for col, b in self._swatches:
            border = "#ffffff" if col.lower() == self.accent.lower() else "transparent"
            b.setStyleSheet(f"background:{col}; border:2px solid {border};")

    def _pick_accent(self):
        c = QColorDialog.getColor(QColor(self.accent), self, "Accent colour")
        if c.isValid():
            self._set_accent(c.name())

    # ---- ADVANCED ------------------------------------------------------------------
    # ---- MCP -----------------------------------------------------------------
    def _build_mcp(self):
        w, lay = self._new_page("MCP")
        box, f = self._section("MCP servers", "Give SAINT the tools of any Model Context Protocol server — your "
                               "notes, GitHub, a database, a smart-home hub. Paste the server's JSON the way its "
                               "README shows it for Claude Desktop ({\"mcpServers\": {...}}). Its tools then work by "
                               "voice like SAINT's own; anything that could change something asks you first unless "
                               "you add \"trust\": \"allow\" to that server. Saved in data/mcp.json.")
        self._row(f, "MCP", self._check("mcp.enabled", "Connect the MCP servers below when SAINT starts"))
        self.mcp_json = QPlainTextEdit()
        self.mcp_json.setMinimumHeight(220)
        self.mcp_json.setPlaceholderText('{\n  "mcpServers": {\n    "filesystem": {\n      "command": "npx",\n'
                                         '      "args": ["-y", "@modelcontextprotocol/server-filesystem", '
                                         '"C:/Users/you/Documents"]\n    }\n  }\n}')
        f.addRow(self.mcp_json)
        row = QHBoxLayout()
        save = QPushButton("Save && connect")
        save.setObjectName("Primary")
        save.clicked.connect(self._mcp_save)
        row.addWidget(save)
        self.mcp_status = QLabel("")
        self.mcp_status.setObjectName("Muted")
        self.mcp_status.setWordWrap(True)
        row.addWidget(self.mcp_status, 1)
        holder = QWidget()
        holder.setLayout(row)
        f.addRow(holder)
        lay.addWidget(box)
        self._add_page(w, lay)
        self._mcp_load()

    def _mcp_load(self):
        from modules.mcp.manager import mcp_manager
        try:
            with open(mcp_manager.path, encoding="utf-8") as fh:
                self.mcp_json.setPlainText(fh.read())
        except OSError:
            self.mcp_json.setPlainText("")
        self.mcp_status.setText(mcp_manager.describe())

    def _mcp_save(self):
        import json as _json
        from modules.mcp.manager import mcp_manager
        text = self.mcp_json.toPlainText().strip() or '{"mcpServers": {}}'
        try:
            data = _json.loads(text)
            servers = data.get("mcpServers", data) if isinstance(data, dict) else None
            if not isinstance(servers, dict) or not all(isinstance(v, dict) for v in servers.values()):
                raise ValueError("expected {\"mcpServers\": {\"name\": {...}}}")
        except ValueError as e:
            self.mcp_status.setText(f"That isn't valid MCP JSON: {e}")
            return
        os.makedirs(os.path.dirname(mcp_manager.path), exist_ok=True)
        with open(mcp_manager.path, "w", encoding="utf-8") as fh:
            _json.dump({"mcpServers": servers}, fh, indent=2)
        self.mcp_status.setText("Connecting…")
        run_async(lambda: (mcp_manager.reload(wait=True), mcp_manager.describe())[1],
                  lambda d: self.mcp_status.setText(d), lambda e: self.mcp_status.setText(str(e)))

    def _build_advanced(self):
        w, lay = self._new_page("Advanced")
        box, f = self._section("Logging & diagnostics")
        self._row(f, "Log level", self._combo("logging.level", ["Verbose", "Normal", "Errors Only"]))
        self._row(f, "Debug mode", self._check("logging.debug", "Log detailed subsystem debug output"))
        self._row(f, "Analytics", self._check("analytics.enabled", "Record local latency statistics"))
        logs = QPushButton("Open log folder")
        logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir() / "logs"))))
        r = QHBoxLayout()
        r.addWidget(logs)
        r.addStretch()
        rw = QWidget()
        rw.setObjectName("FormRow")
        rw.setLayout(r)
        f.addRow("", rw)
        lay.addWidget(box)

        box, f = self._section("Files")
        lbl = QLabel(f"Config: {display_path(config.path)}\nData: {display_path(data_dir())}")
        lbl.setObjectName("Muted")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f.addRow(lbl)
        self._row(f, "Startup check", self._check("system.startup_check", "Run the environment check on launch"))
        if os.name == "nt":                          # on Linux it's Service › Start at login
            auto = self._check("system.start_with_windows", "Start SAINT when I sign in to Windows")
            auto.toggled.connect(self._set_autostart)
            self._row(f, "Start with Windows", auto,
                      "Starts hidden in the tray. Shows up as “SAINT” in Task Manager → Startup apps.")
        lay.addWidget(box)
        self._add_page(w, lay)

    def _set_autostart(self, on: bool):
        if self._loading:
            return
        from core import autostart
        ok, message = autostart.set_enabled(on)
        pal = current_palette()
        self.status.setText(message)
        self.status.setStyleSheet(f"color:{(pal.success if on else pal.muted) if ok else pal.danger};")

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #
    def _value(self, key):
        for k, getter, _ in self._bindings:
            if k == key:
                return getter()
        return config.get(key)

    def load(self):
        self._loading = True
        try:
            for key, _getter, setter in self._bindings:
                try:
                    setter(config.get(key))
                except Exception:
                    pass
        finally:
            self._loading = False
        self._render_wake_status()
        self._refresh_spotify_status()
        self._provider_changed()
        self.status.setText("")

    def save(self):
        before_modules = {k: config.get(f"modules.{k}", False) for k in
                          ("voice", "memory", "automation", "desktop", "vision", "spotify")}
        errors = []
        for key, getter, _ in self._bindings:
            try:
                config.set(key, getter(), persist=False)
            except Exception as e:
                errors.append(f"{key}: {e}")
        config.set("theme", config.get("appearance.theme", "Dark"), persist=False)
        try:
            config.save()
        except OSError as e:
            self.status.setText(f"Couldn't write settings: {e}")
            return
        for k, was in before_modules.items():
            now = config.get(f"modules.{k}", False)
            if now != was:
                module_manager.set_enabled(k, now)
        event_bus.emit_event(EventType.SETTINGS_CHANGED, {})
        if self.on_appearance_changed:
            self.on_appearance_changed()
        pal = current_palette()
        if errors:
            self.status.setText("Saved with problems: " + "; ".join(errors))
            self.status.setStyleSheet(f"color:{pal.warning};")
        else:
            self.status.setText("Settings saved and applied.")
            self.status.setStyleSheet(f"color:{pal.success};")
        QTimer.singleShot(1500, self._render_wake_status)

    # ------------------------------------------------------------------ #
    def _on_event(self, ev):
        if ev.type in (EventType.WAKE_STATUS, EventType.WAKE_ERROR):
            self._render_wake_status()
        elif ev.type == EventType.VOICE_WAKE_SCORE and self.isVisible():
            self.wake_meter.set_value(ev.payload.get("score", 0.0))
        elif ev.type in (EventType.SPOTIFY_CONNECTED, EventType.SPOTIFY_DISCONNECTED):
            self._refresh_spotify_status()

    def showEvent(self, e):
        super().showEvent(e)
        self._render_wake_status()
        self._refresh_spotify_status()
        self._refresh_voice_status()
        self._refresh_ai_progress()
        self._pull_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._pull_timer.stop()
