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

Clips have an owner. One the person asked for (the menu, a voice command, the settings page) is theirs: her own
desktop play (beats, idle animations, gestures for SAINT's actions) can't replace it for USER_HOLD seconds, so a
dance keeps dancing and a sit keeps sitting. That override was why an animation played for a second and snapped
back to standing.
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
USER_HOLD = 60.0                  # seconds a clip the person asked for wins over her own desktop play
HEAD_AT = {"full": 0.13, "portrait": 0.42}    # her eyes, as a fraction of the view's height (look-at maths)


def quick3d_available() -> bool:
    return importlib.util.find_spec("PySide6.QtQuick3D") is not None


def picture_for(avatar: dict) -> QPixmap:
    """The 2D picture to draw for an avatar; a 3D one (or a broken file) falls back to SAINT.png."""
    pix = QPixmap(avatar["file"]) if avatar.get("kind") == "2d" else QPixmap()
    return pix if not pix.isNull() else QPixmap(str(paths.resource_path("SAINT.png")))


def _open_avatar_settings():
    """SAINT's Avatar settings page: a separate `saint --page Avatar` hands the running SAINT the command (calling
    the instance channel from inside SAINT's own process would wait on itself)."""
    import shutil
    import subprocess
    import sys
    exe = shutil.which("saint")
    argv = [exe] if exe else [sys.executable, str(paths.PROJECT_ROOT / "app.py")]
    try:
        subprocess.Popen(argv + ["--page", "Avatar"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


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
        self._clip, self._clip_t0, self.clip_pose = None, 0.0, None
        self._speed, self._user_until = 1.0, 0.0
        self.base_pose = None             # under every clip: sitting on a window's edge, turned the way she walks
        self.look = None                  # (yaw, pitch) degrees towards the cursor / the text being typed
        self.opacity = 1.0
        self.hop, self.pop = 0.0, 1.0
        ui_bus.event.connect(self._on_event)
        self.reload()

    def set_opacity(self, v: float):
        """Fade the whole avatar (the 3D scene and the 2D picture); FloatingAvatar animates it."""
        self.opacity = max(0.0, min(1.0, float(v)))
        root = self._q3d.rootObject() if getattr(self, "_q3d", None) is not None else None
        if root is not None:
            root.setProperty("opacity", self.opacity)
        self.update()

    # ---- animation clips (core/avatar/clips.py): played over the state pose
    def play_clip(self, clip, user: bool = False, speed: float = 1.0) -> bool:
        """Play a clip (a validated dict, or a clip name). ``user``: the person asked for it, so her own play can't
        replace it for a while. False if there's no such clip, or one the person asked for is still playing."""
        from core.avatar import clips
        if isinstance(clip, str):
            clip = clips.get(clip)
        if not clip or (not user and self.user_clip()):
            return False
        clip = clips.validate(clip)
        now = time.monotonic()
        self._clip, self._clip_t0, self._speed = clip, now, max(0.25, min(4.0, float(speed)))
        if user:
            lasting = clip["loop"] or clip["hold"]
            self._user_until = now + (USER_HOLD if lasting else clip["duration"] / self._speed)
        else:
            self._user_until = 0.0
        self._step_clip()
        self._sync_timer()
        return True

    def stop_clip(self, user: bool = True):
        """Stop the clip; her own play (``user`` False) doesn't stop one the person asked for."""
        if not user and self.user_clip():
            return
        self._clip, self.clip_pose, self._user_until = None, None, 0.0

    def playing(self) -> bool:
        return self._clip is not None

    def clip_name(self) -> str:
        return self._clip["name"] if self._clip else ""

    def user_clip(self) -> bool:
        """A clip the person asked for is still playing (and still theirs)."""
        return self._clip is not None and time.monotonic() < self._user_until

    def set_base_pose(self, pose):
        self.base_pose = dict(pose) if pose else None

    def set_look(self, look):
        self.look = tuple(look) if look else None

    def look_at(self, gx: float, gy: float):
        """Turn her head and eyes towards the global screen point (gx, gy)."""
        from core.avatar.body import look_angles
        top = self.mapToGlobal(QPoint(0, 0))
        eye_x = top.x() + self.width() / 2
        eye_y = top.y() + self.height() * HEAD_AT.get(self.cfg["view"] if self._holo() else "portrait", 0.42)
        self.look = look_angles(gx - eye_x, gy - eye_y)

    def _step_clip(self):
        if self._clip is None:
            return
        from core.avatar import clips
        self.clip_pose = clips.sample(self._clip, (time.monotonic() - self._clip_t0) * self._speed)
        if self.clip_pose is None:
            self._clip, self._user_until = None, 0.0

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
            r.setProperty("voiceStyle", self.cfg["voice_style"])
            r.setProperty("round", not self._holo())
            from core.avatar import outfits
            o = outfits.get(self.cfg["outfit"])
            r.setProperty("outfit", {"tints": o["tints"], "hide_accessories": o["hide_accessories"]})
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
                for dll in ("Qt6Quick3DAssetUtils.dll", "Qt6QuickEffects.dll"):    # MultiEffect: the round mask
                    ctypes.WinDLL(os.path.join(os.path.dirname(PySide6.__file__), dll))
            from PySide6.QtQuickWidgets import QQuickWidget
            w = QQuickWidget(self)
            # Clicks and drags belong to the avatar window (move, menu), not the 3D scene: the scene covered the
            # whole window in full-body view and swallowed every press, so she couldn't be dragged.
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
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
            root.setProperty("round", self.cfg["style"] != "hologram" and self.cfg["view"] != "full")
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
            look = None if self.cfg["reduce_motion"] else self.look
            bones = self._body.step(self.state, time.monotonic() - self._t0, self._level, dt, k, self.clip_pose,
                                    self.base_pose, look)
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
        self._step_clip()
        self._apply_face(self._timer.interval() / 1000)
        pose = self.clip_pose or {}
        self.hop, self.pop = float(pose.get("hop", 0.0)), float(pose.get("scale", 1.0))   # a clip's jump / size pulse
        if getattr(self, "_q3d", None) is not None and self._q3d.rootObject() is not None:
            root = self._q3d.rootObject()
            root.setProperty("level", self._level)
            root.setProperty("hop", self.hop)
            root.setProperty("popScale", self.pop)
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
        p.setOpacity(self.opacity)
        t = time.monotonic() - self._t0
        still = self.cfg["reduce_motion"]
        breathe = 0.0 if still else math.sin(t * 2 * math.pi / 4.0)
        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2 - self.hop * side * 0.06
        r = side / 2 * 0.80 * (1 + 0.015 * breathe) * min(1.1, self.pop)
        color = self.ring_color()

        if self._level > 0.02 and self.cfg["voice_style"] != "off":     # speaking / listening glow
            glow = QColor(color)
            for i in range(4):
                glow.setAlphaF(0.10 * self._level * (4 - i) / 4)
                p.setPen(QPen(glow, 2 + i * 3))
                p.drawEllipse(QRectF(cx - r - 4 - i * 3, cy - r - 4 - i * 3, 2 * (r + 4 + i * 3), 2 * (r + 4 + i * 3)))

        clip = QPainterPath()
        clip.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.save()
        p.setClipPath(clip)
        p.setOpacity(self.opacity * (0.5 if self.state == AvatarState.OFFLINE else 0.94 + 0.06 * breathe))
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


PLACE_NAME = "SAINT Avatar"           # the saint-shell KWin script reports drags of this window under this name


class FloatingAvatar(QWidget):
    """The avatar as its own always-on-top window. Drag to move, wheel to resize; both are remembered.
    Right-click: play an animation, or open the Avatar settings.

    On Wayland (HalOS) an app can't move its own window, so move() did nothing and she couldn't be dragged. There
    the window is placed through the saint-shell KWin script (ui/placement.wayland_place: which also keeps her off
    the taskbar), a drag is the compositor's own move (startSystemMove), and the script reports where she landed
    (PlacedMoved over D-Bus, core/saint_dbus.desktop_events) so the position is remembered."""

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowDoesNotAcceptFocus)        # a companion never steals your typing
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.view = AvatarView(self)
        self._drag = None
        self._pos = None
        self._keep = None
        self._fade = None
        from ui.avatar.companion import Companion
        self.companion = Companion(self)
        ui_bus.setting_changed.connect(self._setting)
        try:
            from core.saint_dbus import desktop_events
            desktop_events.placed_moved.connect(self._placed_moved)
            desktop_events.placed_over.connect(self._placed_over)
        except Exception:                            # no QtDBus: drags still work on X11 / Windows
            pass
        self.apply()

    def _wayland(self) -> bool:
        from ui import placement
        return placement.on_wayland()

    def _set_pos(self, pos: QPoint):
        """Put the window at ``pos`` (global logical pixels), on Wayland through the KWin script."""
        from PySide6.QtCore import QRect
        from ui import placement
        self._pos = QPoint(pos)
        placement.wayland_place(self, QRect(pos.x(), pos.y(), self.width(), self.height()), PLACE_NAME)
        if not self._wayland():
            self.move(pos)

    set_pos = _set_pos

    def current_pos(self) -> QPoint:
        return QPoint(self._pos) if self._pos is not None else self.pos()

    def home(self) -> QPoint:
        """Where the person put her (or the corner): where she goes back to between desktop play."""
        s = self.view.cfg
        return self._position(s, max(self.width(), self.height()))

    def dragging(self) -> bool:
        return self._drag is not None

    def _placed_moved(self, name: str, x: int, y: int):
        if name == PLACE_NAME:
            self._remember(QPoint(x, y))

    def _placed_over(self, name: str, cls: str, x: int, y: int, w: int, h: int):
        """The KWin script: the app window under her feet after a drop (w = 0: none), and where it goes after."""
        if name == PLACE_NAME:
            self.companion.perch_on((cls, x, y, w, h) if w > 0 else None)

    def _remember(self, pos: QPoint):
        """She was dropped here: keep off the wallpaper's logo (gliding off it, not jumping), remember the spot."""
        self.companion.stop_motion()
        self.companion.placed(pos)
        clear = self.clear_spot(pos)
        self._set_pos(pos)
        if clear != pos:
            self.companion.glide(clear)
        config.set("avatar.pos", [clear.x(), clear.y()])

    # ---- shown / faded out of the way
    def wanted(self) -> bool:
        s = self.view.cfg
        return s["enabled"] and s["placement"] != "off" and not self.companion.hidden and self.companion.present()

    def refresh_visibility(self):
        """Fade in or out (eased) to match wanted(); never activates the window."""
        from PySide6.QtCore import QEasingCurve, QVariantAnimation
        want = self.wanted()
        if want == (self.isVisible() and (self._fade is None or self._fade.endValue() == 1.0)):
            return
        if self._fade is not None:
            self._fade.stop()
        start = self.view.opacity if self.isVisible() else 0.0
        if want and not self.isVisible():
            self.view.set_opacity(0.0)
            self.show()
            self.view.play_clip("pop-in")              # she pops in, never just appears
            self.companion._appeared("show")
        a = QVariantAnimation(self)
        a.setStartValue(float(start))
        a.setEndValue(1.0 if want else 0.0)
        a.setDuration(320 if want else 260)
        a.setEasingCurve(QEasingCurve.OutCubic if want else QEasingCurve.InCubic)
        a.valueChanged.connect(lambda v: self.view.set_opacity(float(v)))
        if not want:
            a.finished.connect(lambda: self.hide() if not self.wanted() else None)
        self._fade = a
        a.start()

    def pop_up(self, start: QPoint):
        """Show her at ``start`` (below the screen's bottom edge) at full opacity: the companion then glides her
        up into view ("Hey SAINT"). Never activates the window."""
        if self._fade is not None:
            self._fade.stop()
            self._fade = None
        self._set_pos(start)
        self.view.set_opacity(1.0)
        if not self.isVisible():
            self.show()

    def _keep_out(self):
        """The living wallpaper's logo and voice bars, when they move with SAINT's voice: she stays off them (two
        things reacting to the voice in one spot read as one muddle). Plasma's config is re-read once a minute."""
        now = time.monotonic()
        if self._keep is None or now - self._keep[0] > 60:
            from core.avatar import behavior
            rect = None
            try:
                from ui.settings_pages import wallpaper
                raw = behavior.read_living()
                g = QApplication.primaryScreen().geometry()     # ponytail: the primary's wallpaper only
                rect = behavior.logo_rect(wallpaper.clean(raw) if raw is not None else None,
                                          (g.x(), g.y(), g.width(), g.height()))
            except Exception:                        # never let the wallpaper's config break the avatar
                pass
            self._keep = (now, rect)
        return self._keep[1]

    def clear_spot(self, pos: QPoint) -> QPoint:
        from core.avatar import behavior
        a = QApplication.primaryScreen().availableGeometry()
        x, y = behavior.avoid((pos.x(), pos.y()), (self.width(), self.height()), self._keep_out(),
                              (a.x(), a.y(), a.width(), a.height()))
        return QPoint(int(x), int(y))

    def _setting(self, key: str):
        if key.startswith("avatar") or key == "appearance.accent":
            self.apply()

    def apply(self):
        self.view.reload()
        s = self.view.cfg
        self.companion.restart()
        if not s["enabled"] or s["placement"] == "off":
            if self._fade is not None:
                self._fade.stop()
            self.hide()
            return
        size = s["size"] if s["placement"] == "floating" else max(SIZE_MIN, s["size"] * 2 // 3)
        w, h = self._dims(size)
        self.resize(w, h)
        self.view.setGeometry(0, 0, w, h)
        home = self.clear_spot(self._position(s, max(w, h)))
        if self.isVisible():
            self.companion.glide(home)          # a setting changed while she's out: back home, smoothly
        else:
            self._set_pos(home)
        self.refresh_visibility()

    def _position(self, s, size) -> QPoint:
        screen = QApplication.primaryScreen().availableGeometry()
        corner = QPoint(screen.right() - size - 24, screen.bottom() - size - 24)
        if s["placement"] != "floating" or not s["pos"]:
            return corner
        pos = QPoint(*s["pos"])
        from PySide6.QtCore import QRect
        on_screen = any(sc.availableGeometry().intersects(QRect(pos.x(), pos.y(), size, size))
                        for sc in QApplication.screens())
        return pos if on_screen else corner      # a monitor that's gone can't strand it off-screen

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton or self.view.cfg["placement"] != "floating":
            return
        self.companion.stop_motion()                 # the person's hand wins over desktop play
        handle = self.windowHandle()
        if self._wayland() and handle is not None and handle.startSystemMove():
            return                               # KWin moves her; the script reports where (_placed_moved)
        self._drag = e.globalPosition().toPoint() - self.pos()

    def enterEvent(self, e):
        if not QApplication.mouseButtons():          # not while the person is grabbing her
            self.companion.shy()
        super().enterEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self._remember(self.pos())

    def contextMenuEvent(self, e):
        from PySide6.QtWidgets import QMenu
        from core.avatar import clips
        menu = QMenu(self)
        play = menu.addMenu("Play animation")
        for name in clips.names():
            play.addAction(name.replace("-", " ").capitalize(), lambda n=name: self.companion.play_for_user(n))
        built = self.companion.engine.built
        if built:                                    # the moves she made up for the moment (behaviour engine)
            own = menu.addMenu("Her own moves")
            for c in reversed(built):
                own.addAction(c["name"], lambda c=c: self.companion.play_for_user(c))
        menu.addAction("Stop animation", self.view.stop_clip)
        menu.addSeparator()
        if self.view.cfg["style"] != "hologram":
            full = self.view.cfg["view"] == "full"
            menu.addAction("Head and shoulders" if full else "Full body",
                           lambda: self.set_view("portrait" if full else "full"))
        menu.addAction("Customize avatar…", lambda: _open_avatar_settings())
        menu.addAction("Hide avatar", lambda: (config.set("avatar.enabled", False),
                                               ui_bus.setting_changed.emit("avatar.enabled")))
        menu.exec(e.globalPos())

    def set_view(self, view: str):
        """Head and shoulders <-> full body (the right-click menu); saved like the settings page saves it."""
        config.set("avatar.view", view)
        ui_bus.setting_changed.emit("avatar.view")

    def wheelEvent(self, e):
        if self.view.cfg["placement"] != "floating":
            return
        size = max(SIZE_MIN, min(SIZE_MAX, self.view.cfg["size"] + (10 if e.angleDelta().y() > 0 else -10)))
        config.set("avatar.size", size)
        self.view.cfg["size"] = size
        w, h = self._dims(size)
        self.resize(w, h)
        self.view.setGeometry(0, 0, w, h)
        if self._pos is not None:
            self._set_pos(self._pos)              # Wayland: the KWin script sizes the window from the title

    def _dims(self, size: int):
        """Full body is a tall window (room for her and the props around her); portrait is square."""
        if self.view.cfg["view"] == "full" and self.view.cfg["style"] != "hologram":
            return int(size * 1.15), int(size * 1.8)
        return size, size
