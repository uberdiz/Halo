"""
core/downloads.py

Everything downloading or updating on this PC right now, in one list, from deterministic sources:

    SAINT's model pulls   core.model_pull's state (Ollama)
    package operations    pacman / paru / flatpak / winget processes, and SAINT's own install queue
    browsers              partial files in Downloads (.crdownload, .part, .partial, .download), with speed from growth
    Steam                 games in steamapps/downloading

    downloads.snapshot()  -> [Item], newest information each call (speed needs two calls a few seconds apart)
    downloads.summary()   -> one sentence for SAINT ("2 things are downloading: …")

Nothing here polls on its own: the Downloads page asks every 2 seconds while it's open, SAINT asks when asked.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

PARTIAL = (".crdownload", ".part", ".partial", ".download", ".opdownload")
PACKAGE_TOOLS = {"pacman": "Arch packages", "paru": "AUR packages", "yay": "AUR packages", "flatpak": "Flatpak",
                 "pamac": "Packages", "winget.exe": "Windows apps (winget)", "winget": "Windows apps (winget)",
                 "ollama": None}            # ollama pulls come from model_pull, not the process list
STALE_S = 120                           # a partial file untouched this long is a stopped download, not an active one


@dataclass
class Item:
    name: str
    source: str
    done: int = 0                       # bytes, when known
    total: int = 0                      # bytes, 0 when unknown
    speed: float = 0.0                  # bytes a second, 0 when unknown
    state: str = "downloading"          # downloading | waiting | paused

    @property
    def percent(self) -> Optional[int]:
        return int(100 * self.done / self.total) if self.total else None

    def text(self) -> str:
        parts = [self.name]
        if self.percent is not None:
            parts.append(f"{self.percent}%")
        elif self.done:
            parts.append(f"{self.done / 1e6:.0f} MB so far")
        if self.speed > 0:
            parts.append(f"{self.speed / 1e6:.1f} MB/s")
        if self.state != "downloading":
            parts.append(self.state)
        return " · ".join(parts)


_seen: Dict[str, Tuple[int, float]] = {}            # path -> (size, when): for speed between two calls
_lock = threading.Lock()


def _speed(key: str, size: int, now: float) -> float:
    with _lock:
        before = _seen.get(key)
        _seen[key] = (size, now)
    if not before or now <= before[1]:
        return 0.0
    return max(0.0, (size - before[0]) / (now - before[1]))


def download_dirs() -> List[Path]:
    home = Path.home()
    dirs = [home / "Downloads"]
    xdg = home / ".config/user-dirs.dirs"
    try:
        for line in xdg.read_text(encoding="utf-8").splitlines():
            if line.startswith("XDG_DOWNLOAD_DIR="):
                dirs.insert(0, Path(line.split("=", 1)[1].strip('"').replace("$HOME", str(home))))
    except OSError:
        pass
    return [d for d in dict.fromkeys(dirs) if d.is_dir()]


def browser_items(dirs: Optional[List[Path]] = None, now: Optional[float] = None) -> List[Item]:
    now = now or time.time()
    out = []
    for d in download_dirs() if dirs is None else dirs:
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            if not e.is_file() or not e.name.lower().endswith(PARTIAL):
                continue
            st = e.stat()
            name = e.name[:e.name.lower().rfind(".")]
            state = "downloading" if now - st.st_mtime < STALE_S else "paused"
            out.append(Item(name, "Browser", st.st_size, 0, _speed(e.path, st.st_size, now), state))
    return out


def steam_items(roots: Optional[List[Path]] = None, now: Optional[float] = None) -> List[Item]:
    now = now or time.time()
    roots = roots if roots is not None else [Path.home() / ".local/share/Steam", Path.home() / ".steam/steam",
                                             Path("C:/Program Files (x86)/Steam")]
    out = []
    for root in roots:
        dl = root / "steamapps/downloading"
        if not dl.is_dir():
            continue
        for game in dl.iterdir():
            if not game.is_dir():
                continue
            size = sum(f.stat().st_size for f in game.rglob("*") if f.is_file())
            name = _steam_name(root, game.name) or f"Steam app {game.name}"
            out.append(Item(name, "Steam", size, 0, _speed(str(game), size, now)))
    return out


def _steam_name(root: Path, appid: str) -> str:
    try:
        text = (root / f"steamapps/appmanifest_{appid}.acf").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    for line in text.splitlines():
        parts = line.strip().split('"')
        if len(parts) >= 4 and parts[1] == "name":
            return parts[3]
    return ""


def package_items(processes: Optional[Callable[[], List[str]]] = None, queued: Optional[Callable[[], int]] = None) -> List[Item]:
    names = (processes or _process_names)()
    out, seen = [], set()
    for n in names:
        label = PACKAGE_TOOLS.get(n.lower())
        if label and label not in seen:
            seen.add(label)
            out.append(Item(f"{label}: installing or updating", "Packages"))
    try:
        from core import pkg_queue
        waiting = (queued or pkg_queue.waiting)()
    except Exception:
        waiting = 0
    if waiting > 1:
        out.append(Item(f"{waiting - 1} more app installs queued", "SAINT Store", state="waiting"))
    return out


def _process_names() -> List[str]:
    try:
        import psutil
        return [p.info.get("name") or "" for p in psutil.process_iter(["name"])]
    except Exception:
        return []


def model_items(state: Optional[Callable[[], Dict]] = None) -> List[Item]:
    from core import model_pull
    s = (state or model_pull.state)()
    if not s.get("running"):
        return []
    return [Item(f"AI model {s['model']}", "SAINT", int(s.get("completed") or 0), int(s.get("total") or 0))]


def snapshot(**sources) -> List[Item]:
    """Every source; one that fails is left out (logged), never an error for the caller."""
    import logging
    out: List[Item] = []
    for fn in (model_items, package_items, browser_items, steam_items):
        try:
            out += fn(**sources.get(fn.__name__, {}))
        except Exception:
            logging.getLogger("saint.downloads").exception("downloads.source_failed %s", fn.__name__)
    return out


def summary(items: Optional[List[Item]] = None) -> str:
    items = snapshot() if items is None else items
    active = [i for i in items if i.state == "downloading"]
    if not items:
        return "Nothing is downloading right now."
    if len(items) == 1:
        return f"One thing is downloading: {items[0].text()}."
    head = f"{len(active)} things are downloading" if len(active) != len(items) or len(active) > 1 else "One thing is downloading"
    return f"{head}: " + "; ".join(i.text() for i in items[:6]) + "."
