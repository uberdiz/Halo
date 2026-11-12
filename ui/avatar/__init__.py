"""
ui/avatar

SAINT's avatar on screen. ``AvatarView`` paints it (the settings preview uses it inside the page);
``FloatingAvatar`` is the frameless, draggable, wheel-resizable window around one.

3D: a .vrm/.glb is drawn by QtQuick3D's RuntimeLoader (avatar3d.qml) inside the ring, as plain glTF
(VRM extensions such as spring bones and expressions are ignored). Without QtQuick3D, or if the model
fails to load, the 2D picture (SAINT.png) is drawn instead.

Animation: a slow breathing scale/opacity, a state-coloured ring, a spinning arc while thinking,
planning or working, and a glow that follows the TTS playback level (core.audio_echo) while
speaking or the mic level while listening. No viseme data exists, so lip-sync is amplitude only.
The timer runs only while the view is visible and reduce-motion is off.
"""

import importlib.util
import math
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from core import paths
from core.audio_echo import playback_monitor
from core.avatar import COLORS, SIZE_MAX, SIZE_MIN, AvatarState, AvatarStateMachine, settings
from core.avatar import library
from core.config import config
from ui.reactive import ui_bus

_SPIN = (AvatarState.THINKING, AvatarState.PLANNING, AvatarState.WORKING)


def quick3d_available() -> bool:
    return importlib.util.find_spec("PySide6.QtQuick3D") is not None


def picture_for(avatar: dict) -> QPixmap:
    """The 2D picture to draw for an avatar; a 3D one (or a broken file) falls back to SAINT.png."""
    pix = QPixmap(avatar["file"]) if avatar.get("kind") == "2d" else QPixmap()
    return pix if not pix.isNull() else QPixmap(str(paths.resource_path("SAINT.png")))


class AvatarView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.machine = AvatarStateMachine(str(ui_bus.state.get("state", "offline")))
        self.state = self.machine.current()
        self._t0 = time.monotonic()
        self._level = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        from core.avatar.face import FaceDriver
        self._face = FaceDriver()
        from core.avatar.body import BodyDriver
        self._body = BodyDriver()
        self._task = {"title": "", "steps": [], "index": -1}
        ui_bus.event.connect(self._on_event)
        self.reload()

    def reload(self):
        self.cfg = settings()
        avatar = library.get(self.cfg["id"])
        self.avatar = avatar
        self._pix = picture_for(avatar)
        self._setup_3d(avatar)
        if getattr(self, "_q3d", None) is not None and self._q3d.rootObject() is not None:
            r = self._q3d.rootObject()
            r.setProperty("hologram", self.cfg["style"] == "hologram")
            r.setProperty("tint", QColor(self.cfg["accent"] or "#ff9a1f"))
            r.setProperty("motion", not self.cfg["reduce_motion"])
            r.setProperty("view", self.cfg["view"])
            r.setProperty("props", self.cfg["props"])
            self._place_3d()
        accent = self.cfg["accent"] or config.get("appearance.accent", COLORS[AvatarState.IDLE])
        self._accent = QColor(accent) if QColor(accent).isValid() else QColor(COLORS[AvatarState.IDLE])
        self.setToolTip(f"{self.cfg['name']} — {self.state.value}")
        self._sync_timer()
        self.update()

    def _setup_3d(self, avatar: dict):
        want = avatar.get("kind") == "3d" and quick3d_available() and avatar.get("file")
        if getattr(self, "_q3d", None) is not None and (not want or self._q3d_file != avatar["file"]):
            self._q3d.deleteLater()
            self._q3d = None
        if not want or getattr(self, "_q3d", None) is not None:
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6 import QtQuick3D  # noqa: F401  loads the Qt Quick 3D libraries the QML plugin needs
            import os
            if os.name == "nt":            # no Python module loads AssetUtils; its QML plugin can't find it alone
                import ctypes
                import PySide6
                ctypes.WinDLL(os.path.join(os.path.dirname(PySide6.__file__), "Qt6Quick3DAssetUtils.dll"))
            from PySide6.QtQuickWidgets import QQuickWidget
            w = QQuickWidget(self)
            w.setAttribute(Qt.WA_AlwaysStackOnTop)
            w.setAttribute(Qt.WA_TranslucentBackground)
            w.setClearColor(Qt.transparent)
            w.setResizeMode(QQuickWidget.SizeRootObjectToView)
            w.setSource(QUrl.fromLocalFile(str(paths.resource_path("ui", "avatar", "avatar3d.qml"))))
            root = w.rootObject()
            if root is None:
                raise RuntimeError(w.errors())
            root.setProperty("flip", avatar.get("meta", {}).get("version") == "0.x")
            root.setProperty("motion", not self.cfg["reduce_motion"])
            root.setProperty("hologram", self.cfg["style"] == "hologram")
            root.setProperty("view", self.cfg["view"])
            root.setProperty("props", self.cfg["props"])
            root.setProperty("tint", QColor(self.cfg["accent"] or "#ff9a1f"))
            if avatar.get("qml"):          # balsam scene: named MorphTargets we drive (blink, visemes, expressions)
                root.setProperty("component", QUrl.fromLocalFile(avatar["qml"]))
            else:
                root.setProperty("source", QUrl.fromLocalFile(avatar["file"]))
            root.failedChanged.connect(self._3d_failed)
            self._q3d, self._q3d_file = w, avatar["file"]
            self._place_3d()
            w.show()
        except Exception as e:                      # no 3D on this machine: the 2D picture stays
            import logging
            logging.getLogger("SAINT.avatar").warning("avatar.3d_unavailable %s", e)
            self._q3d = None

    def _track_task(self, kind, p: dict):
        """The plan SAINT is running, for the caption and plan cards around the full-body avatar."""
        from core.events import EventType
        if kind == EventType.PLAN_STARTED:
            steps = [str(s.get("title") or s.get("action") or "") for s in p.get("steps", [])]
            self._task = {"title": str(p.get("title") or "Working on it"), "steps": steps, "index": 0}
        elif kind == EventType.PLAN_STEP and self._task["steps"]:
            self._task["index"] = int(p.get("index", self._task["index"]))
            self._task["title"] = str(p.get("title") or self._task["title"])
        elif kind == EventType.PLAN_DONE:
            self._task = {"title": "Done" if p.get("ok") else "Couldn't finish that", "steps": [], "index": -1}
        root = self._q3d.rootObject() if getattr(self, "_q3d", None) is not None else None
        if root is not None:
            root.setProperty("taskTitle", self._task["title"])
            root.setProperty("taskSteps", self._task["steps"])
            root.setProperty("taskIndex", self._task["index"])

    def _apply_face(self, dt: float):
        """Face weights for this frame -> the QML scene, which owns the MorphTargets (see avatar3d.qml)."""
        q3d = getattr(self, "_q3d", None)
        root = q3d.rootObject() if q3d is not None else None
        if root is None or not self.avatar.get("qml") or not root.property("morphCount"):
            return                                 # no controllable face, or the scene is still loading
        weights = self._face.step(self.state, time.monotonic() - self._t0, self._level, dt)
        if root.property("vroid"):
            from core.avatar.face import to_vroid
            weights = to_vroid(weights)
        root.setProperty("faceWeights", {k: float(v) for k, v in weights.items()})
        if root.property("boneCount"):
            k = 0.0 if self.cfg["reduce_motion"] else self.cfg["motion"]
            bones = self._body.step(self.state, time.monotonic() - self._t0, self._level, dt, k)
            root.setProperty("bodyRot", {b: [float(c) for c in q] for b, q in bones.items()})
        root.setProperty("activity", self.state.value)
        root.setProperty("level", float(self._level))

    def _3d_failed(self):
        if self._q3d is not None and self._q3d.rootObject().property("failed"):
            import logging
            logging.getLogger("SAINT.avatar").warning("avatar.3d_load_failed %s", self._q3d_file)
            self._q3d.deleteLater()
            self._q3d = None
            self.update()

    def _place_3d(self):
        if getattr(self, "_q3d", None) is not None:
            if self._holo():
                self._q3d.setGeometry(0, 0, self.width(), self.height())
                return
            side = min(self.width(), self.height())
            r = int(side / 2 * 0.80)
            self._q3d.setGeometry(int(self.width() / 2 - r), int(self.height() / 2 - r), 2 * r, 2 * r)

    def _holo(self) -> bool:
        """True when the 3D view is its own frame (hologram or full body): no disc or ring around it."""
        return getattr(self, "_q3d", None) is not None and (self.cfg["style"] == "hologram" or
                                                            self.cfg["view"] == "full")

    def resizeEvent(self, e):
        self._place_3d()
        super().resizeEvent(e)

    def _on_event(self, ev):
        self._track_task(ev.type, ev.payload or {})
        new = self.machine.feed(ev.type, ev.payload)
        if new != self.state:
            self.state = new
            self.setToolTip(f"{self.cfg['name']} — {new.value}")
            self.update()

    # ---- animation runs only while seen
    def _sync_timer(self):
        if self.isVisible():
            self._timer.setInterval(500 if self.cfg["reduce_motion"] else 33)
            self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, e):
        self._sync_timer()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        state = self.machine.current()           # transient flashes expire here
        if state == AvatarState.SPEAKING:
            target = min(1.0, playback_monitor.level() * 6)
        elif state == AvatarState.LISTENING:
            target = min(1.0, float(ui_bus.level) * 4)
        else:
            target = 0.0
        self._level += (target - self._level) * 0.35
        self._apply_face(self._timer.interval() / 1000)
        if getattr(self, "_q3d", None) is not None and self._q3d.rootObject() is not None:
            self._q3d.rootObject().setProperty("level", self._level)
        self.state = state
        self.update()

    def ring_color(self) -> QColor:
        return QColor(self._accent) if self.state == AvatarState.IDLE else QColor(COLORS[self.state])

    def paintEvent(self, _e):
        if self._holo():                           # the hologram is its own frame: no disc or ring
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        t = time.monotonic() - self._t0
        still = self.cfg["reduce_motion"]
        breathe = 0.0 if still else math.sin(t * 2 * math.pi / 4.0)
        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2
        r = side / 2 * 0.80 * (1 + 0.015 * breathe)
        color = self.ring_color()

        if self._level > 0.02:                    # speaking / listening glow
            glow = QColor(color)
            for i in range(4):
                glow.setAlphaF(0.10 * self._level * (4 - i) / 4)
                p.setPen(QPen(glow, 2 + i * 3))
                p.drawEllipse(QRectF(cx - r - 4 - i * 3, cy - r - 4 - i * 3, 2 * (r + 4 + i * 3), 2 * (r + 4 + i * 3)))

        clip = QPainterPath()
        clip.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.save()
        p.setClipPath(clip)
        p.setOpacity(0.5 if self.state == AvatarState.OFFLINE else 0.94 + 0.06 * breathe)
        if getattr(self, "_q3d", None) is not None:   # the 3D view draws the picture
            p.restore()
            pix = None
        else:
            pix = self._pix.scaled(int(2 * r) + 1, int(2 * r) + 1, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        if pix is not None:
            p.drawPixmap(int(cx - pix.width() / 2), int(cy - pix.height() / 2), pix)
            p.restore()

        ring = QRectF(cx - r - 3, cy - r - 3, 2 * r + 6, 2 * r + 6)
        p.setPen(QPen(color, max(2.0, side / 50)))
        p.drawEllipse(ring)
        if self.state in _SPIN:
            arc = QColor(color).lighter(150)
            pen = QPen(arc, max(3.0, side / 30))
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            start = 0 if still else int(-t * 360 * 16) % (360 * 16)
            p.drawArc(ring, start, 90 * 16)
        p.end()


class FloatingAvatar(QWidget):
    """The avatar as its own always-on-top window. Drag to move, wheel to resize; both are remembered."""

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.view = AvatarView(self)
        self._drag = None
        ui_bus.setting_changed.connect(self._setting)
        self.apply()

    def _setting(self, key: str):
        if key.startswith("avatar") or key == "appearance.accent":
            self.apply()

    def apply(self):
        self.view.reload()
        s = self.view.cfg
        if not s["enabled"] or s["placement"] == "off":
            self.hide()
            return
        size = s["size"] if s["placement"] == "floating" else max(SIZE_MIN, s["size"] * 2 // 3)
        w, h = self._dims(size)
        self.resize(w, h)
        self.view.setGeometry(0, 0, w, h)
        self.move(self._position(s, max(w, h)))
        self.show()

    def _position(self, s, size) -> QPoint:
        screen = QApplication.primaryScreen().availableGeometry()
        corner = QPoint(screen.right() - size - 24, screen.bottom() - size - 24)
        if s["placement"] != "floating" or not s["pos"]:
            return corner
        pos = QPoint(*s["pos"])
        on_screen = any(sc.availableGeometry().intersects(self.geometry().translated(pos - self.pos()))
                        for sc in QApplication.screens())
        return pos if on_screen else corner      # a monitor that's gone can't strand it off-screen

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.view.cfg["placement"] == "floating":
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            config.set("avatar.pos", [self.x(), self.y()])

    def wheelEvent(self, e):
        if self.view.cfg["placement"] != "floating":
            return
        size = max(SIZE_MIN, min(SIZE_MAX, self.view.cfg["size"] + (10 if e.angleDelta().y() > 0 else -10)))
        config.set("avatar.size", size)
        self.view.cfg["size"] = size
        w, h = self._dims(size)
        self.resize(w, h)
        self.view.setGeometry(0, 0, w, h)

    def _dims(self, size: int):
        """Full body is a tall window (room for her and the props around her); portrait is square."""
        if self.view.cfg["view"] == "full" and self.view.cfg["style"] != "hologram":
            return int(size * 1.15), int(size * 1.8)
        return size, size
