"""
ui/avatar/companion.py

SAINT's avatar as a desktop companion: what FloatingAvatar does on its own between commands.

core/avatar/behavior.BehaviorEngine picks a beat (clip + anchor + how long) from the desktop context; this turns it
into motion: a walk along the taskbar or an eased glide/hop to the spot (FloatingAvatar._set_pos, which on Wayland
goes through the saint-shell KWin script), sitting on a window's top edge, a climb up its side, and a fade out of
the way of games and fullscreen apps. Event-driven where it can be: a focus change, a game starting, music starting
or stopping re-plans soon; otherwise the next beat comes when the current one is over. Never takes focus.

Where she rests: never over the window you're working in (behavior.settle: on the taskbar beside it, on its top edge
when there's room, in a corner, peeking in), on the monitor with the pointer or the focused window, and more and
more where you like her (core/avatar/habits.py). Dropped on a window she sits on its top edge and follows it; on a
music player she stands and dances to the beat while it plays.

Her eyes follow the pointer; while you type (keys, no pointer movement) they go to the caret (Windows) or the
focused window. On Wayland the pointer comes from the KWin script (a few reports a second while she's out);
elsewhere a light timer reads it, only while she's visible.

"Hey SAINT": she pops up from the bottom of the screen onto the taskbar (or stands on a window) with a hand by her
ear, and the voice layer is told she appeared (AVATAR_APPEARED, and core.followup.open_followup_window: talk to her
without the wake word); the same window opens when she finishes answering while she's out.
"""

import sys
import time
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtWidgets import QApplication

from core.avatar import AvatarState, behavior
from core.avatar.clips import SIT_POSE
from core.events import EventType
from ui.reactive import ui_bus

BUSY = (AvatarState.LISTENING, AvatarState.THINKING, AvatarState.PLANNING, AvatarState.SPEAKING,
        AvatarState.WORKING)
GLIDE_STEPS, GLIDE_MS = 15, 40          # a ~0.6 s eased move
CLIMB_STEPS, CLIMB_MS = 15, 220         # a ~3.3 s climb up a window edge
GAZE_MS = 150                           # how often her eyes catch up (the pointer is read here off Wayland)
PLACED_RESPECT_S = 600.0                # she stays on the monitor the person put her on for this long
WAKE_STATES = ("wake_detected", "command_listening", "listening")
STANDING_CLIPS = ("dance", "hop", "climb", "walk", "cheer", "spin", "bob", "pop-up", "stretch")


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


def caret_point():
    """The text caret on screen (global logical px), Windows only; None elsewhere or when there's none."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND),
                        ("hwndMenuOwner", wintypes.HWND), ("hwndMoveSize", wintypes.HWND),
                        ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]
        gti = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if not ctypes.windll.user32.GetGUIThreadInfo(0, ctypes.byref(gti)) or not gti.hwndCaret:
            return None
        pt = wintypes.POINT(gti.rcCaret.left, gti.rcCaret.bottom)
        ctypes.windll.user32.ClientToScreen(gti.hwndCaret, ctypes.byref(pt))
        dpr = QApplication.primaryScreen().devicePixelRatio() or 1.0
        return pt.x / dpr, pt.y / dpr
    except Exception:
        return None


def battery_low() -> bool:
    try:
        import psutil
        b = psutil.sensors_battery()
    except Exception:
        return False
    return bool(b) and not b.power_plugged and b.percent <= 15


def _rect(g) -> tuple:
    return g.x(), g.y(), g.width(), g.height()


FOLLOWUP_S = 20.0                       # she's out: you can talk to her without the wake word this long


def open_followup(seconds: float = FOLLOWUP_S) -> bool:
    """The voice layer's wake-free follow-up window (core/followup.py); False when it says no (games,
    fullscreen, calls) or this build doesn't have it."""
    try:
        from core.followup import open_followup_window
    except ImportError:
        return False
    try:
        return bool(open_followup_window(seconds=seconds, source="avatar"))
    except Exception:
        import logging
        logging.getLogger("SAINT.avatar").warning("avatar.followup_failed", exc_info=True)
        return False


class Companion(QObject):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.engine = behavior.BehaviorEngine()
        from core.avatar.habits import Habits
        self.habits = Habits()
        self.active = None                   # the KWin report (class, x, y, w, h) of the focused window
        self.perch = None                    # (class, x, y, w, h): the window the person sat her on
        self.sitting = False
        self.beat = None
        self.hidden = False                  # out of the way of a game / fullscreen app
        self.cursor = None                   # the pointer (global), and when it last moved
        self._cursor_at = 0.0
        self._idle_s, self._idle_at = 0.0, 0.0
        self.areas = []                      # Wayland: each monitor's area without panels (KWin script)
        self._placed_at = -1e9
        self._music = False
        self._shy_at = 0.0
        self._points, self._then = [], None
        self._beat_timer = QTimer(self)
        self._beat_timer.setSingleShot(True)
        self._beat_timer.timeout.connect(self.next_beat)
        self._move = QTimer(self)
        self._move.timeout.connect(self._advance)
        self.presence = behavior.Presence(win.view.cfg["presence"])
        self._hold = QTimer(self)                # "pop" mode: fade out when the hold runs out
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._hold_over)
        self._gesture_at = 0.0
        self._idle = QTimer(self)                # a small idle animation every 20-60 s while nothing else plays
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self._idle_animation)
        self._gaze = QTimer(self)
        self._gaze.timeout.connect(self._update_gaze)
        self._wake = False
        self._spoke = False
        try:
            from core.saint_dbus import desktop_events
            desktop_events.active_window.connect(self._active)
            desktop_events.cursor.connect(self._cursor)
            desktop_events.work_areas.connect(self._areas)
        except Exception:                    # no QtDBus: no window anchors, the rest still plays
            pass
        app = QApplication.instance()
        if app is not None:
            app.screenRemoved.connect(lambda _s: self.soon(300))   # a monitor went away: never stranded on it
        ui_bus.event.connect(self._event)

    # ---- on / off
    def enabled(self) -> bool:
        s = self.win.view.cfg
        return s["enabled"] and s["behaviors"] and s["placement"] == "floating"

    def present(self) -> bool:
        return self.presence.visible(time.monotonic())

    def restart(self):
        mode = self.win.view.cfg["presence"]
        if mode != self.presence.mode:
            self.presence = behavior.Presence(mode)
        s = self.win.view.cfg
        if s["enabled"] and s["placement"] != "off" and s["idle_animations"]:
            if not self._idle.isActive():
                self._idle.start(int(behavior.idle_delay(self.engine.rng) * 1000))
        else:
            self._idle.stop()
        if s["enabled"] and s["placement"] != "off" and not s["reduce_motion"]:
            self._gaze.start(GAZE_MS)
        else:
            self._gaze.stop()
            self.win.view.set_look(None)
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
        here = self.win.current_pos()
        if behavior.category(cls) != before:
            self.soon()
        elif not self.perch and behavior.covers((here.x(), here.y()), self._size(), (x, y, w, h)):
            self.soon(600)                   # the window you work in moved under her: out of its way

    def _cursor(self, x, y):
        self.cursor, self._cursor_at = (x, y), time.monotonic()
        self._update_look()

    def _areas(self, areas):
        self.areas = [tuple(a) for a in areas]

    def _event(self, ev):
        p = ev.payload or {}
        if ev.type in (EventType.ACTION_STARTED, EventType.TOOL_STARTED, EventType.PLAN_STARTED):
            action = str(p.get("action") or p.get("tool") or ("plan" if ev.type == EventType.PLAN_STARTED else ""))
            if not action.startswith("avatar"):          # her own animation commands aren't a cue for a gesture
                self.react(action)
        elif ev.type in (EventType.ACTION_FAILED, EventType.TOOL_FAILED):
            self.react(str(p.get("action") or p.get("tool") or ""), failed=True)
        elif ev.type == EventType.ACTION_TARGET and p.get("rects"):
            self.near_target(p["rects"][0])
        elif ev.type == EventType.NOTIFY:
            self.glance()
        elif ev.type == EventType.AVATAR_COMMAND:
            self.command(p)
        elif ev.type == EventType.GAME_MODE:
            self.soon(150)
        elif ev.type == EventType.ASSISTANT_STATE:
            state = str(p.get("state", ""))
            wake = state in WAKE_STATES
            if wake and not self._wake:
                self.summon()
            self._wake = wake
            if self._spoke and state != "speaking" and self.win.isVisible() and not self.hidden:
                open_followup()                          # she answered and is still out: just talk back
            self._spoke = state == "speaking"
        elif ev.type in (EventType.SPOTIFY_PLAYBACK_CHANGED, EventType.MEDIA_CHANGED):
            music = bool(ui_bus.now_playing().get("is_playing"))
            if music != self._music:
                self._music = music
                if self.perch:
                    self._on_perch()
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
        ctx = behavior.build_context(self.active, screens, datetime.now().hour, idle_seconds(), self._music, game,
                                     self.win.view.state in BUSY, True, battery_low())
        ctx.bias = self.habits.anchor_bias(behavior.category(ctx.app_class), ctx.hour)
        return ctx

    # ---- beats
    def next_beat(self):
        if not self.enabled():
            return
        ctx = self.context()
        beat = self.engine.next(ctx)
        self.beat = beat
        self.set_hidden(beat.anchor == "hidden")
        v = self.win.view
        if beat.anchor != "hidden" and self.present() and not self.win.dragging():
            if v.user_clip():                            # the person's animation plays on: try again after it
                self._beat_timer.start(int(max(3.0, min(60.0, v._user_until - time.monotonic())) * 1000) + 200)
                return
            if self.perch:                               # she stays on the window she was put on
                self._on_perch(beat.new_clip or beat.clip)
            else:
                clip = beat.new_clip or beat.clip
                if clip:
                    v.play_clip(clip)
                elif not ctx.busy:
                    v.stop_clip(user=False)
                self.go(beat.anchor, ctx.window)
        self._beat_timer.start(int(max(5.0, min(180.0, beat.seconds)) * 1000))

    def set_hidden(self, on: bool):
        if on != self.hidden:
            self.hidden = on
            if on:
                self.stop_motion()
            self.win.refresh_visibility()

    def _size(self) -> tuple:
        return self.win.width(), self.win.height()

    def _view(self) -> str:
        return behavior.view_of(self.win.view.cfg)

    def _screen(self) -> tuple:
        """The available area of the monitor she belongs on: the pointer's or the focused window's (the one she
        was put on, for a while after the person put her there)."""
        screens = QApplication.screens() or [QApplication.primaryScreen()]
        here = self.win.current_pos()
        size = self._size()
        centre = (here.x() + size[0] / 2, here.y() + size[1] / 2)
        if time.monotonic() - self._placed_at < PLACED_RESPECT_S:
            i = behavior.pick_screen([_rect(s.geometry()) for s in screens], here=centre)
        else:
            i = behavior.pick_screen([_rect(s.geometry()) for s in screens], self.cursor,
                                     self.active[1:5] if self.active else None, centre)
        geo, avail = _rect(screens[i].geometry()), _rect(screens[i].availableGeometry())
        for a in self.areas:                 # Wayland: Qt doesn't know where the panels are; KWin does
            if behavior.overlap(a, geo) > 0.5 * a[2] * a[3]:
                return a
        return avail

    def _set_sitting(self, on: bool):
        self.sitting = on
        self.win.view.set_base_pose(SIT_POSE if on else None)

    def _fits(self, clip):
        """Clips that need her standing don't play while she sits."""
        name = clip.get("name") if isinstance(clip, dict) else clip
        return not (self.sitting and name in STANDING_CLIPS)

    def go(self, anchor: str, window=None):
        size, screen, view = self._size(), self._screen(), self._view()
        here = self.win.current_pos()
        here = (here.x(), here.y())
        if anchor == "edge" and window:
            self._set_sitting(False)
            bottom = behavior.anchor_point("edge", size, window, screen, 0.0)
            self.glide(QPoint(*bottom), then=lambda: self._climb(window))
            return
        if anchor == "titlebar" and window and "titlebar" in behavior.settle_spots(size, view, screen, window):
            stand = self._music
            point = behavior.perch_point(size, window, view, sitting=not stand)
            self._set_sitting(False)
            self.glide(QPoint(*point), then=lambda: self._land(stand))
            return
        sx, sy, sw, sh = screen
        on_screen = sx - size[0] // 2 <= here[0] <= sx + sw - size[0] // 2 and sy - size[1] // 2 <= here[1] <= sy + sh
        if anchor == "stay" and on_screen and not behavior.covers(here, size, window):
            return                                       # where the person put her, and out of the way: stays
        if anchor == "peek":
            name, point = "peek", behavior.settle_spots(size, view, screen, window)["peek"]
        else:
            fav = self.habits.favourite_spot(screen, size, datetime.now().hour)
            bias = self.habits.anchor_bias(behavior.category(self.active[0] if self.active else ""),
                                           datetime.now().hour)
            name, point = behavior.settle(size, view, screen, window, here, bias, fav)
        self.habits.settled(name, datetime.now().hour)
        if name == "titlebar" and window:
            self._set_sitting(False)
            self.glide(QPoint(*point), then=lambda: self._land(False))
            return
        self._set_sitting(False)
        self.glide(QPoint(*point))

    def _land(self, standing: bool):
        """On a window's top edge: sit and swing her legs, or (music) stand and dance to the beat."""
        if standing:
            self._set_sitting(False)
            self.win.view.play_clip("bob", speed=behavior.dance_speed(ui_bus.now_playing()))
        else:
            self._set_sitting(True)
            self.win.view.play_clip("sit-swing")

    def _climb(self, window):
        size, screen = self._size(), self._screen()
        self.win.view.play_clip("climb")
        points = [behavior.anchor_point("edge", size, window, screen, i / CLIMB_STEPS)
                  for i in range(1, CLIMB_STEPS + 1)]
        self._run(points, CLIMB_MS, lambda: self._land(False))

    # ---- perched on a window the person put her on
    def perch_on(self, window):
        """The person dropped her on ``window`` (class, x, y, w, h), or it moved: onto its top edge. None or a
        zero width: she's on no window (any more)."""
        if not window or window[3] <= 0:
            if self.perch:
                self.perch = None
                self._set_sitting(False)
                self.win.view.stop_clip(user=False)
                self.soon(800)
            return
        new = not self.perch or self.perch[0] != window[0]
        self.perch = tuple(window)
        if new:
            self.habits.perched(behavior.category(window[0]))
        self._on_perch()

    def _on_perch(self, clip=None):
        """Sit on (or, with music on a music player, dance on) the perch window's top edge."""
        cls, *rect = self.perch
        dance = self._music and behavior.category(cls) == "music"
        here = self.win.current_pos()
        size = self._size()
        point = behavior.perch_point(size, tuple(rect), self._view(), x=here.x() + size[0] / 2, sitting=not dance)

        def settle_in():
            if dance:
                self._set_sitting(False)
                self.win.view.play_clip("bob", speed=behavior.dance_speed(ui_bus.now_playing()))
                return
            self._set_sitting(True)
            if not clip or not self._fits(clip) or not self.win.view.play_clip(clip):
                if self.win.view.clip_name() != "sit-swing":
                    self.win.view.play_clip("sit-swing")
        if (here.x(), here.y()) != tuple(point):
            self.glide(QPoint(*point), then=settle_in)
        else:
            settle_in()

    def placed(self, pos: QPoint):
        """The person dropped her here (FloatingAvatar._remember): learn it, stay on this monitor a while."""
        self._placed_at = time.monotonic()
        screen = QApplication.screenAt(pos + QPoint(self.win.width() // 2, self.win.height() // 2))
        if screen is not None:
            self.habits.placed((pos.x(), pos.y()), self._size(), _rect(screen.availableGeometry()),
                               datetime.now().hour)

    # ---- "Hey SAINT": she pops up from the bottom of the screen and listens
    def summon(self):
        s = self.win.view.cfg
        if not s["enabled"] or s["placement"] == "off" or self.hidden:
            return
        now = time.monotonic()
        self.presence.poke(now)
        if self.presence.mode == "pop":
            self._hold.start(int(self.presence.hold * 1000) + 100)
        shown = self.win.isVisible() and self.win.view.opacity > 0.5
        if shown or self.perch or self.win.dragging() or s["placement"] != "floating":
            self.win.refresh_visibility()
            self.win.view.play_clip("listen")
            self._appeared("wake")
            return
        size, screen, view = self._size(), self._screen(), self._view()
        here = self.win.current_pos()
        window = self.active[1:5] if self.active else None
        name, point = behavior.settle(size, view, screen, window, (here.x(), here.y()))
        stand_on_window = name == "titlebar"
        if stand_on_window:
            point = behavior.perch_point(size, window, view, sitting=False)
        self._set_sitting(False)
        start = QPoint(point[0], screen[1] + screen[3] + 8)    # just below the bottom edge
        self.win.pop_up(start)
        self.win.view.play_clip("pop-up")
        self.glide(QPoint(*point), then=lambda: self.win.view.play_clip("listen"))
        self._appeared("wake")

    def _appeared(self, reason: str):
        from core.events import event_bus
        event_bus.emit_event(EventType.AVATAR_APPEARED, {"reason": reason})
        open_followup()

    # ---- SAINT's actions: pop in, make a gesture that fits, fade out again ("pop" presence)
    def react(self, action: str, failed: bool = False, dx=None):
        s = self.win.view.cfg
        now = time.monotonic()
        if not s["enabled"] or s["placement"] == "off" or self.hidden:
            return
        popped = self.presence.poke(now)
        if self.presence.mode == "pop":
            self._hold.start(int(self.presence.hold * 1000) + 100)
        if popped:
            self.win.refresh_visibility()
        if now - self._gesture_at < 1.2 and not failed:     # a burst of tool calls: one gesture, not twenty
            return
        self._gesture_at = now
        clip = behavior.gesture(action, failed, dx)
        if self._fits(clip):
            QTimer.singleShot(700 if popped else 0, lambda: self.win.view.play_clip(clip))

    def near_target(self, rect):
        """An action outlined the window it acts on (ACTION_TARGET): she goes and stands by it, pointing."""
        if self.hidden or not self.present() or self.win.dragging() or len(rect) != 4 or self.perch:
            return
        size = self._size()
        point = behavior.anchor_point("titlebar", size, tuple(rect), self._screen())
        if point:
            here = self.win.current_pos()
            self._set_sitting(False)
            self.glide(QPoint(*point))
            self.win.view.play_clip(behavior.gesture("windows", dx=rect[0] + rect[2] / 2 - (here.x() + size[0] / 2)))

    def glance(self):
        """A notification: a quick look toward it, if she's out anyway (no popping in for a toast)."""
        now = time.monotonic()
        if self.hidden or not self.present() or not self.win.isVisible() or now - self._gesture_at < 1.5:
            return
        self._gesture_at = now
        self.win.view.play_clip("glance")

    def command(self, p: dict):
        """AVATAR_COMMAND: from the avatar.* actions (any thread, via the event bus) or the settings page."""
        if p.get("settings"):
            ui_bus.setting_changed.emit("avatar")          # FloatingAvatar, the settings page preview ... re-read
        if p.get("stop"):
            self.win.view.stop_clip()
        clip = p.get("clip") or p.get("play")
        if clip:
            if self.presence.poke(time.monotonic()):       # "pop" mode: asked to play, so she comes out for it
                self.win.refresh_visibility()
            if self.presence.mode == "pop":
                self._hold.start(int(self.presence.hold * 1000) + 3000)
            self.play_for_user(clip)

    def play_for_user(self, clip) -> bool:
        """The person asked for this animation: it's theirs (her own play won't cut it short) and it's learned."""
        if not self.win.view.play_clip(clip, user=True):
            return False
        name = clip.get("name") if isinstance(clip, dict) else str(clip)
        if name in STANDING_CLIPS and self.sitting:
            self._set_sitting(False)
        self.habits.asked(name)
        return True

    def _idle_animation(self):
        v = self.win.view
        if (not self.hidden and self.present() and self.win.isVisible() and not v.playing() and not self.moving()
                and v.state == AvatarState.IDLE and not v.cfg["reduce_motion"]):
            hour = datetime.now().hour
            pool = behavior.NIGHT_CLIPS if hour >= 23 or hour < 6 else behavior.IDLE_CLIPS
            clip = self.habits.pick_clip(self.engine.rng, [c for c in pool if self._fits(c)] or ["look-around"])
            v.play_clip(clip)
        if v.cfg["idle_animations"]:
            self._idle.start(int(behavior.idle_delay(self.engine.rng) * 1000))

    def _hold_over(self):
        if self.win.view.state in BUSY:                     # still listening / answering: she stays
            self.presence.poke(time.monotonic())
            self._hold.start(int(self.presence.hold * 1000))
            return
        if not self.present():
            self.win.refresh_visibility()
            QTimer.singleShot(400, lambda: None if self.present() else self.win.set_pos(self.win.home()))
        else:
            self._hold.start(500)

    # ---- where she looks: the pointer, or what you're typing
    def _update_gaze(self):
        if not self.win.isVisible():
            return
        now = time.monotonic()
        from ui import placement
        if not placement.on_wayland():                      # Wayland: the KWin script reports the pointer
            from PySide6.QtGui import QCursor
            p = QCursor.pos()
            if self.cursor != (p.x(), p.y()):
                self.cursor, self._cursor_at = (p.x(), p.y()), now
        if now - self._idle_at > 1.0:                       # input idle time: a cheap query, once a second
            self._idle_s, self._idle_at = idle_seconds(), now
        self._update_look()

    def typing(self) -> bool:
        """Keys are going in (input, but the pointer hasn't moved for a while)."""
        return self._idle_s < 1.5 and time.monotonic() - self._cursor_at > 2.0

    def _update_look(self):
        v = self.win.view
        if not self.win.isVisible() or v.cfg["reduce_motion"]:
            return
        target = None
        if v.state in (AvatarState.LISTENING, AvatarState.SPEAKING):
            target = None                                   # talking with you: she looks at you
        elif self.typing():
            target = caret_point()
            if target is None and self.active:
                _c, x, y, w, h = self.active
                target = (x + w / 2, y + h * 0.6)
        elif self.cursor and time.monotonic() - self._cursor_at < 8.0:
            target = self.cursor
        if target is None:
            v.set_look(None)
        else:
            v.look_at(*target)

    # ---- motion: walks along the floor, eased glides and hops, never a snap
    def glide(self, target: QPoint, then=None):
        target = self.win.clear_spot(target)
        here = self.win.current_pos()
        v = self.win.view
        if v.cfg["reduce_motion"]:
            self._run([(target.x(), target.y())], GLIDE_MS, then)
            return
        size = self._size()
        plan = None if self.sitting else behavior.walk_plan((here.x(), here.y()), (target.x(), target.y()), size)
        if plan and v.play_clip("walk", speed=plan[1]):
            points, _speed, direction = plan
            v.set_base_pose({"hips_y": 65.0 * direction})   # turned the way she walks

            def arrived():
                if v.clip_name() == "walk":
                    v.stop_clip(user=False)
                v.set_base_pose(SIT_POSE if self.sitting else None)
                if then:
                    then()
            self._run(points, GLIDE_MS, arrived)
            return
        if abs(target.y() - here.y()) > size[1] * 0.15 and not self.sitting:
            v.play_clip("hop")
        self._run(behavior.glide_path((here.x(), here.y()), (target.x(), target.y()), GLIDE_STEPS), GLIDE_MS, then)

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
        v = self.win.view
        if v.base_pose and "hips_y" in v.base_pose:          # stopped mid-walk: face front again
            v.set_base_pose(SIT_POSE if self.sitting else None)

    # ---- shy mode: the cursor came close
    def shy(self):
        now = time.monotonic()
        if not self.win.view.cfg["shy"] or self.moving() or now - self._shy_at < 1.5 or self.perch:
            return
        self._shy_at = now
        here = self.win.current_pos()
        x, y = behavior.shy_spot((here.x(), here.y()), self._size(), self._screen())
        self.glide(QPoint(x, y))
