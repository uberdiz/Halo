"""
ui/avatar/companion.py

SAINT's avatar as a desktop companion: what FloatingAvatar does on its own between commands.

core/avatar/behavior.BehaviorEngine picks a beat (clip + anchor + how long) from the desktop context; this turns it
into motion: an eased glide to the anchor (~15 steps through FloatingAvatar._set_pos, which on Wayland goes through
the saint-shell KWin script), a climb up the focused window's edge while the "climb" clip plays, and a fade out of
the way of games and fullscreen apps. Event-driven where it can be: a focus change, a game starting, music starting
or stopping re-plans soon; otherwise the next beat comes when the current one is over. Never takes focus.
"""

import sys
import time
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from core.avatar import AvatarState, behavior
from core.events import EventType
from ui.reactive import ui_bus

BUSY = (AvatarState.LISTENING, AvatarState.THINKING, AvatarState.PLANNING, AvatarState.SPEAKING,
        AvatarState.WORKING)
GLIDE_STEPS, GLIDE_MS = 15, 40          # a ~0.6 s eased move
CLIMB_STEPS, CLIMB_MS = 15, 220         # a ~3.3 s climb up a window edge


def idle_seconds() -> float:
    """Seconds since the person last typed or moved the mouse: KDE's org.freedesktop.ScreenSaver
    GetSessionIdleTime (milliseconds on KDE), Windows' GetLastInputInfo; 0 when nothing answers."""
    if sys.platform == "win32":
        from core.focus_guard import _idle_seconds
        v = _idle_seconds()
        return v if v < 1e8 else 0.0
    try:
        from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return 0.0
        msg = QDBusMessage.createMethodCall("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
                                            "org.freedesktop.ScreenSaver", "GetSessionIdleTime")
        reply = bus.call(msg, QDBus.CallMode.Block, 300)
        if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
            return float(reply.arguments()[0]) / 1000.0
    except Exception:
        pass
    return 0.0


def battery_low() -> bool:
    try:
        import psutil
        b = psutil.sensors_battery()
    except Exception:
        return False
    return bool(b) and not b.power_plugged and b.percent <= 15


def _rect(g) -> tuple:
    return g.x(), g.y(), g.width(), g.height()


class Companion(QObject):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.engine = behavior.BehaviorEngine()
        self.active = None                   # the KWin report (class, x, y, w, h) of the focused window
        self.beat = None
        self.hidden = False                  # out of the way of a game / fullscreen app
        self._music = False
        self._shy_at = 0.0
        self._points, self._then = [], None
        self._beat_timer = QTimer(self)
        self._beat_timer.setSingleShot(True)
        self._beat_timer.timeout.connect(self.next_beat)
        self._move = QTimer(self)
        self._move.timeout.connect(self._advance)
        try:
            from core.saint_dbus import desktop_events
            desktop_events.active_window.connect(self._active)
        except Exception:                    # no QtDBus: no window anchors, the rest still plays
            pass
        ui_bus.event.connect(self._event)

    # ---- on / off
    def enabled(self) -> bool:
        s = self.win.view.cfg
        return s["enabled"] and s["behaviors"] and s["placement"] == "floating"

    def restart(self):
        if self.enabled():
            if not self._beat_timer.isActive():
                self._beat_timer.start(4000)
        else:
            self._beat_timer.stop()
            self.stop_motion()
            self.set_hidden(False)

    def soon(self, ms: int = 1200):
        """Re-plan in ``ms`` (something changed on the desktop), unless a beat is already due sooner."""
        if self.enabled() and not (self._beat_timer.isActive() and self._beat_timer.remainingTime() <= ms):
            self._beat_timer.start(ms)

    # ---- what's happening on the desktop
    def _active(self, cls, x, y, w, h):
        before = behavior.category(self.active[0]) if self.active else ""
        self.active = (cls, x, y, w, h)
        if behavior.category(cls) != before:
            self.soon()

    def _event(self, ev):
        if ev.type == EventType.GAME_MODE:
            self.soon(150)
        elif ev.type in (EventType.SPOTIFY_PLAYBACK_CHANGED, EventType.MEDIA_CHANGED):
            music = bool(ui_bus.now_playing().get("is_playing"))
            if music != self._music:
                self._music = music
                self.soon()

    def context(self) -> behavior.Context:
        screens = [_rect(s.geometry()) for s in QApplication.screens()]
        game = False
        try:
            from core.game_mode import game_mode
            game = game_mode.running or game_mode.overlays_blocked
        except Exception:
            pass
        self._music = bool(ui_bus.now_playing().get("is_playing"))
        return behavior.build_context(self.active, screens, datetime.now().hour, idle_seconds(), self._music, game,
                                      self.win.view.state in BUSY, True, battery_low())

    # ---- beats
    def next_beat(self):
        if not self.enabled():
            return
        ctx = self.context()
        beat = self.engine.next(ctx)
        self.beat = beat
        self.set_hidden(beat.anchor == "hidden")
        if beat.anchor != "hidden" and not self.win.dragging():
            clip = beat.new_clip or beat.clip
            if clip:
                self.win.view.play_clip(clip)
            elif not ctx.busy:
                self.win.view.stop_clip()
            self.go(beat.anchor, ctx.window)
        self._beat_timer.start(int(max(5.0, min(180.0, beat.seconds)) * 1000))

    def set_hidden(self, on: bool):
        if on != self.hidden:
            self.hidden = on
            if on:
                self.stop_motion()
            self.win.refresh_visibility()

    def _screen(self) -> tuple:
        return _rect(QApplication.primaryScreen().availableGeometry())   # ponytail: she lives on the primary

    def go(self, anchor: str, window=None):
        size = (self.win.width(), self.win.height())
        screen = self._screen()
        if anchor == "edge" and window:
            bottom = behavior.anchor_point("edge", size, window, screen, 0.0)
            self.glide(QPoint(*bottom), then=lambda: self._climb(window))
            return
        point = behavior.anchor_point(anchor, size, window, screen)
        self.glide(self.win.home() if point is None else QPoint(*point))

    def _climb(self, window):
        size, screen = (self.win.width(), self.win.height()), self._screen()
        self.win.view.play_clip("climb")
        points = [behavior.anchor_point("edge", size, window, screen, i / CLIMB_STEPS)
                  for i in range(1, CLIMB_STEPS + 1)]
        self._run(points, CLIMB_MS, lambda: self.win.view.play_clip("sit-swing"))

    # ---- motion: eased glides, never a snap
    def glide(self, target: QPoint, then=None):
        target = self.win.clear_spot(target)
        here = self.win.current_pos()
        if self.win.view.cfg["reduce_motion"]:
            points = [(target.x(), target.y())]
        else:
            points = behavior.glide_path((here.x(), here.y()), (target.x(), target.y()), GLIDE_STEPS)
        self._run(points, GLIDE_MS, then)

    def _run(self, points, interval, then=None):
        self._points, self._then = list(points), then
        self._move.start(interval)

    def _advance(self):
        if not self._points:
            self._move.stop()
            then, self._then = self._then, None
            if then:
                then()
            return
        x, y = self._points.pop(0)
        self.win.set_pos(QPoint(int(x), int(y)))

    def moving(self) -> bool:
        return self._move.isActive()

    def stop_motion(self):
        self._move.stop()
        self._points, self._then = [], None

    # ---- shy mode: the cursor came close
    def shy(self):
        now = time.monotonic()
        if not self.win.view.cfg["shy"] or self.moving() or now - self._shy_at < 1.5:
            return
        self._shy_at = now
        here = self.win.current_pos()
        x, y = behavior.shy_spot((here.x(), here.y()), (self.win.width(), self.win.height()), self._screen())
        self.glide(QPoint(x, y))
