"""
core/background_session.py

A hidden desktop where SAINT works without touching yours: apps it opens there, and the typing, clicks and key
presses it sends, happen on a virtual X display (Xvfb), so your keyboard, mouse, focus and windows are never
used. "Show me" opens a small live view of it (ui/background_view.py); otherwise nothing of it is on screen.

    bg = BackgroundDesktop()      bg.start() -> ":42"
    bg.open(["firefox", "https://example.com"])
    bg.type("hello"); bg.key("ctrl+s"); bg.click(400, 300)
    bg.screenshot() -> PIL image (for SAINT's vision, or the live view)
    bg.stop()

The same operations are OS actions (category "background", core/actions/sets/background.py), so trust, the log
and the plan panel apply. Linux only (Xvfb + xdotool are in the HalOS image).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

WIDTH, HEIGHT = 1600, 900


class BackgroundError(RuntimeError):
    pass


class BackgroundDesktop:
    def __init__(self, run: Callable = subprocess.run, popen: Callable = subprocess.Popen,
                 which: Callable[[str], Optional[str]] = shutil.which, sockets: str = "/tmp/.X11-unix"):
        self._run, self._popen, self._which, self._sockets = run, popen, which, sockets
        self.display = ""
        self._server = None
        self._apps: List[subprocess.Popen] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ lifecycle
    def free_display(self) -> str:
        for n in range(42, 100):
            if not os.path.exists(os.path.join(self._sockets, f"X{n}")) and not os.path.exists(f"/tmp/.X{n}-lock"):
                return f":{n}"
        raise BackgroundError("No free display number for the background desktop.")

    def start(self) -> str:
        with self._lock:
            if self.running:
                return self.display
            for tool in ("Xvfb", "xdotool"):
                if not self._which(tool):
                    raise BackgroundError(f"The background desktop needs {tool}, which isn't installed.")
            display = self.free_display()
            self._server = self._popen(["Xvfb", display, "-screen", "0", f"{WIDTH}x{HEIGHT}x24", "-nolisten", "tcp",
                                        "-noreset"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.display = display
        for _ in range(50):                                   # ready when its socket appears (at most ~5 s)
            if os.path.exists(os.path.join(self._sockets, f"X{display[1:]}")) or self._server.poll() is not None:
                break
            time.sleep(0.1)
        if self._server.poll() is not None:
            self.display = ""
            raise BackgroundError("The background desktop didn't start (Xvfb exited).")
        return display

    @property
    def running(self) -> bool:
        return self._server is not None and self._server.poll() is None

    def stop(self):
        for p in self._apps + ([self._server] if self._server else []):
            try:
                p.terminate()
            except OSError:
                pass
        self._apps, self._server, self.display = [], None, ""

    def env(self) -> Dict[str, str]:
        """An app's environment there: X11 only, so nothing reaches the Wayland session you're using."""
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET")}
        env.update(DISPLAY=self.display, QT_QPA_PLATFORM="xcb", GDK_BACKEND="x11", SDL_VIDEODRIVER="x11",
                   MOZ_ENABLE_WAYLAND="0", ELECTRON_OZONE_PLATFORM_HINT="x11")
        return env

    # ------------------------------------------------------------------ doing things there
    def _need(self):
        if not self.running:
            self.start()

    def _xdotool(self, *args: str, timeout: float = 20) -> str:
        self._need()
        r = self._run(["xdotool", *args], capture_output=True, text=True, timeout=timeout, env=self.env())
        if r.returncode != 0:
            raise BackgroundError(f"xdotool {args[0]} failed: {(r.stderr or '').strip()[:160]}")
        return r.stdout or ""

    def open(self, argv: List[str]) -> int:
        self._need()
        if not argv or not self._which(argv[0]):
            raise BackgroundError(f"{argv[0] if argv else 'That app'} isn't installed.")
        p = self._popen(argv, env=self.env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
        self._apps.append(p)
        return p.pid

    def windows(self) -> List[Dict]:
        out = []
        try:
            ids = self._xdotool("search", "--onlyvisible", "--name", ".").split()
        except BackgroundError:
            return []
        for wid in ids:
            try:
                out.append({"id": wid, "title": self._xdotool("getwindowname", wid).strip()})
            except BackgroundError:
                continue
        return out

    def focus(self, title: str) -> str:
        """Bring a window to the front of the background desktop (yours is untouched)."""
        for w in self.windows():
            if title.lower() in w["title"].lower():
                self._xdotool("windowactivate", "--sync", w["id"])
                return w["title"]
        raise BackgroundError(f"No window called {title} on the background desktop.")

    def type(self, text: str):
        self._xdotool("type", "--delay", "12", "--", text, timeout=max(20, len(text) * 0.05))

    def key(self, keys: str):
        self._xdotool("key", "--", *keys.split())

    def click(self, x: int, y: int, button: int = 1):
        self._xdotool("mousemove", str(int(x)), str(int(y)), "click", str(int(button)))

    def screenshot(self, path: Optional[str] = None):
        self._need()
        from PIL import ImageGrab
        img = ImageGrab.grab(xdisplay=self.display)
        if path:
            img.save(path)
        return img


_shared: Optional[BackgroundDesktop] = None


def shared() -> BackgroundDesktop:
    global _shared
    if _shared is None:
        _shared = BackgroundDesktop()
    return _shared
