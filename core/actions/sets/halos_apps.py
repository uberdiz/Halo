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

from ..registry import RISKY, SAFE, Action, ActionError, ActionResult, P

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


def _passwords_find(p):
    """Site and username only: the password never leaves core/passwords (SAINT may read this to a model)."""
    from core import passwords
    try:
        hits = passwords.vault().find(p["query"])
    except RuntimeError as e:
        raise ActionError(str(e), "UNAVAILABLE")
    data = {"items": [e.public() for e in hits[:10]]}
    if not hits:
        return ActionResult(True, f"No saved login matches {p['query']!r}.", data=data)
    names = ", ".join(f"{e.username or '(no username)'} on {e.site}" for e in hits[:5])
    return ActionResult(True, f"Found {len(hits)}: {names}.", data=data)


def _passwords_pick(p):
    from core import passwords
    try:
        hits = passwords.vault().find(p["query"])
    except RuntimeError as e:
        raise ActionError(str(e), "UNAVAILABLE")
    if p.get("username"):
        hits = [e for e in hits if e.username.casefold() == p["username"].casefold()]
    if not hits:
        raise ActionError(f"No saved login matches {p['query']!r}.", "NOT_FOUND")
    if len({e.key for e in hits}) > 1:
        raise ActionError("More than one login matches: " + ", ".join(f"{e.username} on {e.site}" for e in hits[:5])
                          + ". Say which username.", "AMBIGUOUS")
    return hits[0]


def _passwords_fill(p):
    """Types username, Tab, password into the window in front (modules/desktop/controller.type_text)."""
    e = _passwords_pick(p)
    from modules.desktop.controller import desktop
    try:
        desktop.type_text(f"{e.username}\t{e.password}" if e.username else e.password)
    except Exception as err:            # ToolError: keyboard control off, focus blocked, game mode...
        raise ActionError(str(err) or type(err).__name__, getattr(err, "code", None) or "FAILED")
    return ActionResult(True, f"Filled in {e.username or 'the password'} for {e.site}.", data=e.public())


def _passwords_import(p):
    from core import passwords
    path = Path(os.path.expanduser(p["path"]))
    if not path.is_file():
        raise ActionError(f"{path} doesn't exist", "NOT_FOUND")
    try:
        c = passwords.vault().import_csv(path)
    except (ValueError, RuntimeError) as e:
        raise ActionError(str(e), "FAILED")
    return ActionResult(True, f"Imported {path.name}: {c['added']} added, {c['updated']} updated, "
                              f"{c['unchanged']} unchanged, {c['kept']} kept. You can delete the CSV now.", data=c)


def _passwords_open(p):
    _spawn(_launcher("halos-passwords", "-m", "ui.passwords_app") + ([p["query"]] if p["query"] else []))
    return "Opened Passwords."


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
        Action("passwords.find", "Find a saved login (site and username, never the password)", _passwords_find,
               {"query": P("string", "site, app or username to look for")},
               risk=SAFE, keywords="password passwords login logins account username saved keychain",
               preview=lambda p: f"Look for a saved login for {p['query']}."),
        Action("passwords.fill", "Fill in a saved login in the window in front", _passwords_fill,
               {"query": P("string", "site or app of the login"),
                "username": P("string", "which username, when there are several", required=False, default="")},
               risk=RISKY, keywords="password fill autofill sign in log in type my password",
               preview=lambda p: f"Type the saved login for {p['query']} into the window in front."),
        Action("passwords.import", "Import a password export (Apple, Chrome, Firefox, Bitwarden CSV)",
               _passwords_import, {"path": P("string", "path of the CSV export")},
               risk=SAFE, keywords="password passwords import export csv apple icloud keychain chrome firefox bitwarden",
               preview=lambda p: f"Import passwords from {p['path']}."),
        Action("passwords.open", "Open HalOS Passwords", _passwords_open,
               {"query": P("string", "search to start with", required=False, default="")},
               risk=SAFE, keywords="password passwords manager vault keychain logins open",
               preview=lambda p: "Open Passwords."),
    ]:
        registry.register(a, replace=True)
