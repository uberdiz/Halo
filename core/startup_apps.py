"""
core/startup_apps.py

What starts when you sign in, on Linux: XDG autostart entries (core/sysinfo.py reads them and writes the per-user
Hidden= override) plus the user systemd services that are an app's own, and adding or removing your own entries.
Nothing here starts anything or goes through a shell: a custom command becomes the Exec= line of a .desktop file,
checked first. Services are limited to SAINT's and the ones in ~/.config/systemd/user: the rest of the user's
services are the desktop's plumbing (audio, portals), not startup apps.
"""

import logging
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core import kde_desktop as kde
from core import sysinfo

log = logging.getLogger("saint.startup_apps")

INTERNAL = {"saintos-firstrun.desktop"}        # HalOS's one-time welcome isn't a startup app
OWN_SERVICES = ("saint.service", "halo-remote.service")
SHELLS = {"sh", "bash", "dash", "zsh", "fish", "ksh", "csh", "tcsh"}
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,127}\.desktop$")
_NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,64}$")
_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.@-]{0,127}\.service$")
_SHELL_SYNTAX = re.compile(r"^(\||\|\||&|&&|;|<|>|>>|2>|2>&1)$|[`\n\r]|\$\(")
_FIELD_CODE = re.compile(r'\s+"?%[fFuUdDnNickvm]"?(?=\s|$)')


def user_dir() -> str:
    return os.path.join(kde.config_home(), "autostart")


# ------------------------------------------------------------------ what's listed
def _run(argv: List[str]) -> Tuple[bool, str]:
    return kde._run(argv)


def autostart_rows(udir: Optional[str] = None, system_dirs=("/etc/xdg/autostart",)) -> List[Dict]:
    """Autostart entries the page lists. ``removable``: yours alone; a system entry can only be switched off."""
    udir = udir or user_dir()
    rows = []
    for e in sysinfo.autostart_entries(user_dir=udir, system_dirs=system_dirs):
        if e["file"] in INTERNAL:
            continue
        rows.append({**e, "kind": "autostart", "removable": e["scope"] == "user"})
    return rows


def service_rows(run: Callable = _run, unit_dir: Optional[str] = None) -> List[Dict]:
    """The services that are startup apps: SAINT's own and the user's, with enabled/disabled state."""
    ok, out = run(["systemctl", "--user", "list-unit-files", "--type=service", "--no-legend", "--no-pager"])
    if not ok:
        return []
    states = {p[0]: p[1] for p in (line.split() for line in out.splitlines()) if len(p) >= 2}
    d = unit_dir or os.path.join(kde.config_home(), "systemd", "user")
    try:
        mine = [n for n in os.listdir(d) if n.endswith(".service")]
    except OSError:
        mine = []
    rows = []
    for unit in sorted(set(OWN_SERVICES) | set(mine)):
        state = states.get(unit)
        if state in ("enabled", "disabled", "enabled-runtime") and _UNIT.match(unit):
            label = {"saint.service": "SAINT", "halo-remote.service": "Halo Remote"}.get(unit, unit[:-8])
            rows.append({"kind": "service", "file": unit, "name": label, "command": f"{unit} (systemd user service)",
                         "enabled": state != "disabled", "scope": "service", "removable": False})
    return rows


def rows(run: Callable = _run) -> List[Dict]:
    return sorted(autostart_rows() + service_rows(run), key=lambda r: r["name"].lower())


def set_enabled(row: Dict, on: bool, run: Callable = _run, udir: Optional[str] = None) -> str:
    """Turn one row on or off, for this user only. Raises ValueError/OSError when it can't."""
    if row["kind"] == "service":
        unit = row["file"]
        if not _UNIT.match(unit):
            raise ValueError(f"not a service name: {unit!r}")
        ok, out = run(["systemctl", "--user", "enable" if on else "disable", unit])
        if not ok:
            raise ValueError(out or f"systemctl couldn't change {unit}")
        return f"{row['name']} will {'start' if on else 'no longer start'} when you sign in"
    if not _FILE.match(row["file"]):
        raise ValueError(f"not an autostart file name: {row['file']!r}")
    return sysinfo.set_autostart(row, on, user_dir=udir or user_dir())


# ------------------------------------------------------------------ adding
def _escape_value(value: str) -> str:
    return value.replace("\\", "\\\\")


def _quote_arg(arg: str) -> str:
    """One Exec= argument per the Desktop Entry spec (reserved characters are quoted, % is doubled)."""
    arg = arg.replace("%", "%%")
    if re.search(r"[\s\"'\\><~|&;$*?#()`]", arg):
        return '"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"'
    return arg


def parse_command(command: str, which: Callable = shutil.which) -> List[str]:
    """A typed command -> argv. Refuses shell syntax and shells (an autostart entry never runs a shell string)
    and a program that isn't installed. Raises ValueError saying why."""
    if not command.strip() or re.search(r"[\x00-\x1f\x7f]", command):
        raise ValueError("Type a command on one line.")
    try:
        argv = shlex.split(command)
    except ValueError as e:
        raise ValueError(f"The quotes in that command don't match: {e}")
    if not argv:
        raise ValueError("Type a command.")
    for a in argv:
        if _SHELL_SYNTAX.search(a):
            raise ValueError(f"Shell syntax isn't allowed here: {a}")
    if os.path.basename(argv[0]) in SHELLS:
        raise ValueError("A shell can't be a startup app here. Point at the program itself.")
    if not which(argv[0]):
        raise ValueError(f"There's no program called {argv[0]}.")
    return argv


def _write(udir: str, filename: str, name: str, exec_line: str, icon: str = "", comment: str = "") -> Path:
    if not _FILE.match(filename):
        raise ValueError(f"not an autostart file name: {filename!r}")
    if not _NAME.match(name):
        raise ValueError("The name must be 1-64 characters on one line.")
    target = Path(udir) / filename
    if target.exists():
        raise ValueError(f"{name} is already in your startup apps.")
    lines = ["[Desktop Entry]", "Type=Application", f"Name={_escape_value(name)}", f"Exec={_escape_value(exec_line)}"]
    if icon:
        lines.append(f"Icon={_escape_value(icon)}")
    if comment:
        lines.append(f"Comment={_escape_value(comment)}")
    lines += ["Terminal=false", "X-HalOS-Added=true"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def add_command(name: str, command: str, udir: Optional[str] = None, which: Callable = shutil.which) -> Path:
    """A custom command as a startup app."""
    argv = parse_command(command, which)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "app"
    return _write(udir or user_dir(), f"halos-{slug}.desktop", name, " ".join(_quote_arg(a) for a in argv))


def add_app(app: Dict, udir: Optional[str] = None) -> Path:
    """An installed application (from installed_apps) as a startup app. Field codes mean nothing at sign-in."""
    exec_line = _FIELD_CODE.sub("", app["exec"]).strip()
    if not exec_line:
        raise ValueError(f"{app.get('name', 'That app')} has no command to start.")
    return _write(udir or user_dir(), app["file"], app["name"], exec_line, app.get("icon", ""), app.get("comment", ""))


def remove(row: Dict, udir: Optional[str] = None) -> str:
    """Remove an entry the user added. System entries and overrides of them stay: those are switched off."""
    if row.get("kind") != "autostart" or not row.get("removable"):
        raise ValueError(f"{row.get('name')} can only be switched off.")
    if not _FILE.match(row["file"]):
        raise ValueError(f"not an autostart file name: {row['file']!r}")
    (Path(udir or user_dir()) / row["file"]).unlink()
    return f"Removed {row['name']}."


# ------------------------------------------------------------------ the installed-apps picker
def application_dirs() -> List[str]:
    home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [os.path.join(d, "applications") for d in [home, *system.split(":")] if d]


def installed_apps(dirs: Optional[List[str]] = None, listdir: Callable = os.listdir,
                   read: Optional[Callable] = None) -> List[Dict]:
    """Applications a menu would show: {file, name, exec, icon, comment}. The first directory wins for one file."""
    apps: Dict[str, Dict] = {}
    hidden = set()
    for d in (dirs if dirs is not None else application_dirs()):
        try:
            names = [n for n in listdir(d) if n.endswith(".desktop")]
        except OSError:
            continue
        for n in names:
            if n in apps or n in hidden or not _FILE.match(n):
                continue
            path = os.path.join(d, n)
            f = sysinfo._desktop_entry(path, read) if read else sysinfo._desktop_entry(path)
            if not f:
                continue
            only = f.get("OnlyShowIn", "")
            if (f.get("Type", "Application") != "Application" or not f.get("Exec") or not f.get("Name")
                    or f.get("NoDisplay", "").lower() == "true" or f.get("Hidden", "").lower() == "true"
                    or (only and "KDE" not in only.split(";")) or "KDE" in f.get("NotShowIn", "").split(";")):
                hidden.add(n)
                continue
            apps[n] = {"file": n, "name": f["Name"], "exec": f["Exec"], "icon": f.get("Icon", ""),
                       "comment": f.get("Comment", "")}
    return sorted(apps.values(), key=lambda a: a["name"].lower())

