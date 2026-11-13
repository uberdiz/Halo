"""
core/actions/sets/halos_apps.py

HalOS's own apps for SAINT: open a folder in Files (a new tab when Files is already open), say what's downloading
(and show the Downloads page if asked), open the Task Manager on one of its pages. Plain phrases find them through
their keywords ("open my downloads folder", "what's downloading", "open task manager", "show cpu usage") with
core/actions/saint.find, no model needed; the model only picks the path or page.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..registry import SAFE, Action, ActionError, ActionResult, P

APP_ROOT = Path(__file__).resolve().parents[3]
TASKMGR_PAGES = ["Processes", "Performance", "App history", "Startup apps", "Users", "Services", "System information"]
_FOLDERS = {"home": "", "desktop": "Desktop", "documents": "Documents", "downloads": "Downloads",
            "pictures": "Pictures", "photos": "Pictures", "music": "Music", "videos": "Videos"}


def _spawn(argv):
    """Start an app detached from SAINT (tests replace this)."""
    kw = {"start_new_session": True} if os.name != "nt" else {}
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, cwd=str(APP_ROOT), **kw)


def _launcher(command: str, *fallback: str):
    """The installed launcher (/usr/bin/<command>) or, in a checkout, this Python running the module."""
    exe = shutil.which(command)
    return [exe] if exe else [sys.executable, *fallback]


def _folder(text: str) -> Path:
    """A path, or a plain name of a home folder ("downloads", "my pictures")."""
    t = (text or "").strip()
    word = t.lower().removeprefix("my ").strip()
    if word in _FOLDERS:
        return Path.home() / _FOLDERS[word]
    return Path(os.path.expandvars(os.path.expanduser(t))).absolute()


def _files_open(p):
    path = _folder(p["path"])
    if not path.exists():
        raise ActionError(f"{path} doesn't exist", "NOT_FOUND")
    _spawn(_launcher("halos-files", "-m", "ui.files_app") + [str(path)] + ([] if p["new_tab"] else ["--new-window"]))
    where = "a new tab" if p["new_tab"] else "a new window"
    return ActionResult(True, f"Opened {path.name or path} in Files ({where}).", data={"path": str(path)})


def _downloads_list(p):
    from core import downloads
    items = downloads.snapshot()
    if p["show"]:
        _spawn(_launcher("saint", str(APP_ROOT / "app.py")) + ["--page", "Downloads"])
    data = {"items": [{"name": i.name, "source": i.source, "percent": i.percent, "state": i.state,
                       "speed_bps": round(i.speed), "eta_s": None if i.eta is None else round(i.eta)}
                      for i in items]}
    return ActionResult(True, downloads.summary(items), data=data)


def _taskmgr_open(p):
    _spawn(_launcher("saint-taskmgr", "-m", "ui.taskmanager") + ["--page", p["page"]])
    return f"Opened the Task Manager on {p['page']}."


def register(registry):
    for a in [
        Action("files.open", "Open a folder in HalOS Files", _files_open,
               {"path": P("string", "folder or file path, or a home folder name like 'downloads'"),
                "new_tab": P("boolean", "a new tab in the open Files window", required=False, default=True)},
               risk=SAFE, keywords="show folder explorer file manager browse my downloads documents pictures",
               preview=lambda p: f"Open {p['path']} in Files."),
        Action("downloads.list", "What's downloading or updating", _downloads_list,
               {"show": P("boolean", "also open the Downloads page", required=False, default=False)},
               risk=SAFE, keywords="downloading download progress updating installing eta",
               preview=lambda p: "Say what's downloading."),
        Action("taskmgr.open", "Open the Task Manager", _taskmgr_open,
               {"page": P("string", "page to open", required=False, default="Processes", enum=TASKMGR_PAGES)},
               risk=SAFE, keywords="task manager processes performance cpu memory usage kill frozen app startup",
               preview=lambda p: f"Open the Task Manager on {p['page']}."),
    ]:
        registry.register(a, replace=True)
