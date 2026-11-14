"""
core/downloads.py

Everything downloading or updating on this PC right now, in one list, from deterministic sources:

    SAINT's model pulls   core.model_pull's state (Ollama)
    package operations    pacman / paru / flatpak / winget processes, and SAINT's own install queue
    browsers              partial files in Downloads (.crdownload, .part, .partial, .download), with speed from growth
    Steam                 games in steamapps/downloading
    reports               SAINT's Store (incl. Flathub progress parsed from flatpak's output) and the Visual Shop,
                          from any process, through Tracker -> small JSON files in the runtime dir

    downloads.snapshot()  -> [Item], newest information each call (speed needs two calls a few seconds apart)
    downloads.summary()   -> one sentence for SAINT ("2 things are downloading: …")
    Notifier().changes()  -> the few "started" / "finished" toasts worth showing (deduplicated, rate-limited)

Nothing here polls on its own: the Downloads page asks every 2 seconds while it's open, SAINT asks every
NOTIFY_POLL_S for the toasts and when asked.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
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
REPORT_TTL_S = 3600                     # a Tracker report this old is left over (its process is checked first)
SPEED_SMOOTHING = 0.4                   # weight of the newest speed sample (ETA would jump around otherwise)


@dataclass
class Item:
    name: str
    source: str
    done: int = 0                       # bytes, when known
    total: int = 0                      # bytes, 0 when unknown
    speed: float = 0.0                  # bytes a second, 0 when unknown
    state: str = "downloading"          # downloading | waiting | paused
    pct: Optional[int] = None           # a percentage a tool printed, when bytes aren't known (flatpak, pacman)
    eta_s: Optional[float] = None       # seconds left as a tool printed them; else worked out from speed
    key: str = ""                       # stable id across snapshots (toasts, the Downloads page)
    path: str = ""                      # the file or folder on disk, when there is one (Open / Show in folder)
    cancellable: bool = False           # SAINT's own installs stop after the current step (request_cancel)

    def __post_init__(self):
        self.key = self.key or f"{self.source}:{self.name}"

    @property
    def percent(self) -> Optional[int]:
        if self.pct is not None:
            return max(0, min(100, int(self.pct)))
        return min(100, int(100 * self.done / self.total)) if self.total else None

    @property
    def eta(self) -> Optional[float]:
        """Seconds left: what the tool said, or what's left at the current speed; None when it can't be known."""
        if self.eta_s is not None:
            return max(0.0, self.eta_s)
        if self.total and self.speed > 0 and self.state == "downloading":
            return max(0.0, (self.total - self.done) / self.speed)
        return None

    def text(self) -> str:
        parts = [self.name]
        if self.percent is not None:
            parts.append(f"{self.percent}%")
        elif self.done:
            parts.append(f"{self.done / 1e6:.0f} MB so far")
        if self.speed > 0:
            parts.append(f"{self.speed / 1e6:.1f} MB/s")
        left = fmt_eta(self.eta)
        if left:
            parts.append(left)
        if self.state != "downloading":
            parts.append(self.state)
        return " · ".join(parts)


def fmt_eta(seconds: Optional[float]) -> str:
    """'about 4 min left'; '' when unknown or a few seconds (not worth saying)."""
    if seconds is None or seconds < 5:
        return ""
    if seconds < 60:
        return "under a minute left"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"about {minutes} min left"
    h, m = divmod(minutes, 60)
    return f"about {h} h {m} min left" if m else f"about {h} h left"


_seen: Dict[str, Tuple[int, float, float]] = {}     # key -> (size, when, smoothed speed): speed between two calls
_lock = threading.Lock()


def _speed(key: str, size: int, now: float) -> float:
    """Bytes a second since the last call for ``key``, smoothed (exponential average) so the ETA doesn't jump."""
    with _lock:
        before = _seen.get(key)
        if not before or now <= before[1]:
            _seen[key] = (size, now, before[2] if before else 0.0)
            return 0.0
        raw = max(0.0, (size - before[0]) / (now - before[1]))
        smooth = raw if not before[2] else SPEED_SMOOTHING * raw + (1 - SPEED_SMOOTHING) * before[2]
        _seen[key] = (size, now, smooth)
    return smooth


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
            out.append(Item(name, "Browser", st.st_size, 0, _speed(e.path, st.st_size, now), state, path=e.path))
    return out


def finished_items(dirs: Optional[List[Path]] = None, days: float = 7, limit: int = 30,
                   now: Optional[float] = None) -> List[Item]:
    """Files that arrived in Downloads in the last ``days`` (newest first): the finished half of the list."""
    now = now or time.time()
    out = []
    for d in download_dirs() if dirs is None else dirs:
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if e.name.startswith(".") or e.name.lower().endswith(PARTIAL) or not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if now - st.st_mtime <= days * 86400:
                out.append((st.st_mtime, Item(e.name, "Finished", st.st_size, st.st_size, state="finished",
                                              key=f"finished:{e.path}", path=e.path)))
    return [i for _t, i in sorted(out, key=lambda x: -x[0])[:limit]]


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
            out.append(Item(name, "Steam", size, 0, _speed(str(game), size, now), path=str(game)))
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


# --------------------------------------------------------------------------- reports from SAINT's own installers
_PCT = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s?%")
_RATE = re.compile(r"(\d+(?:\.\d+)?)\s?([kKMGT]?i?B)/s")
_CLOCK = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])")
_UNITS = {"b": 1, "kb": 1e3, "kib": 1024, "mb": 1e6, "mib": 2 ** 20, "gb": 1e9, "gib": 2 ** 30, "tb": 1e12,
          "tib": 2 ** 40}


def parse_progress(line: str) -> Optional[Dict]:
    """A progress line from flatpak ("Installing 2/3… ████  43%  2.4 MB/s  00:12") or pacman
    ("firefox  65.2 MiB  10.1 MiB/s 00:03 [####----]  54%"): {"pct", "speed" (bytes/s), "eta_s"}; None if it isn't one."""
    m = _PCT.search(line)
    if not m:
        return None
    out = {"pct": int(float(m[1])), "speed": 0.0, "eta_s": None}
    r = _RATE.search(line)
    if r:
        out["speed"] = float(r[1]) * _UNITS.get(r[2].lower(), 1)
    c = _CLOCK.search(line)
    if c:
        out["eta_s"] = (int(c[1]) * 3600 + int(c[2]) * 60 + int(c[3])) if c[3] else int(c[1]) * 60 + int(c[2])
    return out


def report_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    d = Path(base) / f"saint-downloads-{os.getuid() if hasattr(os, 'getuid') else 'user'}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _report_path(key: str, directory: Optional[Path] = None) -> Path:
    return (directory or report_dir()) / (re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:120] + ".json")


class Tracker:
    """One download or install SAINT runs itself (the Store, Flathub, the Visual Shop), visible to every SAINT
    process: ``progress(done, total)`` for bytes, ``line(text)`` for a tool's own progress output, ``done()`` at
    the end (also on leaving a ``with`` block). Writes at most every ``every_s`` seconds."""

    def __init__(self, key: str, name: str, source: str, directory: Optional[Path] = None, every_s: float = 0.5,
                 clock: Callable[[], float] = time.time):
        self.key, self.name, self.source = key, name, source
        self.directory, self.every_s, self.clock = directory, every_s, clock
        self._last = 0.0
        self.cancel = threading.Event()        # set when someone presses Cancel (another process: a .cancel file)
        self.state: Dict = {"done": 0, "total": 0, "pct": None, "speed": 0.0, "eta_s": None, "state": "waiting"}

    def __enter__(self):
        self._write(force=True)
        return self

    def __exit__(self, *_exc):
        self.done()

    def progress(self, done: int, total: int = 0):
        self.state.update(done=int(done), total=int(total), state="downloading")
        self._write()

    def step(self):
        """A step of the plan started: no longer waiting in the queue."""
        if self.state["state"] != "downloading":
            self.state["state"] = "downloading"
            self._write(force=True)

    def line(self, text: str):
        p = parse_progress(text or "")
        if p:
            self.state.update(p, state="downloading")
            self._write()

    def _write(self, force: bool = False):
        if _cancel_path(self.key, self.directory).exists():
            self.cancel.set()
        now = self.clock()
        if not force and now - self._last < self.every_s:
            return
        if not force:                                  # the first progress after "waiting" always goes out
            self._last = now
        data = dict(self.state, key=self.key, name=self.name, source=self.source, at=now, pid=os.getpid())
        try:
            path = _report_path(self.key, self.directory)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            pass                                       # progress is a nicety: never fail an install over it

    def done(self):
        for path in (_report_path(self.key, self.directory), _cancel_path(self.key, self.directory)):
            try:
                path.unlink()
            except OSError:
                pass


def _cancel_path(key: str, directory: Optional[Path] = None) -> Path:
    return _report_path(key, directory).with_suffix(".cancel")


def request_cancel(key: str, directory: Optional[Path] = None) -> bool:
    """Ask a Tracker'd install (any SAINT process) to stop; it stops before its next step, never mid-pacman."""
    path = _report_path(key, directory)
    if not path.exists():
        return False
    try:
        _cancel_path(key, directory).write_text("cancel", encoding="utf-8")
        return True
    except OSError:
        return False


def _alive(pid) -> bool:
    """The reporting process is still running (no pid: an older report, judged by its age only)."""
    if not pid:
        return True
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:
        return True


def reported_items(directory: Optional[Path] = None, now: Optional[float] = None) -> List[Item]:
    now = now or time.time()
    out = []
    d = directory or report_dir()
    for f in sorted(d.glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if now - float(r.get("at") or 0) > REPORT_TTL_S or not _alive(r.get("pid")):
            try:
                f.unlink()                             # its process died without saying done
            except OSError:
                pass
            continue
        done, total = int(r.get("done") or 0), int(r.get("total") or 0)
        speed = float(r.get("speed") or 0.0) or (_speed(f"report:{r['key']}", done, now) if done else 0.0)
        out.append(Item(r.get("name") or r["key"], r.get("source") or "SAINT", done, total, speed,
                        r.get("state") or "downloading", r.get("pct"), r.get("eta_s"), r["key"], cancellable=True))
    return out


# --------------------------------------------------------------------------- toasts
NOTIFY_POLL_S = 15                     # SAINT looks this often for the start/finish toasts (only the cheap sources)
MIN_SEEN_S = 10                        # quicker than this isn't worth a toast either way
KEY_COOLDOWN_S = 600                   # the same download toasts at most once per 10 minutes for each kind
GLOBAL_GAP_S = 20                      # and SAINT shows at most one download toast per 20 seconds


class Notifier:
    """Turns successive snapshots into the few toasts worth showing: "started" for something still going after
    MIN_SEEN_S, "finished" when it was seen that long and is gone. Repeats and bursts are folded together."""

    def __init__(self):
        self.first_seen: Dict[str, float] = {}
        self.items: Dict[str, Item] = {}
        self.announced: Dict[Tuple[str, str], float] = {}
        self.last_toast = float("-inf")
        self.held: List[Tuple[str, Item]] = []
        self.said_start: set = set()           # keys still here whose "started" was shown: never twice in one run

    def changes(self, items: List[Item], now: Optional[float] = None) -> List[Tuple[str, str]]:
        """[(title, message)] to show now (zero or one)."""
        now = time.time() if now is None else now
        current = {i.key: i for i in items}
        for key in list(self.first_seen):
            if key not in current:
                if now - self.first_seen.pop(key) >= MIN_SEEN_S:
                    self.held.append(("finished", self.items[key]))
                self.items.pop(key, None)
                self.said_start.discard(key)
        for key, it in current.items():
            self.first_seen.setdefault(key, now)
            self.items[key] = it
            if it.state == "downloading" and key not in self.said_start and now - self.first_seen[key] >= MIN_SEEN_S                     and ("started", key) not in [(k, i.key) for k, i in self.held]:
                self.held.append(("started", it))
        fresh = []
        for kind, it in self.held:
            if now - self.announced.get((kind, it.key), -1e9) >= KEY_COOLDOWN_S:
                fresh.append((kind, it))
        self.held = fresh
        if not fresh or now - self.last_toast < GLOBAL_GAP_S:
            return []
        for kind, it in fresh:
            self.announced[(kind, it.key)] = now
            if kind == "started":
                self.said_start.add(it.key)
        self.held, self.last_toast = [], now
        done = [it.name for kind, it in fresh if kind == "finished"]
        started = [it.text() for kind, it in fresh if kind == "started"]

        def names(xs):
            return ", ".join(xs[:3]) + (f" and {len(xs) - 3} more" if len(xs) > 3 else "")
        if done and started:
            return [("Downloads", f"Finished: {names(done)}. Started: {names(started)}.")]
        if done:
            return [("Download finished" if len(done) == 1 else f"{len(done)} downloads finished", names(done))]
        return [("Downloading" if len(started) == 1 else f"{len(started)} downloads started", names(started))]


def snapshot(**sources) -> List[Item]:
    """Every source; one that fails is left out (logged), never an error for the caller."""
    import logging
    out: List[Item] = []
    for fn in SOURCES:
        if fn.__name__ in sources.get("skip", ()):
            continue
        try:
            out += fn(**sources.get(fn.__name__, {}))
        except Exception:
            logging.getLogger("saint.downloads").exception("downloads.source_failed %s", fn.__name__)
    # ponytail: while the Store reports an install, the bare "pacman/flatpak is running" rows are taken to be that
    # install (the Store's row says more); a pacman run by hand at the same moment is folded in too.
    if any(i.source in ("Flathub", "SAINT Store") for i in out):
        out = [i for i in out if not (i.source == "Packages" and i.name.endswith("installing or updating"))]
    return out


SOURCES = (model_items, reported_items, package_items, browser_items, steam_items)


def summary(items: Optional[List[Item]] = None) -> str:
    items = snapshot() if items is None else items
    active = [i for i in items if i.state == "downloading"]
    if not items:
        return "Nothing is downloading right now."
    if len(items) == 1:
        return f"One thing is downloading: {items[0].text()}."
    head = f"{len(active)} things are downloading" if len(active) != len(items) or len(active) > 1 else "One thing is downloading"
    return f"{head}: " + "; ".join(i.text() for i in items[:6]) + "."
