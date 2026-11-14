"""
core/pkg_queue.py

One queue for everything that installs, updates or removes packages, so "pacman is busy" never reaches the user.

    run_plan(steps, on_wait=...)    core.saintos_apps.run_plan, queued: waits its turn, waits for pacman, retries

Two things are waited for, both with a line the UI can show ("Waiting for another install to finish…"):

    a turn          one package operation at a time across every SAINT process (the Store, SAINT, Settings, the
                    migration wizard). A turn is a ticket file in the user's runtime directory: the oldest ticket
                    whose process is alive goes first; a crashed process's ticket is dropped.
    pacman's lock   /var/lib/pacman/db.lck, held by whatever else is using pacman (the first-boot provisioner, a
                    terminal, pamac). Only steps that use pacman or an AUR helper wait for it; Flatpak, npm and
                    Wine steps keep their place in the queue but run while pacman is busy.

A lock with no pacman, pamac, paru or yay process behind it is stale (a crash, a power cut). After it has stayed
stale for ``STALE_AFTER`` seconds it is removed, only if it's still the same file and still nobody is running;
that asks for the password like any admin step. If it can't be removed the step fails saying exactly that.

A step that still loses the race for the lock ("unable to lock database") is waited for and run again.
"""

from __future__ import annotations

import itertools
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

log = logging.getLogger("saint.pkg_queue")

PACMAN_LOCK = "/var/lib/pacman/db.lck"
PKG_TOOLS = ("pacman", "pamac", "pamac-daemon", "paru", "yay", "pacman-key")   # who may hold the lock
_LOCKERS = {"pacman", "paru", "yay", "pamac"}                                   # steps that need the lock
LOCK_ERROR = re.compile(r"unable to lock database|db\.lck|could not lock database", re.I)
WAITING = "Waiting for another install to finish…"
STALE_AFTER = 20.0          # seconds a lock must stay ownerless before it's removed
POLL = 1.0
RETRIES = 3

_seq = itertools.count()
_local = threading.local()


class QueueError(RuntimeError):
    """The operation couldn't get its turn (cancelled, or a leftover lock that couldn't be cleared)."""


def wait_text(position: int = 0) -> str:
    """What the UI shows while waiting; ``position`` is how many operations are ahead of this one."""
    if position <= 0:
        return WAITING
    return f"{WAITING} ({position} ahead of this one)"


def needs_pacman(argv: List[str]) -> bool:
    """Does this command take pacman's lock? (pacman itself, through pkexec/sudo, or an AUR helper)"""
    return any(os.path.basename(a) in _LOCKERS for a in argv[:3])


# ---------------------------------------------------------------- pacman's lock

def package_processes() -> List[str]:
    """Names of the running programs that can hold pacman's lock."""
    try:
        import psutil
        return sorted({n for p in psutil.process_iter(["name"]) if (n := p.info.get("name") or "") in PKG_TOOLS})
    except Exception:
        return []


def lock_state(exists: Callable[[str], bool] = os.path.exists,
               procs: Callable[[], List[str]] = package_processes, lock: str = PACMAN_LOCK) -> str:
    """"free", "held" (someone is using pacman) or "stale" (the lock is there but nobody is)."""
    if not exists(lock):
        return "free"
    return "held" if procs() else "stale"


def _mtime(path: str) -> float:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def _remove_lock(lock: str, run: Callable = subprocess.run) -> bool:
    try:
        os.remove(lock)                               # root (the provisioner), or a test's own file
        return True
    except FileNotFoundError:
        return True
    except OSError:
        pass
    try:
        return run(["pkexec", "rm", "-f", "--", lock], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def clear_stale_lock(exists: Callable[[str], bool] = os.path.exists,
                     procs: Callable[[], List[str]] = package_processes, remove: Callable[[str], bool] = _remove_lock,
                     mtime: Callable[[str], float] = _mtime, seen_mtime: Optional[float] = None,
                     lock: str = PACMAN_LOCK) -> bool:
    """Remove a leftover lock. Checked again right before: it must still be there, still ownerless, and (when
    ``seen_mtime`` is given) the same lock that was seen going stale. True when the lock is gone."""
    if not exists(lock):
        return True
    if procs() or (seen_mtime is not None and mtime(lock) != seen_mtime):
        return False                                  # somebody took it meanwhile: it isn't stale any more
    log.warning("pkg_queue.clearing_stale_lock %s", lock)
    return bool(remove(lock)) and not exists(lock)


def wait_for_pacman(on_wait: Optional[Callable[[str], None]] = None, cancel: Optional[threading.Event] = None,
                    exists: Callable[[str], bool] = os.path.exists,
                    procs: Callable[[], List[str]] = package_processes,
                    remove: Callable[[str], bool] = _remove_lock, mtime: Callable[[str], float] = _mtime,
                    sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                    stale_after: float = STALE_AFTER, poll: float = POLL, lock: str = PACMAN_LOCK) -> float:
    """Return once pacman's lock is free; the seconds waited. Raises QueueError when cancelled or when a stale
    lock can't be removed."""
    began = clock()
    stale_since: Optional[float] = None
    stale_mtime = 0.0
    said = ""
    while True:
        state = lock_state(exists, procs, lock)
        if state == "free":
            return clock() - began
        if cancel is not None and cancel.is_set():
            raise QueueError("Cancelled while waiting for another install to finish.")
        if state == "held":
            stale_since, text = None, WAITING
        else:
            now, seen = clock(), mtime(lock)
            if stale_since is None or seen != stale_mtime:
                stale_since, stale_mtime = now, seen
            text = "Checking a leftover lock from an interrupted install…"
            if now - stale_since >= stale_after:
                if clear_stale_lock(exists, procs, remove, mtime, stale_mtime, lock):
                    continue
                if lock_state(exists, procs, lock) == "stale":
                    raise QueueError("An interrupted install left the package database locked and SAINT couldn't "
                                     "clear it (the password prompt was cancelled). Restarting the PC clears it.")
                stale_since = None
        if on_wait and text != said:
            on_wait(text)
            said = text
        sleep(poll)


# ---------------------------------------------------------------- turns

def queue_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    return Path(base) / f"saint-pkg-queue-{re.sub(r'[^A-Za-z0-9_.-]', '_', user)}"


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return True


class Turn:
    """``with Turn(on_wait):`` returns when every earlier package operation (of any SAINT process) has finished.
    Re-entering on the same thread is free, so a queued job may call queued helpers."""

    def __init__(self, on_wait: Optional[Callable[[str], None]] = None, cancel: Optional[threading.Event] = None,
                 directory: Optional[Path] = None, pid_alive: Callable[[int], bool] = _pid_alive,
                 sleep: Callable[[float], None] = time.sleep, poll: float = 0.5, pid: Optional[int] = None):
        self.on_wait, self.cancel = on_wait, cancel
        self.dir = Path(directory) if directory else queue_dir()
        self.pid_alive, self.sleep, self.poll = pid_alive, sleep, poll
        self.pid = os.getpid() if pid is None else pid
        self.ticket: Optional[Path] = None
        self._nested = False

    def take_ticket(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ticket = self.dir / f"{time.time_ns():020d}-{next(_seq):06d}-{self.pid}.ticket"
        self.ticket.write_text("")
        return self.ticket

    def position(self) -> int:
        """How many live operations are ahead of this one (0: it's this one's turn)."""
        ahead = 0
        for name in sorted(os.listdir(self.dir)):
            if not name.endswith(".ticket"):
                continue
            if name == self.ticket.name:
                return ahead
            try:
                pid = int(name[:-7].rsplit("-", 1)[1])
            except (ValueError, IndexError):
                continue
            if pid == self.pid or self.pid_alive(pid):
                ahead += 1
            else:                                     # its process died without finishing: drop it
                try:
                    os.remove(self.dir / name)
                except OSError:
                    pass
        return ahead

    def __enter__(self) -> "Turn":
        if getattr(_local, "depth", 0):
            _local.depth += 1
            self._nested = True
            return self
        self.take_ticket()
        said = -1
        try:
            while (ahead := self.position()) > 0:
                if self.cancel is not None and self.cancel.is_set():
                    raise QueueError("Cancelled while waiting for another install to finish.")
                if self.on_wait and ahead != said:
                    self.on_wait(wait_text(ahead))
                    said = ahead
                self.sleep(self.poll)
        except BaseException:
            self._drop()
            raise
        _local.depth = 1
        return self

    def _drop(self):
        if self.ticket is not None:
            try:
                os.remove(self.ticket)
            except OSError:
                pass
            self.ticket = None

    def __exit__(self, *exc):
        _local.depth = max(0, getattr(_local, "depth", 1) - 1)
        if not self._nested:
            self._drop()
        return False


def waiting(directory: Optional[Path] = None, pid_alive: Callable[[int], bool] = _pid_alive) -> int:
    """How many package operations are queued or running right now (for the downloads tray)."""
    d = Path(directory) if directory else queue_dir()
    n = 0
    try:
        names = os.listdir(d)
    except OSError:
        return 0
    for name in names:
        try:
            n += name.endswith(".ticket") and pid_alive(int(name[:-7].rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            pass
    return n


# ---------------------------------------------------------------- the gate core.saintos_apps.run_plan uses

class Gate:
    """What run_plan asks before and after each step: wait for pacman if the step needs it, and whether a step
    that lost the race for the lock should run again."""

    def __init__(self, on_wait: Optional[Callable[[str], None]] = None, cancel: Optional[threading.Event] = None,
                 wait: Callable = wait_for_pacman, retries: int = RETRIES):
        self.on_wait, self.cancel, self.wait, self.retries = on_wait, cancel, wait, retries

    def before(self, step) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise QueueError("Cancelled.")           # between steps only: never in the middle of pacman
        if needs_pacman(step.argv):
            self.wait(self.on_wait, self.cancel)

    def retry(self, step, lines: List[str], attempt: int) -> bool:
        if attempt >= self.retries or not needs_pacman(step.argv) or not LOCK_ERROR.search("\n".join(lines[-40:])):
            return False
        if self.on_wait:
            self.on_wait(WAITING)
        self.wait(self.on_wait, self.cancel)
        return True


def run_plan(steps, on_wait: Optional[Callable[[str], None]] = None, cancel: Optional[threading.Event] = None,
             gate: Optional[Gate] = None, turn: Optional[Turn] = None, **kw) -> Dict[str, bool]:
    """core.saintos_apps.run_plan through the queue. ``on_wait(text)`` gets the waiting line; the other arguments
    are run_plan's (on_line, on_step, errors, popen, live)."""
    from core import saintos_apps as sa
    with (turn or Turn(on_wait, cancel)):
        return sa.run_plan(steps, gate=gate or Gate(on_wait, cancel), **kw)


def run_queued(fn: Callable[[], object], on_wait: Optional[Callable[[str], None]] = None,
               cancel: Optional[threading.Event] = None, pacman: bool = False):
    """Run any package operation that isn't a plan (a model's package, a repair) in its turn."""
    with Turn(on_wait, cancel):
        if pacman:
            wait_for_pacman(on_wait, cancel)
        return fn()
