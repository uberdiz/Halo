"""Settings page "Wallpaper": the HalOS living wallpaper (org.halos.living). A colour or gradient, the SAINT logo
anywhere on the screen at any size, its glow, what makes it move (SAINT's voice, the music playing, the microphone,
a slow breath, or nothing) and how smoothly. A live preview shows the result before it's applied; each monitor
can have its own."""

import re
import subprocess

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QWidget)

from core.paths import PROJECT_ROOT
from ui.widgets import Page, set_button_state

TITLE = "Wallpaper"
ICON = "sparkles"
ORDER = 2
PLUGIN = "org.halos.living"
SOURCES = [("saint", "SAINT's voice"), ("desktop", "Music and sound playing"), ("mic", "Microphone"),
           ("breathing", "A slow breath"), ("still", "Nothing (still)")]
PRESETS = {"Center": (0.5, 0.5), "Top left": (0.18, 0.22), "Top right": (0.82, 0.22), "Bottom left": (0.18, 0.78),
           "Bottom right": (0.82, 0.78), "Left": (0.25, 0.5), "Right": (0.75, 0.5)}
DEFAULTS = {"Background": "gradient", "Color": "#0a0b0d", "Color2": "#2a1a08", "Angle": 135, "LogoScale": 0.28,
            "LogoX": 0.5, "LogoY": 0.5, "ShowLogo": True, "Glow": 0.5, "Accent": "#feaa34", "Source": "saint",
            "Sensitivity": 1.0, "Bars": True, "BarStyle": "bars", "Fps": 30}
BAR_STYLES = [("bars", "Bars under the logo"), ("ring", "A ring around the logo")]
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
_SHELL = ["org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript"]


def clean(values: dict) -> dict:
    """Every value checked and clamped before it goes anywhere near the Plasma script."""
    v = dict(DEFAULTS)
    for k in ("Color", "Color2", "Accent"):
        if _COLOR.fullmatch(str(values.get(k, ""))):
            v[k] = str(values[k]).lower()
    v["Background"] = values.get("Background") if values.get("Background") in ("solid", "gradient") else v["Background"]
    v["Source"] = values.get("Source") if values.get("Source") in dict(SOURCES) else v["Source"]
    v["BarStyle"] = values.get("BarStyle") if values.get("BarStyle") in dict(BAR_STYLES) else v["BarStyle"]
    for k, lo, hi in (("Angle", 0, 360), ("Fps", 5, 60)):
        try:
            v[k] = int(max(lo, min(hi, int(values.get(k, v[k])))))
        except (TypeError, ValueError):
            pass
    for k, lo, hi in (("LogoScale", 0.05, 0.8), ("LogoX", 0, 1), ("LogoY", 0, 1), ("Glow", 0, 1), ("Sensitivity", 0.2, 3)):
        try:
            v[k] = round(max(lo, min(hi, float(values.get(k, v[k])))), 3)
        except (TypeError, ValueError):
            pass
    for k in ("ShowLogo", "Bars"):
        v[k] = bool(values.get(k, v[k]))
    return v


def plasma_script(values: dict, screen: int = -1) -> str:
    """The plasmashell script that switches a monitor's desktop (or all, -1) to the living wallpaper with these
    settings. Only clean() values are put in it."""
    return desktop_script(PLUGIN, clean(values), screen)


def desktop_script(plugin: str, values: dict, screen: int = -1) -> str:
    """Switch the desktops (one monitor, or all with -1) to ``plugin`` and write ``values`` into its General group,
    then reload so Plasma shows it now. Strings must already be checked: they're quoted, not escaped, except that
    a quote or backslash is refused."""
    if not re.fullmatch(r"[A-Za-z0-9_.]{1,80}", plugin):
        raise ValueError(f"bad wallpaper plugin {plugin!r}")
    lines = ["desktops().forEach(function (d) {", f"  if ({int(screen)} >= 0 && d.screen !== {int(screen)}) return;",
             f"  d.wallpaperPlugin = '{plugin}';", f"  d.currentConfigGroup = ['Wallpaper', '{plugin}', 'General'];"]
    for k, val in values.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", k) or isinstance(val, str) and re.search(r"['\\\n\r]", val):
            raise ValueError(f"unsafe wallpaper setting {k!r}")
        js = "true" if val is True else "false" if val is False else (f"'{val}'" if isinstance(val, str) else repr(val))
        lines.append(f"  d.writeConfig('{k}', {js});")
    return "\n".join(lines + ["  d.reloadConfig();", "});"])


def run_script(script: str, run=subprocess.run) -> str:
    """Run a plasmashell script through qdbus6 (or qdbus): "" when Plasma took it, else why not, with qdbus' own
    error so the user (and the log) sees the real reason."""
    why = "Plasma's qdbus isn't installed."
    for q in ("qdbus6", "qdbus"):
        try:
            r = run([q, *_SHELL, script], capture_output=True, text=True, timeout=15)
        except FileNotFoundError:
            continue
        except (OSError, subprocess.SubprocessError) as e:
            why = f"{q} didn't answer: {e}"
            continue
        if r.returncode == 0:
            return ""
        err = " ".join(f"{getattr(r, 'stderr', '') or ''} {getattr(r, 'stdout', '') or ''}".split())
        return f"Plasma didn't accept the wallpaper: {err[:300] or f'{q} exit code {r.returncode}'}"
    return why


def slideshow_script(folder, minutes: float = 10, screen: int = -1) -> str:
    """Plasma's own slideshow (org.kde.slideshow) over a folder of pictures, cross-fading every ``minutes``."""
    from pathlib import Path
    p = Path(folder)
    if not p.is_absolute() or not p.is_dir():
        raise ValueError(f"{folder} isn't a folder")
    secs = int(max(10, min(24 * 3600, float(minutes) * 60)))
    # SlideshowMode 0 = random order; FillMode 2 = scaled and cropped (fills the screen without stretching)
    return desktop_script("org.kde.slideshow", {"SlidePaths": p.as_posix(), "SlideInterval": secs,
                                                "SlideshowMode": 0, "FillMode": 2}, screen)


def apply_why(values: dict, screen: int = -1, run=subprocess.run) -> str:
    """Switch to the living wallpaper: "" on success, else the reason."""
    return run_script(plasma_script(values, screen), run)


def apply(values: dict, screen: int = -1, run=subprocess.run) -> bool:
    return not apply_why(values, screen, run)


class Preview(QWidget):
    """The wallpaper drawn small, with the same rules as the QML (no audio: a gentle pulse shows the movement)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(480, 270)
        self.values = dict(DEFAULTS)
        self.t = 0.0
        self.logo = QPixmap(str(PROJECT_ROOT / "SAINT.png"))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def set_values(self, values):
        self.values = clean(values)
        moving = self.values["Source"] != "still"
        self.timer.setInterval(int(1000 / self.values["Fps"]))
        self.timer.start() if moving else self.timer.stop()
        self.update()

    def _tick(self):
        self.t += self.timer.interval() / 1000
        self.update()

    def paintEvent(self, _):
        v = self.values
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        if v["Background"] == "gradient":
            import math
            a = math.radians(v["Angle"])
            c = r.center()
            d = QPointF(math.sin(a), -math.cos(a)) * (max(r.width(), r.height()) / 2)
            grad = QLinearGradient(c - d, c + d)
            grad.setColorAt(0, QColor(v["Color"]))
            grad.setColorAt(1, QColor(v["Color2"]))
            g.fillRect(r, grad)
        else:
            g.fillRect(r, QColor(v["Color"]))
        if not v["ShowLogo"]:
            return
        import math
        level = 0.0 if v["Source"] == "still" else 0.35 + 0.35 * math.sin(self.t * 2 * math.pi / 5)
        size = min(r.width(), r.height()) * v["LogoScale"] * (1 + level * 0.12 * v["Sensitivity"])
        center = QPointF(r.width() * v["LogoX"], r.height() * v["LogoY"])
        accent = QColor(v["Accent"])
        if v["Glow"] > 0:
            for i in range(6, 0, -1):
                glow = QColor(accent)
                glow.setAlphaF(min(1.0, v["Glow"] * 0.08 * (1 + level)))
                g.setBrush(glow)
                g.setPen(Qt.NoPen)
                rad = size / 2 * (1 + 0.06 * i * (1 + v["Glow"]))
                g.drawEllipse(center, rad, rad)
        if v["Bars"] and v["BarStyle"] == "bars":     # same layout as main.qml's row (48 bars, mirrored)
            g.setPen(Qt.NoPen)
            n, span, max_h = 48, size * 1.7, size * 0.34
            pitch = span / n
            base = center.y() + size / 2 + size * 0.06 + max_h
            for i in range(n):
                j = abs(i - (n - 1) / 2) / ((n - 1) / 2)
                val = level * (0.55 + 0.45 * math.sin(self.t * 2.2 + j * 9) * math.sin(self.t * 0.9 + j * 4)) * (1 - 0.5 * j)
                h = max(pitch * 0.5, max_h * (0.04 + 0.96 * max(0.0, min(1.0, val * v["Sensitivity"]))))
                x = center.x() - span / 2 + i * pitch + pitch * 0.2
                for top, hh, alpha in ((base - h, h, 0.45 + 0.55 * val), (base + pitch * 0.25, h * 0.7, 0.12 + 0.22 * val)):
                    c = QColor(accent)
                    c.setAlphaF(max(0.0, min(1.0, alpha)))
                    g.setBrush(c)
                    g.drawRoundedRect(QRectF(x, top, pitch * 0.6, hh), pitch * 0.3, pitch * 0.3)
        elif v["Bars"]:
            g.setPen(Qt.NoPen)
            g.setBrush(accent)
            for i in range(32):
                h = size * (0.03 + 0.32 * level * (0.6 + 0.4 * math.sin(self.t * 3 + i * 0.7)))
                g.save()
                g.translate(center)
                g.rotate(i * 360 / 32)
                g.drawRoundedRect(QRectF(-size * 0.0125, -size * 0.56 - h, size * 0.025, h), 2, 2)
                g.restore()
        if not self.logo.isNull():
            g.drawPixmap(QRectF(center.x() - size / 2, center.y() - size / 2, size, size), self.logo,
                         QRectF(self.logo.rect()))


class WallpaperPage(Page):
    def __init__(self, applier=apply_why, accent_applier=None):
        super().__init__(TITLE, "Your desktop: a colour or gradient, and the SAINT logo where you want it, moving "
                                "with SAINT's voice, your music or a slow breath.", scroll=True)
        self.applier = applier
        if accent_applier is None:
            def accent_applier(color):
                from core import accent
                return accent.apply(color)
        self.accent_applier = accent_applier
        self.values = dict(DEFAULTS)
        self.preview = Preview()
        self.root.addWidget(self.preview)
        form = QFormLayout()
        self.color_btns = {}
        bg = QHBoxLayout()
        self.background = QComboBox()
        self.background.addItem("Gradient", "gradient")
        self.background.addItem("Solid colour", "solid")
        self.background.currentIndexChanged.connect(lambda: self._set("Background", self.background.currentData()))
        bg.addWidget(self.background)
        for key, label in (("Color", "Colour"), ("Color2", "Second colour"), ("Accent", "Logo glow colour")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.color_btns[key] = b
            bg.addWidget(b)
        form.addRow("Background", bg)
        self.angle = self._slider(0, 360, "Angle", 1)
        form.addRow("Gradient angle", self.angle)
        self.show_logo = QCheckBox("Show the SAINT logo")
        self.show_logo.setChecked(True)
        self.show_logo.toggled.connect(lambda on: self._set("ShowLogo", on))
        form.addRow("", self.show_logo)
        self.size = self._slider(5, 80, "LogoScale", 100)
        form.addRow("Logo size", self.size)
        pos = QHBoxLayout()
        self.preset = QComboBox()
        for name in PRESETS:
            self.preset.addItem(name)
        self.preset.currentTextChanged.connect(self._preset)
        self.x = self._slider(0, 100, "LogoX", 100)
        self.y = self._slider(0, 100, "LogoY", 100)
        pos.addWidget(self.preset)
        pos.addWidget(QLabel("left/right"))
        pos.addWidget(self.x)
        pos.addWidget(QLabel("up/down"))
        pos.addWidget(self.y)
        form.addRow("Logo position", pos)
        self.glow = self._slider(0, 100, "Glow", 100)
        form.addRow("Glow", self.glow)
        self.source = QComboBox()
        for key, label in SOURCES:
            self.source.addItem(label, key)
        self.source.currentIndexChanged.connect(lambda: self._set("Source", self.source.currentData()))
        form.addRow("Moves with", self.source)
        vis = QHBoxLayout()
        self.bars = QCheckBox("Show the visualizer")
        self.bars.setChecked(True)
        self.bars.toggled.connect(lambda on: self._set("Bars", on))
        self.bar_style = QComboBox()
        for key, label in BAR_STYLES:
            self.bar_style.addItem(label, key)
        self.bar_style.currentIndexChanged.connect(lambda: self._set("BarStyle", self.bar_style.currentData()))
        vis.addWidget(self.bars)
        vis.addWidget(self.bar_style, 1)
        form.addRow("Visualizer", vis)
        self.sens = self._slider(20, 300, "Sensitivity", 100)
        form.addRow("Sensitivity", self.sens)
        self.fps = self._slider(5, 60, "Fps", 1)
        form.addRow("Smoothness (frames a second)", self.fps)
        self.root.addLayout(form)
        row = QHBoxLayout()
        self.screen = QComboBox()
        self.screen.addItem("All monitors", -1)
        try:
            from PySide6.QtGui import QGuiApplication
            for i, s in enumerate(QGuiApplication.screens()):
                self.screen.addItem(f"Monitor {i + 1}: {s.name()}", i)
        except Exception:
            pass
        self.apply_btn = QPushButton("Use this wallpaper")
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.clicked.connect(self.use)
        row.addWidget(self.screen)
        row.addStretch(1)
        row.addWidget(self.apply_btn)
        self.root.addLayout(row)
        extra = QHBoxLayout()
        self.match_accent = QCheckBox("Use the glow colour as the accent everywhere")
        try:
            from core.config import config
            self.match_accent.setChecked(bool(config.get("appearance.accent_follows_wallpaper", True)))
        except Exception:
            self.match_accent.setChecked(True)
        self.slide_every = QComboBox()
        for label, minutes in (("every 5 minutes", 5), ("every 15 minutes", 15), ("every hour", 60),
                               ("every day", 1440)):
            self.slide_every.addItem(label, minutes)
        self.slide_btn = QPushButton("Slideshow from a folder…")
        self.slide_btn.clicked.connect(lambda: self.slideshow())
        extra.addWidget(self.match_accent)
        extra.addStretch(1)
        extra.addWidget(self.slide_btn)
        extra.addWidget(self.slide_every)
        self.root.addLayout(extra)
        self.note = QLabel("Moving with music or the microphone reads only sound levels, live, on this PC; nothing is "
                           "recorded. Lower smoothness uses less power.")
        self._note = self.note.text()
        self.note.setObjectName("Muted")
        self.note.setWordWrap(True)
        self.root.addWidget(self.note)
        self.root.addStretch(1)
        self._load(DEFAULTS)

    def _slider(self, lo, hi, key, scale):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.valueChanged.connect(lambda v, k=key, sc=scale: self._set(k, v / sc if sc != 1 else v))
        s.setProperty("scale", scale)
        return s

    def _load(self, values):
        v = clean(values)
        for slider, key in ((self.angle, "Angle"), (self.size, "LogoScale"), (self.x, "LogoX"), (self.y, "LogoY"),
                            (self.glow, "Glow"), (self.sens, "Sensitivity"), (self.fps, "Fps")):
            slider.blockSignals(True)
            slider.setValue(int(round(v[key] * slider.property("scale"))))
            slider.blockSignals(False)
        self.bar_style.blockSignals(True)
        self.bar_style.setCurrentIndex(max(0, self.bar_style.findData(v["BarStyle"])))
        self.bar_style.blockSignals(False)
        self.values = v
        self.preview.set_values(v)

    def _set(self, key, value):
        self.values[key] = value
        self.values = clean(self.values)
        self.preview.set_values(self.values)

    def _preset(self, name):
        x, y = PRESETS[name]
        self._load({**self.values, "LogoX": x, "LogoY": y})

    def _pick(self, key):
        c = QColorDialog.getColor(QColor(self.values[key]), self, "Choose a colour")
        if c.isValid():
            self._set(key, c.name())

    def use(self):
        set_button_state(self.apply_btn, "busy", "Applying…")
        out = self.applier(self.values, self.screen.currentData())     # True / "" = applied; False / why = not
        ok = out is True or out == ""
        set_button_state(self.apply_btn, "done" if ok else "failed", "Done" if ok else "Didn't apply", 2200)
        self.note.setText(self._note if ok else out if isinstance(out, str) else "Plasma didn't answer.")
        if ok and self.match_accent.isChecked():
            self.accent_applier(self.values["Accent"])
        return ok

    def slideshow(self, folder: str = "", run=subprocess.run) -> bool:
        """Plasma's slideshow over a folder of pictures (it cross-fades between them)."""
        if not folder:
            from PySide6.QtWidgets import QFileDialog
            folder = QFileDialog.getExistingDirectory(self, "Pictures for the slideshow")
            if not folder:
                return False
        try:
            why = run_script(slideshow_script(folder, self.slide_every.currentData(), self.screen.currentData()), run)
        except ValueError as e:
            why = str(e)
        self.note.setText(why or f"Slideshow on: {folder}, {self.slide_every.currentText()}.")
        return not why


def build():
    return WallpaperPage()
