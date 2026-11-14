"""
core/saint_dbus.py

SAINT on the session bus (Linux): org.saintos.Saint at /Saint, for the parts of Halo that live outside
SAINT's process — the KWin script (screen edge, window closes), the reactive wallpaper and the Plasma widgets.

    methods  ToggleOverlay()  Show()  OpenPage(s name)  State() -> s  PlaySupernova(s "x,y")
             PlacedMoved(s "name|x,y")             a SAINT helper window the person dragged (the avatar) landed here
             ActiveWindow(s "class|x,y,w,h")        the focused app window and where it is (the avatar's desktop play)
             PlacedOver(s "name|class|x,y,w,h")     the app window a dropped helper (the avatar) stands on, and where
                                                    it is when it moves; w = 0: it's gone (or she was dropped on none)
             Cursor(s "x,y")                        the mouse pointer, a few times a second while the avatar is out
             WorkAreas(s "x,y,w,h;...")             each monitor's area without panels (Qt doesn't know it on Wayland)
    signal   StateChanged(s state, d level)     assistant state ("idle", "listening", "thinking",
                                                "speaking", ...) and the microphone level 0..1

The methods go through the same closed command set as core/instance.py, or (geometry) through ``desktop_events``.
No-op where there's no session bus (Windows, a bare console).
"""

import json
import logging
import re
import time

from PySide6.QtCore import ClassInfo, QObject, Signal, Slot

log = logging.getLogger("saint.dbus")
SERVICE = "org.saintos.Saint"
PATH = "/Saint"
LEVEL_HZ = 15                      # microphone level updates per second at most (the wallpaper animates on them)
_POINT = re.compile(r"^(-?\d{1,6}),(-?\d{1,6})$")
_PLACED = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]{0,40})\|(-?\d{1,6}),(-?\d{1,6})$")
_OVER = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]{0,40})\|([A-Za-z0-9._ -]{0,80})\|(-?\d{1,6}),(-?\d{1,6}),(\d{1,6}),(\d{1,6})$")
_RECT = re.compile(r"^(-?\d{1,6}),(-?\d{1,6}),(\d{1,6}),(\d{1,6})$")
_ACTIVE = re.compile(r"^([A-Za-z0-9._ -]{0,80})\|(-?\d{1,6}),(-?\d{1,6}),(\d{1,6}),(\d{1,6})$")


def supernova_command(where: str) -> str:
    """PlaySupernova's "x,y" (screen pixels, from the saint-shell KWin script) -> a window command, "" if malformed."""
    m = _POINT.match(str(where))
    return f"supernova:{int(m.group(1))},{int(m.group(2))}" if m else ""


def parse_placed(text: str):
    """PlacedMoved's "name|x,y" -> (name, x, y), None if malformed."""
    m = _PLACED.match(str(text))
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def parse_active(text: str):
    """ActiveWindow's "class|x,y,w,h" -> (class, x, y, w, h), None if malformed."""
    m = _ACTIVE.match(str(text))
    return (m.group(1).lower(), *(int(m.group(i)) for i in range(2, 6))) if m else None


def parse_over(text: str):
    """PlacedOver's "name|class|x,y,w,h" -> (name, class, x, y, w, h), None if malformed."""
    m = _OVER.match(str(text))
    return (m.group(1), m.group(2).lower(), *(int(m.group(i)) for i in range(3, 7))) if m else None


def parse_cursor(text: str):
    m = _POINT.match(str(text))
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_areas(text: str) -> list:
    """WorkAreas' "x,y,w,h;x,y,w,h" -> [(x, y, w, h), ...] (malformed parts dropped, at most 16)."""
    out = []
    for part in str(text).split(";")[:16]:
        m = _RECT.match(part.strip())
        if m and int(m.group(3)) > 0 and int(m.group(4)) > 0:
            out.append(tuple(int(m.group(i)) for i in range(1, 5)))
    return out


class _DesktopEvents(QObject):
    """Geometry the saint-shell KWin script reports. On Wayland SAINT can't ask where windows are; KWin tells it."""
    placed_moved = Signal(str, int, int)                 # helper window name, new top-left
    active_window = Signal(str, int, int, int, int)      # app class, x, y, width, height
    placed_over = Signal(str, str, int, int, int, int)   # helper name, app class under it, x, y, width (0: none), height
    cursor = Signal(int, int)                            # the mouse pointer
    work_areas = Signal(list)                            # [(x, y, w, h)] per monitor, panels left out


desktop_events = _DesktopEvents()


@ClassInfo({"D-Bus Interface": SERVICE})
class _Interface(QObject):
    StateChanged = Signal(str, float)

    def __init__(self, handler, state_getter):
        super().__init__()
        self._handler = handler
        self._state = state_getter

    @Slot()
    def ToggleOverlay(self):
        self._handler("toggle-overlay")

    @Slot()
    def Show(self):
        self._handler("show")

    @Slot(str)
    def OpenPage(self, name):
        self._handler(f"page:{name}")

    @Slot(result=str)
    def State(self):
        return json.dumps(self._state())

    @Slot(str)
    def PlaySupernova(self, where):
        command = supernova_command(where)
        if command:
            self._handler(command)

    @Slot(str)
    def PlacedMoved(self, text):
        p = parse_placed(text)
        if p:
            desktop_events.placed_moved.emit(*p)

    @Slot(str)
    def ActiveWindow(self, text):
        a = parse_active(text)
        if a:
            desktop_events.active_window.emit(*a)

    @Slot(str)
    def PlacedOver(self, text):
        o = parse_over(text)
        if o:
            desktop_events.placed_over.emit(*o)

    @Slot(str)
    def Cursor(self, text):
        c = parse_cursor(text)
        if c:
            desktop_events.cursor.emit(*c)

    @Slot(str)
    def WorkAreas(self, text):
        areas = parse_areas(text)
        if areas:
            desktop_events.work_areas.emit(areas)


class SaintBus:
    def __init__(self, handler, state_getter):
        self.iface = None
        self._last = ("", 0.0, 0.0)
        try:
            from PySide6.QtDBus import QDBusConnection
        except ImportError:
            return
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return
        iface = _Interface(handler, state_getter)
        if not bus.registerObject(PATH, iface, QDBusConnection.ExportAllSlots | QDBusConnection.ExportAllSignals):
            log.warning("dbus.register_object_failed %s", bus.lastError().message())
            return
        if not bus.registerService(SERVICE):
            log.warning("dbus.register_service_failed %s", bus.lastError().message())
            bus.unregisterObject(PATH)
            return
        self.iface = iface
        log.info("dbus.ready %s", SERVICE)

    @property
    def active(self) -> bool:
        return self.iface is not None

    def publish(self, state: str, level: float):
        """Send StateChanged when the state changes, and level changes at most LEVEL_HZ times a second."""
        if not self.iface:
            return
        now = time.monotonic()
        last_state, last_level, last_t = self._last
        if state == last_state and (abs(level - last_level) < 0.02 or now - last_t < 1 / LEVEL_HZ):
            return
        self._last = (state, level, now)
        self.iface.StateChanged.emit(state, float(level))
