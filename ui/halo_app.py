"""
ui/halo_app.py

The Halo as its own app ("halos-halo"). On Plasma Wayland the task manager groups windows by app id, and every
window of a process shares one — so while the Halo's edge windows lived inside SAINT, a click on the SAINT taskbar
pin "activated" the invisible Halo instead of opening SAINT. Now the Halo runs in a child process with its own app
id, and the SAINT pin only ever means the SAINT app.

SAINT (the parent) keeps every decision — when the Halo shows, game mode, previews — and talks to the child over
its stdin/stdout, one JSON object per line:

    parent -> child   {"visible": bool} {"preview": ms} {"refresh": 1} {"state": {...}} {"np": {...}}
                      {"event": "<EventType value>", "payload": {...}}
    child -> parent   open | preview_ended

The child exits when SAINT does (stdin closes). If it can't start or keeps crashing, HaloProxy falls back to the
in-process Halo, so the glow never just disappears.
"""

import json
import logging
import os
import sys
import threading

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

log = logging.getLogger("saint.halo_app")
APP_ID = "halos-halo"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_RESTARTS = 3

# What the child needs to draw: state (colour), flashes, plan progress, the edge tab's text, the cover colour.
from core.events import EventType  # noqa: E402

FORWARD_EVENTS = (EventType.PLAN_STARTED, EventType.PLAN_STEP, EventType.PLAN_DONE, EventType.VOICE_HOTWORD,
                  EventType.VOICE_WAKE_WORD, EventType.TOOL_COMPLETED, EventType.AUTOMATION_TRIGGERED)


def separate_process() -> bool:
    """Only Linux needs it (Wayland app ids); off with overlay.halo_process = false."""
    from core.config import config
    return sys.platform.startswith("linux") and bool(config.get("overlay.halo_process", True))


def encode(obj: dict) -> bytes:
    return (json.dumps(obj, default=str, separators=(",", ":")) + "\n").encode("utf-8")


def make_halo(parent=None):
    """The Halo SAINT's main window uses: its own process on Linux, in-process elsewhere."""
    if separate_process():
        return HaloProxy(parent)
    from ui.halo import Halo
    return Halo(parent)


class HaloProxy(QObject):
    """Stands in for ui.halo.Halo inside SAINT; the real one draws in the child process."""
    open_requested = Signal()
    preview_ended = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.events import EventType
        from ui.reactive import ui_bus
        self._bus, self._ET = ui_bus, EventType
        self._visible = False
        self.previewing = False
        self._buf = b""
        self._restarts = 0
        self._local = None                    # the in-process Halo after the child gave up
        self._proc = None
        self._stopping = False
        self._start()
        ui_bus.event.connect(self._forward)

    # -- child process ------------------------------------------------------------------------------------- #
    def _start(self):
        p = QProcess(self)
        p.setProgram(sys.executable)
        p.setArguments(["-m", "ui.halo_app"])
        p.setWorkingDirectory(ROOT)
        p.setProcessChannelMode(QProcess.ForwardedErrorChannel)
        p.readyReadStandardOutput.connect(self._read)
        p.finished.connect(self._died)
        p.errorOccurred.connect(lambda e: log.warning("halo_app.error %s", e))
        self._proc = p
        p.start()
        if not p.waitForStarted(3000):
            log.warning("halo_app.start_failed")
            self._fallback()
            return
        self._send({"state": dict(self._bus.state)})
        self._send({"np": self._bus.now_playing()})
        if self._visible:
            self._send({"visible": True})

    def _send(self, obj: dict):
        if self._local is None and self._proc is not None and self._proc.state() == QProcess.Running:
            self._proc.write(encode(obj))

    def _read(self):
        self._buf += bytes(self._proc.readAllStandardOutput())
        *lines, self._buf = self._buf.split(b"\n")
        for line in lines:
            msg = line.strip().decode("utf-8", "replace")
            if msg == "open":
                self.open_requested.emit()
            elif msg == "preview_ended":
                self.previewing = False
                self.preview_ended.emit()

    def _died(self, code, _status):
        if self._stopping or self._local is not None:
            return
        self._restarts += 1
        log.warning("halo_app.exited code=%s restart=%s", code, self._restarts)
        if self._restarts > MAX_RESTARTS:
            self._fallback()
        else:
            QTimer.singleShot(1000 * self._restarts, self._start)

    def _fallback(self):
        from ui.halo import Halo
        log.warning("halo_app.fallback_in_process")
        self._local = Halo(self)
        self._local.open_requested.connect(self.open_requested)
        self._local.preview_ended.connect(self._local_preview_ended)
        if self._visible:
            self._local.set_visible(True)

    def _local_preview_ended(self):
        self.previewing = False
        self.preview_ended.emit()

    def _forward(self, ev):
        t = ev.type
        if t == self._ET.ASSISTANT_STATE:
            self._send({"state": dict(ev.payload or {})})
        elif t in (self._ET.SPOTIFY_PLAYBACK_CHANGED, self._ET.MEDIA_CHANGED):
            self._send({"np": self._bus.now_playing()})
        elif t in FORWARD_EVENTS:
            self._send({"event": t, "payload": ev.payload or {}})

    # -- the Halo interface main_window uses --------------------------------------------------------------- #
    @property
    def visible(self):
        return self._visible

    def set_visible(self, on: bool):
        on = bool(on)
        if self._local is not None:
            self._local.set_visible(on)
            self._visible = self._local.visible
            return
        if on != self._visible:
            self._visible = on
            self._send({"visible": on})

    def preview(self, ms: int = 3200):
        self.previewing = True
        if self._local is not None:
            self._local.preview(ms)
        else:
            self._visible = True
            self._send({"preview": int(ms)})

    def refresh(self):
        if self._local is not None:
            self._local.refresh()
        else:
            self._send({"refresh": 1})

    def shutdown(self):
        self._stopping = True
        if self._local is not None:
            self._local.shutdown()
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            self._proc.closeWriteChannel()             # the child quits on EOF
            if not self._proc.waitForFinished(1500):
                self._proc.kill()


# ------------------------------------------------------------------------------------------------------------ #
class HaloChild(QObject):
    """Runs in the halos-halo process: applies SAINT's messages to a real ui.halo.Halo."""
    line = Signal(str)
    eof = Signal()                                 # emitted from the stdin thread: queued onto the Qt thread

    def __init__(self, halo, bus, out=None):
        super().__init__()
        self.halo, self.bus = halo, bus
        self.out = out or sys.stdout
        self.np = {}
        bus.now_playing = lambda: self.np          # this process has no media pollers: SAINT tells us
        halo.open_requested.connect(lambda: self._say("open"))
        halo.preview_ended.connect(self._preview_ended)
        self.line.connect(self.handle)

    def _say(self, word: str):
        try:
            self.out.write(word + "\n")
            self.out.flush()
        except (OSError, ValueError):
            pass

    def _preview_ended(self):
        self._say("preview_ended")
        if not self._wanted:
            self.halo.set_visible(False)

    _wanted = False

    def handle(self, text: str):
        from core.events import Event
        try:
            msg = json.loads(text)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        if "state" in msg and isinstance(msg["state"], dict):
            self.bus.state = msg["state"]
            self.bus.event.emit(Event(EventType.ASSISTANT_STATE, msg["state"]))
        if "np" in msg and isinstance(msg["np"], dict):
            self.np = msg["np"]
        if "event" in msg:
            self.bus.event.emit(Event(str(msg["event"]), msg.get("payload") or {}))
        if "visible" in msg:
            self._wanted = bool(msg["visible"])
            if not self.halo.previewing:
                self.halo.set_visible(self._wanted)
        if "preview" in msg:
            self.halo.preview(int(msg["preview"]))
        if "refresh" in msg:
            from core.config import config
            config.reload()
            self.halo.refresh()


def _stdin_reader(child: HaloChild):
    for raw in sys.stdin:
        child.line.emit(raw.strip())
    child.eof.emit()                               # SAINT is gone


def main() -> int:
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setDesktopFileName(APP_ID)                 # its own Wayland app id: never grouped with the SAINT pin
    app.setQuitOnLastWindowClosed(False)
    from ui.halo import Halo
    from ui.reactive import ui_bus
    child = HaloChild(Halo(), ui_bus)
    child.eof.connect(app.quit)
    threading.Thread(target=_stdin_reader, args=(child,), daemon=True).start()
    rc = app.exec()
    child.halo.shutdown()
    return rc


if __name__ == "__main__":
    sys.exit(main())
