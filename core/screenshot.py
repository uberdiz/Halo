"""
core/screenshot.py

Screenshots on HalOS (Plasma, Wayland). Wayland gives apps no way to read the screen themselves (Pillow's ImageGrab
and Qt's grabWindow come back empty or black), so capture goes through the compositor's own tool:

    Spectacle (KDE, ships with HalOS)   spectacle -b -n -r|-f|-m|-a -o FILE   region select works by click-and-drag
    grim (+ slurp for a region)        on other wlroots compositors

capture(mode) saves to Pictures/Screenshots, copies the picture to the clipboard (wl-copy) and shows a notification.
The Print key itself is Spectacle's (packaging/linux/rootfs/etc/xdg/spectaclerc: Print = drag a region).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Optional

log = logging.getLogger("saint.screenshot")

MODES = {"region": "-r", "full": "-f", "screen": "-m", "window": "-a"}
WHAT = {"region": "the area you picked", "full": "all screens", "screen": "this screen", "window": "this window"}
REGION_WAIT_S = 180            # the user is dragging a rectangle; Esc cancels


class ScreenshotError(Exception):
    pass


def folder(home: Optional[Path] = None) -> Path:
    """XDG Pictures/Screenshots (where Spectacle saves too)."""
    home = Path(home or Path.home())
    pictures = home / "Pictures"
    try:
        for line in (home / ".config/user-dirs.dirs").read_text(encoding="utf-8").splitlines():
            if line.startswith("XDG_PICTURES_DIR="):
                pictures = Path(line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(home)))
    except OSError:
        pass
    return pictures / "Screenshots"


def command(mode: str, path: Path, which: Callable = shutil.which, run: Callable = subprocess.run) -> list:
    """The capture command for this desktop. Raises ScreenshotError when no tool is installed."""
    if mode not in MODES:
        raise ScreenshotError(f"Unknown screenshot mode {mode!r}.")
    if which("spectacle"):
        return ["spectacle", "-b", "-n", MODES[mode], "-o", str(path)]
    if which("grim"):
        if mode == "region":
            if not which("slurp"):
                raise ScreenshotError("Picking an area needs slurp (pacman -S slurp).")
            r = run(["slurp"], capture_output=True, text=True, timeout=REGION_WAIT_S)
            geometry = (r.stdout or "").strip()
            if r.returncode != 0 or not geometry:
                return []                     # Esc: nothing picked
            return ["grim", "-g", geometry, str(path)]
        return ["grim", str(path)]
    raise ScreenshotError("Screenshots need Spectacle (pacman -S spectacle) on Plasma, or grim on other desktops.")


def _copy(path: Path, which: Callable, run: Callable) -> bool:
    if not which("wl-copy"):
        return False
    try:
        with open(path, "rb") as f:
            return run(["wl-copy", "--type", "image/png"], stdin=f, capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        log.info("screenshot.copy_failed %s", e)
        return False


def _notify(path: Path, copied: bool, which: Callable, run: Callable) -> None:
    if not which("notify-send"):
        return
    body = f"{path.name} in {path.parent}" + (" · copied to the clipboard" if copied else "")
    try:
        run(["notify-send", "--app-name=SAINT", f"--icon={path}", "Screenshot saved", body],
            capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        log.info("screenshot.notify_failed %s", e)


def capture(mode: str = "full", path: Optional[Path] = None, which: Callable = shutil.which,
            run: Callable = subprocess.run, notify: bool = True, copy: bool = True) -> Dict:
    """Take a screenshot. {"path", "what", "copied"}; {"cancelled": True} when the user pressed Esc."""
    path = Path(path or folder() / time.strftime("Screenshot_%Y%m%d_%H%M%S.png"))
    path.parent.mkdir(parents=True, exist_ok=True)
    argv = command(mode, path, which, run)
    if not argv:
        return {"cancelled": True, "what": WHAT[mode]}
    try:
        r = run(argv, capture_output=True, text=True, timeout=REGION_WAIT_S if mode == "region" else 30)
    except subprocess.TimeoutExpired:
        raise ScreenshotError(f"{argv[0]} didn't finish the screenshot.")
    except OSError as e:
        raise ScreenshotError(f"Couldn't run {argv[0]}: {e}")
    if not path.is_file() or path.stat().st_size == 0:
        if mode == "region" and r.returncode == 0:
            return {"cancelled": True, "what": WHAT[mode]}
        why = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
        log.warning("screenshot.failed %s rc=%s %s", argv, r.returncode, why[:3])
        raise ScreenshotError(f"{argv[0]} didn't save a screenshot" + (f": {why[0][:200]}" if why else "."))
    copied = _copy(path, which, run) if copy else False
    if notify:
        _notify(path, copied, which, run)
    log.info("screenshot.saved %s mode=%s copied=%s", path, mode, copied)
    return {"path": str(path), "what": WHAT[mode], "copied": copied}


def mode_for(target: str) -> str:
    """What a spoken target means: "" -> full, "area"/"region"/"part" -> region, "this window" -> window."""
    t = (target or "").strip().lower()
    if not t or t in ("all", "everything", "both screens", "all screens", "my screen", "the screen", "screen"):
        return "full"
    if t in ("region", "area", "an area", "a region", "part", "part of the screen", "selection", "a selection",
             "an area of the screen", "a part of the screen", "a part", "rectangle", "snip"):
        return "region"
    if t in ("this", "this window", "the window", "window", "active window", "current window"):
        return "window"
    if t in ("this screen", "this monitor", "current screen"):
        return "screen"
    return ""                  # a named window or monitor: the caller decides


if __name__ == "__main__":             # python -m core.screenshot region|full|screen|window
    import sys
    print(capture(sys.argv[1] if len(sys.argv) > 1 else "region"))
