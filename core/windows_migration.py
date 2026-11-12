"""
core/windows_migration.py

Moving in from Windows (or an earlier Linux), for the "Migrate from Windows" settings page. Each step is separate:

    detect_installs / pick_main       every Windows on every volume; the most recently used is suggested as main
    plan_folders / run_files          Documents, Downloads... linked into the home folder (default) or copied
    import_bookmarks, import_wallpaper, import_vscode, steam_libraries, windows_values
    collect_app_names / match_apps    what was installed there, matched to the Store; the rest can use Wine
    build_removal / execute_removal   the last step, for an install that isn't the main one

Rules the code enforces: never saved passwords, cookies or Wi-Fi keys; never through a symlink or junction; never
outside the exact top-level names in REMOVABLE_*; never a partition table, EFI or Recovery partition. Everything
is logged to <data dir>/windows_migration.log.
"""

import configparser
import html
import json
import logging
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Optional

from core import drives
from core.drives import ci_child, is_link, real_dir
from core.paths import PROJECT_ROOT, data_path

log = logging.getLogger("saint.migration")

FOLDERS = ("Documents", "Downloads", "Pictures", "Music", "Videos", "Desktop")
SKIP_NAMES = {"appdata", "desktop.ini", "thumbs.db", "ntuser.dat", "application data", "local settings"}
NOT_PEOPLE = {"public", "default", "default user", "all users", "defaultuser0", "wdagutilityaccount"}
REMOVABLE_DIRS = ("Windows", "Program Files", "Program Files (x86)", "ProgramData", "$Recycle.Bin", "Windows.old",
                  "$WINDOWS.~BT", "$WINDOWS.~WS", "$WinREAgent", "PerfLogs")
REMOVABLE_FILES = ("pagefile.sys", "hiberfil.sys", "swapfile.sys", "DumpStack.log", "DumpStack.log.tmp")
USERS_DIR = "Users"
BROWSERS = {"Chrome": ("AppData", "Local", "Google", "Chrome", "User Data"),
            "Edge": ("AppData", "Local", "Microsoft", "Edge", "User Data"),
            "Brave": ("AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data")}
SETTINGS_NOTICE = ("Windows' Settings app can't run on Linux, so nothing here pretends to be it. "
                   "These are the values read from your Windows and what HalOS did with them.")
LOG_NAME = "windows_migration.log"
STATE_NAME = "windows_migration.json"
_lock = threading.Lock()


def _log(message: str) -> None:
    log.info(message)
    try:
        with _lock, open(data_path(LOG_NAME), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def _load_state() -> Dict:
    try:
        return json.loads(Path(data_path(STATE_NAME)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: Dict) -> None:
    path = Path(data_path(STATE_NAME))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def should_offer() -> bool:
    """The Welcome page's one-time button."""
    return os.name != "nt" and not drives.is_live() and not _load_state().get("offered")


def mark_offered() -> None:
    state = _load_state()
    state["offered"] = True
    _save_state(state)


def _record_migration(uuid: str, what: str) -> None:
    state = _load_state()
    state.setdefault("migrated", {}).setdefault(uuid or "?", {})[what] = time.time()
    _save_state(state)


def migration_ran(uuid: str) -> bool:
    return bool(_load_state().get("migrated", {}).get(uuid or "?", {}).get("files"))


# ---------------------------------------------------------------------- detection
@dataclass
class WindowsInstall:
    root: Path
    device: str = ""
    label: str = ""
    uuid: str = ""
    partuuid: str = ""
    parttype: str = ""
    size: int = 0
    used: int = 0
    users: List[str] = field(default_factory=list)
    last_used: float = 0.0
    kind: str = "windows"

    @property
    def name(self) -> str:
        return self.label or Path(self.device).name or str(self.root)


def _mtime(path: Optional[Path]) -> float:
    try:
        return os.lstat(path).st_mtime if path is not None else 0.0
    except OSError:
        return 0.0


def _ci_path(root, *parts) -> Optional[Path]:
    """root/parts... ignoring case. None when missing or when any step is a symlink or junction."""
    cur = Path(root)
    for p in parts:
        cur = ci_child(cur, p)
        if cur is None or is_link(cur):
            return None
    return cur


def windows_users(root) -> List[str]:
    users_dir = _ci_path(root, USERS_DIR)
    if users_dir is None:
        return []
    out = []
    try:
        with os.scandir(users_dir) as it:
            for e in it:
                if e.name.lower() not in NOT_PEOPLE and real_dir(e.path) and ci_child(e.path, "NTUSER.DAT"):
                    out.append(e.name)
    except OSError:
        return []
    return sorted(out)


def probe_root(root, vol: Optional[drives.Volume] = None) -> Optional[WindowsInstall]:
    if not drives.is_windows_root(root):
        return None
    users = windows_users(root)
    stamps = [_mtime(_ci_path(root, "Windows", "System32", "config", "SOFTWARE"))]
    stamps += [_mtime(_ci_path(root, USERS_DIR, u, "NTUSER.DAT")) for u in users]
    v = vol or drives.Volume(device="")
    return WindowsInstall(Path(root), v.device, v.label, v.uuid, v.partuuid, v.parttype, v.size, v.used, users, max(stamps))


EXPORT_DIR = "HalOS-Export"
EXPORT_MARK = "HALOS-EXPORT.json"


def probe_export(folder, vol: Optional[drives.Volume] = None) -> Optional[WindowsInstall]:
    """A folder written by export_for_halos.ps1 (Windows) or export_for_halos.sh (macOS): laid out like a Windows
    profile, so every importer here reads it like a Windows disk. None when it isn't one."""
    mark = ci_child(folder, EXPORT_MARK) if folder and real_dir(folder) else None
    if mark is None or is_link(mark):
        return None
    try:
        info = json.loads(Path(mark).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    users = [u for u in ([info.get("user")] if info.get("user") else []) if real_dir(_ci_path(folder, USERS_DIR, u))]
    v = vol or drives.Volume(device="")
    label = f"Export from {info.get('computer') or 'another PC'}"
    return WindowsInstall(Path(folder), v.device, label, v.uuid, v.partuuid, v.parttype, v.size, v.used, users,
                          _mtime(Path(mark)))


def find_exports(volumes: List[drives.Volume]) -> List[WindowsInstall]:
    """HalOS-Export folders at the top of any mounted drive (a USB stick, another disk)."""
    out = []
    for v in volumes:
        if v.mountpoint:
            found = probe_export(ci_child(v.mountpoint, EXPORT_DIR), v)
            if found:
                out.append(found)
    return out


def detect_installs(volumes: Optional[List[drives.Volume]] = None, run: Callable = subprocess.run) -> Dict:
    """Every Windows on every volume, mounting unmounted NTFS read-only to look. {"installs": [...], "locked": [...]}."""
    vols = volumes if volumes is not None else drives.volumes(run)
    installs, locked = [], []
    for v in vols:
        if v.locked:
            locked.append(v)
            continue
        if not v.is_ntfs or v.protected:
            continue
        path, peeked = v.mountpoint, False
        if not path:                   # read-only, just to look; a volume with no Windows on it is let go again
            path, _err = drives._do_mount(v.device, "ro", run)
            peeked = bool(path)
        found = probe_root(path, v) if path else None
        if v.uuid and path:
            drives._windows_seen[v.uuid] = bool(found)
        if found:
            v.mountpoint = path
            installs.append(found)
        elif peeked:
            drives._do_unmount(v.device, run)
    installs += [e for e in find_exports(vols) if e.root not in {i.root for i in installs}]
    return {"installs": sorted(installs, key=lambda i: -i.last_used), "locked": locked}


def pick_main(installs: List[WindowsInstall]) -> Optional[WindowsInstall]:
    """The most recently used. The user can pick another: this is only the suggestion."""
    return max(installs, key=lambda i: i.last_used) if installs else None


def linux_homes(volumes: List[drives.Volume], running: Optional[set] = None) -> List[WindowsInstall]:
    """Home folders on another Linux on this PC, files only (kind "linux"). Skips the running system."""
    running = _running_devices() if running is None else running
    out = []
    for v in volumes:
        if v.fstype.lower() not in ("ext4", "btrfs", "xfs", "ext3", "f2fs") or not v.mountpoint or v.protected:
            continue
        try:
            if os.stat(v.mountpoint).st_dev in running:
                continue
        except OSError:
            continue
        for home in ("home", "@home"):
            base = _ci_path(v.mountpoint, home)
            if base is None:
                continue
            try:
                users = sorted(e.name for e in os.scandir(base) if real_dir(e.path) and e.name != "lost+found"
                               and os.path.isdir(os.path.join(e.path, ".config")))
            except OSError:
                continue
            if users:
                out.append(WindowsInstall(Path(v.mountpoint) / home, v.device, v.label, v.uuid, v.partuuid, v.parttype,
                                          v.size, v.used, users, kind="linux"))
    return out


def profile_dir(install: WindowsInstall, user: str) -> Path:
    if os.sep in user or "/" in user or user in ("", ".", ".."):
        raise ValueError(f"not a user name: {user!r}")
    p = Path(install.root) / user if install.kind == "linux" else _ci_path(install.root, USERS_DIR, user)
    if not real_dir(p):
        raise ValueError(f"{user} has no profile on {install.name}.")
    return Path(p)


# ---------------------------------------------------------------------- files
@dataclass
class FolderChoice:
    name: str
    source: Path
    mode: str = "link"             # link | copy | skip


def plan_folders(install: WindowsInstall, user: str) -> List[FolderChoice]:
    """The known folders that really exist there. A junction or symlink isn't followed. A folder that Windows
    moved to OneDrive is used from there."""
    profile = profile_dir(install, user)
    out = []
    for name in FOLDERS:
        local, cloud = _ci_path(profile, name), _ci_path(profile, "OneDrive", name)
        source = local if real_dir(local) and (not real_dir(cloud) or any(os.scandir(local))) else cloud
        if real_dir(source):
            out.append(FolderChoice(name, Path(source)))
    return out


def safe_walk(top, cancel: Optional[threading.Event] = None) -> Iterator[tuple]:
    """(path, lstat) for every regular file under ``top``. Symlinks, junctions, other filesystems and SKIP_NAMES
    are not entered, and an unreadable folder is skipped."""
    try:
        top_dev = os.lstat(top).st_dev
    except OSError:
        return
    stack = [str(top)]
    while stack:
        if cancel is not None and cancel.is_set():
            return
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for e in entries:
            if e.name.lower() in SKIP_NAMES or is_link(e.path):
                continue
            try:
                st = os.lstat(e.path)
            except OSError:
                continue
            if stat.S_ISDIR(st.st_mode):
                if st.st_dev == top_dev:
                    stack.append(e.path)
            elif stat.S_ISREG(st.st_mode):
                yield e.path, st


def _tree_size(top, cancel=None) -> int:
    return sum(st.st_size for _p, st in safe_walk(top, cancel))


def stable_path(uuid: str) -> Path:
    """A path that survives the mount point changing: re-pointed at every login (login_mount)."""
    if not re.fullmatch(r"[0-9A-Za-z-]{1,64}", uuid or ""):
        raise ValueError(f"not a volume id: {uuid!r}")
    return Path(data_path("windows")) / uuid


def _point_stable(uuid: str, mountpoint: str, symlink: Callable = os.symlink) -> Path:
    link = stable_path(uuid)
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(link):
        if not os.path.islink(link):
            raise OSError(f"{link} is in the way.")
        os.unlink(link)
    symlink(mountpoint, link)
    return link


def link_folder(name: str, source: Path, install: WindowsInstall, home: Path, symlink: Callable = os.symlink) -> Dict:
    """~/<name> becomes a link to the folder on the other drive. If ~/<name> already has files in it, they stay,
    and the link goes inside as ~/<name>/From Windows."""
    volume_root = Path(install.root).parent if install.kind == "linux" else Path(install.root)
    stable = _point_stable(install.uuid, str(volume_root), symlink)
    target = stable / Path(source).relative_to(volume_root)
    dest = Path(home) / name
    if is_link(dest):
        if os.readlink(dest) == str(target):
            return {"name": name, "mode": "link", "path": str(dest), "note": "already linked"}
        dest = dest.parent / f"{name} from Windows"
    elif dest.is_dir():
        if any(os.scandir(dest)):
            dest = dest / "From Windows"
        else:
            dest.rmdir()
    if os.path.lexists(dest):
        return {"name": name, "mode": "link", "path": str(dest), "note": "something is already there; left alone",
                "failed": True}
    dest.parent.mkdir(parents=True, exist_ok=True)
    symlink(str(target), dest, target_is_directory=True)
    _log(f"link {dest} -> {target}")
    return {"name": name, "mode": "link", "path": str(dest), "target": str(target)}


def copy_folder(name: str, source: Path, home: Path, progress: Optional[Callable] = None,
                cancel: Optional[threading.Event] = None, usage: Callable = shutil.disk_usage) -> Dict:
    """Copies into ~/<name>/From Windows; nothing already in the home folder is overwritten."""
    files = list(safe_walk(source, cancel))
    need = sum(st.st_size for _p, st in files)
    dest_root = Path(home) / name / "From Windows"
    dest_root.mkdir(parents=True, exist_ok=True)
    free = usage(dest_root).free
    if need + 2 ** 30 > free:
        _log(f"copy {name} refused: needs {need}, free {free}")
        return {"name": name, "mode": "copy", "failed": True, "copied": 0, "errors": [],
                "note": f"Needs {need / 1e9:.1f} GB and only {free / 1e9:.1f} GB is free. Link it instead."}
    copied, done, errors = 0, 0, []
    for path, st in files:
        if cancel is not None and cancel.is_set():
            break
        rel = os.path.relpath(path, source)
        target = dest_root / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == st.st_size:
                done += st.st_size
                continue
            if target.exists():
                target = target.with_name(f"{target.stem} (from Windows){target.suffix}")
            shutil.copy2(path, target, follow_symlinks=False)
            copied += 1
        except OSError as e:
            errors.append(f"{rel}: {e.strerror or e}")
        done += st.st_size
        if progress:
            progress(f"{name}: {rel}", int(100 * done / need) if need else 100)
    _log(f"copy {name}: {copied} files, {len(errors)} errors")
    return {"name": name, "mode": "copy", "path": str(dest_root), "copied": copied, "errors": errors[:50],
            "failed": bool(errors) and not copied}


def run_files(install: WindowsInstall, user: str, choices: Iterable[FolderChoice], home: Optional[Path] = None,
              write: bool = False, progress: Optional[Callable] = None, cancel: Optional[threading.Event] = None,
              symlink: Callable = os.symlink) -> List[Dict]:
    home = Path(home or Path.home())
    results = []
    for c in choices:
        try:
            profile_dir(install, user)
            inside = Path(os.path.realpath(c.source)).is_relative_to(os.path.realpath(install.root))
            if not inside or not real_dir(c.source):
                raise ValueError(f"{c.source} isn't a folder on {install.name}.")
            if c.mode == "link":
                results.append(link_folder(c.name, Path(c.source), install, home, symlink))
            elif c.mode == "copy":
                results.append(copy_folder(c.name, Path(c.source), home, progress, cancel))
        except (OSError, ValueError) as e:
            _log(f"files {c.name} failed: {e}")
            results.append({"name": c.name, "mode": c.mode, "failed": True, "note": str(e)})
    if any(r.get("mode") == "link" and not r.get("failed") for r in results):
        _remember_mount(install, write)
        write_login_autostart(home)
    if any(not r.get("failed") for r in results):
        _record_migration(install.uuid, "files")
    return results


def _remember_mount(install: WindowsInstall, write: bool) -> None:
    state = _load_state()
    state.setdefault("mounts", {})[install.uuid] = {"write": bool(write)}
    _save_state(state)


def write_login_autostart(home: Path, python: Optional[str] = None) -> Path:
    """No fstab: at login udisks mounts the drives your links point to, then the links are re-pointed."""
    path = Path(home) / ".config" / "autostart" / "saint-migrated-drives.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[Desktop Entry]\nType=Application\nName=Connect your migrated drives\n"
                    f'Exec="{python or sys.executable}" -m core.windows_migration login-mount\n'
                    f"Path={PROJECT_ROOT}\nNoDisplay=true\nX-KDE-autostart-phase=1\n", encoding="utf-8")
    return path


def login_mount(run: Callable = subprocess.run) -> Dict[str, bool]:
    wanted = _load_state().get("mounts", {})
    out = {}
    if not wanted:
        return out
    vols = {v.uuid: v for v in drives.volumes(run)}
    for uuid, opts in wanted.items():
        v = vols.get(uuid)
        res = drives.mount(v, write=bool(opts.get("write")), run=run) if v else None
        out[uuid] = bool(res and res.mountpoint)
        if res and res.mountpoint:
            _point_stable(uuid, res.mountpoint)
        _log(f"login mount {uuid}: {'ok' if out[uuid] else 'not available'}")
    return out


# ---------------------------------------------------------------------- bookmarks
@dataclass
class Bookmark:
    browser: str
    folder: str
    title: str
    url: str


_SAFE_URL = re.compile(r"^(?:https?|ftp)://", re.I)


def _chromium_marks(path: Path, browser: str) -> List[Bookmark]:
    if os.path.getsize(path) > 64 * 2 ** 20:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    out: List[Bookmark] = []

    def walk(node, folder, depth=0):
        if depth > 40 or not isinstance(node, dict):
            return
        if node.get("type") == "url":
            out.append(Bookmark(browser, folder, str(node.get("name") or node.get("url")), str(node.get("url") or "")))
        for child in node.get("children") or []:
            name = child.get("name", "") if child.get("type") == "folder" else ""
            walk(child, f"{folder} / {name}" if name else folder, depth + 1)

    roots = data.get("roots") or {}
    for key, title in (("bookmark_bar", "Bookmarks bar"), ("other", "Other bookmarks"), ("synced", "Mobile bookmarks")):
        walk(roots.get(key), title)
    return out


def _firefox_marks(places: Path, browser: str = "Firefox") -> List[Bookmark]:
    """A private copy of the bookmarks database (a live or read-only one can't be opened safely). Only the
    bookmark tables are read."""
    with tempfile.TemporaryDirectory(prefix="saint-places-") as tmp:
        copy = Path(tmp) / "places.sqlite"
        shutil.copyfile(places, copy)
        con = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            rows = con.execute("SELECT b.title, p.url, f.title FROM moz_bookmarks b JOIN moz_places p ON p.id = b.fk "
                               "LEFT JOIN moz_bookmarks f ON f.id = b.parent WHERE b.type = 1").fetchall()
        finally:
            con.close()
    return [Bookmark(browser, folder or "Bookmarks", title or url, url) for title, url, folder in rows]


def read_bookmarks(profile: Path) -> Dict:
    """{"marks": [...], "errors": [...]} from every browser found. Only Bookmarks / places.sqlite are ever opened."""
    marks: List[Bookmark] = []
    errors = []
    for browser, parts in BROWSERS.items():
        base = _ci_path(profile, *parts)
        if base is None:
            continue
        for prof in sorted(p for p in os.scandir(base) if real_dir(p.path)
                           and (p.name == "Default" or p.name.startswith("Profile "))):
            f = ci_child(prof.path, "Bookmarks")
            if f is None or is_link(f):
                continue
            try:
                marks += _chromium_marks(Path(f), browser)
            except (OSError, ValueError) as e:
                errors.append(f"{browser}: {e}")
    base = _ci_path(profile, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
    if base is not None:
        for prof in os.scandir(base):
            f = ci_child(prof.path, "places.sqlite") if real_dir(prof.path) else None
            if f is None or is_link(f):
                continue
            try:
                marks += _firefox_marks(Path(f))
            except (OSError, sqlite3.Error) as e:
                errors.append(f"Firefox: {e}")
    seen, unique = set(), []
    for m in marks:
        if _SAFE_URL.match(m.url) and (m.browser, m.url) not in seen:
            seen.add((m.browser, m.url))
            unique.append(m)
    return {"marks": unique, "errors": errors}


def netscape_html(marks: List[Bookmark]) -> str:
    """The bookmarks file format every browser imports. Everything is escaped."""
    groups: Dict[str, Dict[str, List[Bookmark]]] = {}
    for m in marks:
        groups.setdefault(m.browser, {}).setdefault(m.folder, []).append(m)
    lines = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>", '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
             "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>", "<DL><p>"]
    for browser, folders in groups.items():
        lines += [f"<DT><H3>From {html.escape(browser)} on Windows</H3>", "<DL><p>"]
        for folder, items in folders.items():
            lines += [f"<DT><H3>{html.escape(folder)}</H3>", "<DL><p>"]
            lines += [f'<DT><A HREF="{html.escape(m.url, quote=True)}">{html.escape(m.title)}</A>' for m in items]
            lines.append("</DL><p>")
        lines.append("</DL><p>")
    lines.append("</DL><p>")
    return "\n".join(lines) + "\n"


def _firefox_profile(home: Path) -> Optional[Path]:
    base = Path(home) / ".mozilla" / "firefox"
    ini = base / "profiles.ini"
    if not ini.is_file():
        return None
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read(ini, encoding="utf-8")
    except configparser.Error:
        return None
    rows = [cp[s] for s in cp.sections() if s.startswith("Profile") and cp[s].get("Path")]
    rows.sort(key=lambda r: r.get("Default") != "1")
    if not rows:
        return None
    p = rows[0]["Path"]
    return base / p if rows[0].get("IsRelative", "1") == "1" else Path(p)


def install_into_firefox(html_file: Path, home: Path, run: Callable = subprocess.run) -> Dict:
    """A Firefox that has no bookmarks yet takes the file at its next start. One that has some keeps them (the
    startup import replaces all bookmarks), so there the user imports the file by hand, which merges."""
    manual = ("In Firefox: Bookmarks > Manage bookmarks > Import and Backup > Import Bookmarks from HTML, "
              f"then pick {html_file}.")
    profile = _firefox_profile(home)
    if profile is None:
        try:
            run(["firefox", "--headless", "--no-remote", "-CreateProfile", "default-release"],
                capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            _log(f"firefox profile: {e}")
        profile = _firefox_profile(home)
    if profile is None or not profile.is_dir() or (profile / "places.sqlite").exists():
        return {"firefox": "manual", "note": manual}
    shutil.copyfile(html_file, profile / "bookmarks.html")
    # prefs.js rather than user.js: Firefox clears this one after importing, while user.js would import (and
    # replace) on every start.
    with open(profile / "prefs.js", "a", encoding="utf-8") as f:
        f.write('user_pref("browser.places.importBookmarksHTML", true);\n')
    return {"firefox": "next_start", "note": f"Firefox picks them up the next time it opens. If not: {manual}"}


def import_bookmarks(install: WindowsInstall, user: str, home: Optional[Path] = None, run: Callable = subprocess.run) -> Dict:
    home = Path(home or Path.home())
    found = read_bookmarks(profile_dir(install, user))
    marks = found["marks"]
    counts: Dict[str, int] = {}
    for m in marks:
        counts[m.browser] = counts.get(m.browser, 0) + 1
    out = {"count": len(marks), "by_browser": counts, "errors": found["errors"]}
    if marks:
        html_file = home / "Documents" / "Bookmarks from Windows.html"
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text(netscape_html(marks), encoding="utf-8")
        out.update(file=str(html_file), **install_into_firefox(html_file, home, run))
    _log(f"bookmarks: {counts}, errors {found['errors']}")
    _record_migration(install.uuid, "bookmarks")
    return out


# ---------------------------------------------------------------------- wallpaper, VS Code, Steam, values
def import_wallpaper(install: WindowsInstall, user: str, home: Optional[Path] = None, run: Callable = subprocess.run) -> Dict:
    home = Path(home or Path.home())
    src = _ci_path(profile_dir(install, user), "AppData", "Roaming", "Microsoft", "Windows", "Themes", "TranscodedWallpaper")
    if src is None:
        return {"ok": False, "note": "No wallpaper was found in this Windows."}
    with open(src, "rb") as f:
        head = f.read(8)
    ext = ".png" if head.startswith(b"\x89PNG") else ".jpg" if head.startswith(b"\xff\xd8") else ""
    if not ext:
        return {"ok": False, "note": "The saved wallpaper isn't a picture HalOS can read."}
    dest = home / "Pictures" / f"Windows wallpaper{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    applied = False
    if shutil.which("plasma-apply-wallpaperimage"):
        try:
            applied = run(["plasma-apply-wallpaperimage", str(dest)], capture_output=True, text=True,
                          timeout=30).returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            _log(f"wallpaper apply: {e}")
    _log(f"wallpaper: {dest}, applied={applied}")
    return {"ok": True, "path": str(dest), "applied": applied}


_EXTENSION = re.compile(r"^([a-z0-9][a-z0-9-]*\.[a-z0-9][a-z0-9-]*)-\d+\.\d+\S*$", re.I)


def import_vscode(install: WindowsInstall, user: str, home: Optional[Path] = None, run: Callable = subprocess.run) -> Dict:
    """settings, keybindings and snippets; anything already in the HalOS copy stays. Extensions are installed by
    name, because the Windows copies won't run here."""
    home = Path(home or Path.home())
    profile = profile_dir(install, user)
    src = _ci_path(profile, "AppData", "Roaming", "Code", "User")
    out: Dict = {"copied": [], "extensions": [], "installed": 0}
    if src is not None:
        dest = home / ".config" / "Code" / "User"
        for name in ("settings.json", "keybindings.json"):
            f = ci_child(src, name)
            if f is not None and not is_link(f) and os.path.isfile(f) and not (dest / name).exists():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest / name)
                out["copied"].append(name)
        snippets = _ci_path(src, "snippets")
        if snippets is not None:
            for path, _st in safe_walk(snippets):
                target = dest / "snippets" / os.path.relpath(path, snippets)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                    out["copied"].append(f"snippets/{target.name}")
    ext_dir = _ci_path(profile, ".vscode", "extensions")
    if ext_dir is not None:
        ids = {m[1].lower() for m in (_EXTENSION.match(e.name) for e in os.scandir(ext_dir)) if m}
        out["extensions"] = sorted(ids)
    if out["extensions"]:
        (home / "Documents").mkdir(parents=True, exist_ok=True)
        (home / "Documents" / "VS Code extensions from Windows.txt").write_text("\n".join(out["extensions"]) + "\n",
                                                                                encoding="utf-8")
        if shutil.which("code"):
            for ext in out["extensions"]:
                try:
                    if run(["code", "--install-extension", ext], capture_output=True, text=True, timeout=180).returncode == 0:
                        out["installed"] += 1
                except (OSError, subprocess.SubprocessError) as e:
                    _log(f"vscode extension {ext}: {e}")
    _log(f"vscode: {len(out['copied'])} files, {len(out['extensions'])} extensions, {out['installed']} installed")
    return out


_VDF_PATH = re.compile(r'"path"\s+"([^"]+)"', re.I)


def steam_libraries(install: WindowsInstall) -> List[str]:
    """Where Windows' Steam kept its games. Shown, not registered: Steam's own Add Drive does that properly, and
    Proton runs poorly from NTFS, so that choice belongs to the user."""
    f = _ci_path(install.root, "Program Files (x86)", "Steam", "steamapps", "libraryfolders.vdf") \
        or _ci_path(install.root, "Program Files (x86)", "Steam", "config", "libraryfolders.vdf")
    if f is None:
        return []
    try:
        return [p.replace("\\\\", "\\") for p in _VDF_PATH.findall(Path(f).read_text(encoding="utf-8", errors="replace"))]
    except OSError:
        return []


def _hive_string(h, node, name: str) -> str:
    v = h.node_get_value(node, name)
    return h.value_string(v) if v else ""


def _hive_path(h, parts: Iterable[str]):
    node = h.root()
    for p in parts:
        node = h.node_get_child(node, p)
        if not node:
            return None
    return node


def windows_values(install: WindowsInstall, hive: Optional[Callable] = None) -> Dict[str, str]:
    """Read-only values from the registry files, when python-hivex is here (optional): computer name, time zone."""
    system = _ci_path(install.root, "Windows", "System32", "config", "SYSTEM")
    out = {"Installed on": install.name, "Accounts": ", ".join(install.users) or "none"}
    if system is None:
        return out
    try:
        if hive is None:
            import hivex
            hive = hivex.Hivex
        h = hive(str(system))
        name = _hive_path(h, ("ControlSet001", "Control", "ComputerName", "ComputerName"))
        zone = _hive_path(h, ("ControlSet001", "Control", "TimeZoneInformation"))
        if name:
            out["Computer name"] = _hive_string(h, name, "ComputerName")
        if zone:
            out["Time zone"] = _hive_string(h, zone, "TimeZoneKeyName")
    except Exception as e:             # hivex missing, or a hive it can't read: the rest of the page still works
        log.info("migration.hive_unavailable %s", e)
    return out


# ---------------------------------------------------------------------- apps
_NOT_APPS = re.compile(
    r"^(?:common files|windows\b|microsoft\b(?! (?:edge|visual studio code|vs code|teams|office|onedrive))|"
    r"internet explorer|modifiablewindowsapps|windowsapps|msbuild|reference assemblies|dotnet|packagemanagement|"
    r"nvidia|intel|realtek|amd\b|uninstall|desktop\.ini|administrative tools|accessibility|accessories|startup|"
    r"system tools|maintenance|windows powershell|powershell|immersive control panel)|"
    r"\b(?:uninstall|readme|help|website|manual|documentation|release notes|license|update|updater)\b", re.I)

# Windows name (lower case, contains) -> what to search the Store for.
ALIASES = {"google chrome": "chrome", "visual studio code": "vscode", "vs code": "vscode", "videolan": "vlc",
           "vlc media player": "vlc", "obs studio": "obs", "obs-studio": "obs", "telegram": "telegram",
           "brave": "brave", "steam": "steam", "discord": "discord", "spotify": "spotify", "slack": "slack",
           "zoom": "zoom", "gimp": "gimp", "krita": "krita", "audacity": "audacity", "blender": "blender",
           "libreoffice": "libreoffice", "obsidian": "obsidian", "qbittorrent": "qbittorrent",
           "heroic": "heroic", "microsoft edge": "microsoft edge", "microsoft teams": "teams-for-linux",
           "microsoft office": "libreoffice", "epic games": "heroic", "7-zip": "p7zip", "notepad++": "notepad++",
           "git": "git", "python": "python", "nodejs": "nodejs", "node.js": "nodejs"}


def _names_in(folder: Optional[Path]) -> List[str]:
    if folder is None:
        return []
    try:
        return [e.name for e in os.scandir(folder) if not is_link(e.path) and os.path.isdir(e.path)]
    except OSError:
        return []


def _uninstall_names(install: WindowsInstall, hive: Optional[Callable] = None) -> List[str]:
    software = _ci_path(install.root, "Windows", "System32", "config", "SOFTWARE")
    if software is None:
        return []
    try:
        if hive is None:
            import hivex
            hive = hivex.Hivex
        h = hive(str(software))
        out = []
        for path in (("Microsoft", "Windows", "CurrentVersion", "Uninstall"),
                     ("WOW6432Node", "Microsoft", "Windows", "CurrentVersion", "Uninstall")):
            node = _hive_path(h, path)
            for child in h.node_children(node) if node else []:
                if h.node_get_value(child, "DisplayName"):
                    out.append(_hive_string(h, child, "DisplayName"))
        return out
    except Exception as e:
        log.info("migration.uninstall_hive_unavailable %s", e)
        return []


def collect_app_names(install: WindowsInstall, hive: Optional[Callable] = None) -> List[str]:
    """Program Files folders, Start Menu shortcut names (never opened), and the Uninstall key when hivex is here.
    An export folder carries the list itself (apps.json)."""
    listed = ci_child(install.root, "apps.json")
    if listed is not None and not is_link(listed):
        try:
            rows = json.loads(Path(listed).read_text(encoding="utf-8-sig"))
            rows = rows if isinstance(rows, list) else [rows]
            return sorted({str(r.get("name", "")).strip() for r in rows if isinstance(r, dict) and r.get("name")},
                          key=str.lower)
        except (OSError, ValueError):
            pass
    names = _names_in(_ci_path(install.root, "Program Files")) + _names_in(_ci_path(install.root, "Program Files (x86)"))
    menus = [_ci_path(install.root, "ProgramData", "Microsoft", "Windows", "Start Menu", "Programs")]
    menus += [_ci_path(install.root, USERS_DIR, u, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs")
              for u in install.users]
    for menu in menus:
        if menu is None:
            continue
        for path, _st in safe_walk(menu):
            if path.lower().endswith(".lnk"):
                names.append(Path(path).stem)
    names += _uninstall_names(install, hive)
    seen: Dict[str, str] = {}
    for n in names:
        n = re.sub(r"\s+", " ", n).strip()
        n = re.sub(r"\s+\(?(?:x64|x86|64-bit|32-bit)\)?$|\s+v?\d[\d.]*$", "", n, flags=re.I).strip()
        if n and not _NOT_APPS.search(n):
            seen.setdefault(n.lower(), n)
    return sorted(seen.values(), key=str.lower)


@dataclass
class AppMatch:
    windows_name: str
    result: object = None          # core.store.Result: what "Install" installs (None when there's nothing to install)
    kind: str = "none"             # native | wine | web | alternative | none | not_needed (core/app_match.py)
    why: str = ""                  # one line for the user: why this match, or why there isn't one
    link: str = ""                 # official Linux download or the web app, when known
    alternative: str = ""
    confidence: float = 0.0


def _plain(s: str) -> str:
    return re.sub(r"[^a-z0-9+]+", " ", s.lower()).strip()


def _best(name: str, query: str, hits: list):
    n, q = _plain(name), _plain(query)
    for h in hits:
        for candidate in (_plain(h.name), _plain(h.id)):
            if candidate and candidate in (n, q):
                return h
    for h in hits:
        c = _plain(h.name)
        if c and len(c) >= 4 and (c in n or n in c):
            return h
    return None


def _curated_match(name: str, c) -> AppMatch:
    """An AppMatch from the curated table's answer (core/app_match.Curated)."""
    from core.store import Result
    target = c.store_target()
    result = Result(target[0], target[1], c.name) if target and c.kind in ("native", "wine", "alternative") else None
    why = c.why or {"native": f"{c.name} has a Linux version.", "wine": f"{c.name} runs with Wine.",
                    "web": f"{c.name} works in the browser."}.get(c.kind, "")
    return AppMatch(name, result, c.kind, why, c.link(), c.alternative, c.confidence)


def match_apps(names: List[str], search: Optional[Callable] = None, progress: Optional[Callable] = None,
               cancel: Optional[threading.Event] = None, limit: int = 400,
               curated: Optional[Callable] = None) -> List[AppMatch]:
    """Each name against the curated table (core/app_match.py), then the Store: Linux versions first, then a
    Windows build for Wine, else nothing is offered. Drivers and runtimes come back as "not_needed"."""
    if search is None:
        from core.store import search as search
        if curated is None:
            from core.app_match import lookup as curated
    native, windows = ("featured", "repo", "flathub"), ("windows",)
    out: List[AppMatch] = []
    used = set()
    names = names[:limit]
    for i, name in enumerate(names):
        if cancel is not None and cancel.is_set():
            break
        low = name.lower()
        query = next((v for k, v in ALIASES.items() if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", low)), name)
        match = AppMatch(name)
        known = curated(name) if curated else None
        if known is not None:
            match = _curated_match(name, known)
            key = f"{known.kind}:{known.name}"
            if key in used:                # "Steam" and "Steam Client Service" are one row, drivers one row each
                continue
            used.add(key)
        else:
            try:
                hit = _best(name, query, search(query, sources=native))
                if hit is not None:
                    match = AppMatch(name, hit, "native", f"Found in {hit.label} by name.", confidence=0.6)
                else:
                    hit = _best(name, query, search(query, sources=windows))
                    if hit is not None:
                        match = AppMatch(name, hit, "wine", "The Windows version, run with Wine.", confidence=0.5)
            except Exception as e:     # offline, a source down, a name the search refuses: this one is listed unmatched
                log.info("migration.match_failed %r: %s", name, e)
        if match.result is not None:
            if match.result.id in used:
                continue
            used.add(match.result.id)
        out.append(match)
        if progress:
            progress(name, int(100 * (i + 1) / len(names)))
    return out


# ---------------------------------------------------------------------- Wi-Fi networks
_WLAN_NAME = re.compile(r"<name>([^<]{1,32})</name>")
_WLAN_KEY = re.compile(r"<keyMaterial>([^<]{8,63})</keyMaterial>")
_WLAN_AUTH = re.compile(r"<authentication>([^<]+)</authentication>")


def wifi_profiles(install: WindowsInstall) -> List[Dict]:
    """Saved Wi-Fi networks: {"ssid", "key" or "", "auth"}. From an export's wifi/ folder (with passwords only if
    the person chose -WifiPasswords), or the names from a Windows disk (its passwords are encrypted for that
    Windows and are never read)."""
    folders = [ci_child(install.root, "wifi"),
               _ci_path(install.root, "ProgramData", "Microsoft", "Wlansvc", "Profiles", "Interfaces")]
    out, seen = [], set()
    for folder in folders:
        if folder is None:
            continue
        for path, _st in safe_walk(folder):
            if not path.lower().endswith(".xml"):
                continue
            try:
                text = Path(path).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            name, key, auth = _WLAN_NAME.search(text), _WLAN_KEY.search(text), _WLAN_AUTH.search(text)
            if not name or name[1] in seen:
                continue
            seen.add(name[1])
            out.append({"ssid": name[1], "key": key[1] if key else "", "auth": auth[1] if auth else ""})
    return out


def wifi_commands(profiles: List[Dict]) -> List[List[str]]:
    """nmcli commands that save each network (argument lists; a network already saved is skipped by nmcli's
    unique name check). Open networks need no key; secured ones without a key are saved to ask on first use."""
    cmds = []
    for p in profiles:
        argv = ["nmcli", "connection", "add", "type", "wifi", "con-name", p["ssid"], "ssid", p["ssid"]]
        if p["key"] and p["auth"].upper().startswith("WPA"):
            argv += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", p["key"]]
        elif p["auth"].upper().startswith("WPA"):
            argv += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk-flags", "2"]        # ask for it when it's in range
        cmds.append(argv)
    return cmds


def import_wifi(install: WindowsInstall, run: Callable = subprocess.run) -> Dict:
    profiles = wifi_profiles(install)
    added, errors = 0, []
    existing = ""
    try:
        existing = run(["nmcli", "-t", "-f", "NAME", "connection", "show"], capture_output=True, text=True,
                       timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        pass
    have = set(existing.splitlines())
    for argv in wifi_commands([p for p in profiles if p["ssid"] not in have]):
        try:
            r = run(argv, capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                added += 1
            else:
                errors.append(f"{argv[6]}: {(r.stderr or '').strip()[:120]}")
        except (OSError, subprocess.SubprocessError) as e:
            errors.append(f"{argv[6]}: {e}")
    with_keys = sum(1 for p in profiles if p["key"])
    _log(f"wifi: {len(profiles)} found, {added} added, {with_keys} with passwords")
    return {"found": len(profiles), "added": added, "with_passwords": with_keys, "errors": errors}


def match_counts(matches: List[AppMatch]) -> Dict[str, int]:
    """kind -> how many, for the filter row ("Works on HalOS (41)")."""
    out: Dict[str, int] = {}
    for m in matches:
        out[m.kind] = out.get(m.kind, 0) + 1
    return out


# ---------------------------------------------------------------------- removal of the old Windows
@dataclass
class MountInfo:
    mountpoint: str
    fstype: str
    source: str
    options: str


def read_mount_info(root, mountinfo: str = "/proc/self/mountinfo") -> Optional[MountInfo]:
    """The mount at exactly ``root``, or None if ``root`` isn't a mount point."""
    try:
        lines = Path(mountinfo).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    found = None
    want = os.path.realpath(root)
    for line in lines:
        left, _, right = line.partition(" - ")
        lf, rf = left.split(), right.split()
        if len(lf) >= 6 and len(rf) >= 3:
            mp = lf[4].replace("\\040", " ")
            if mp == want:
                found = MountInfo(mp, rf[0], rf[1], f"{lf[5]},{rf[2]}")    # the last one is what's on top
    return found


def _running_devices() -> set:
    """st_dev of everything the running OS lives on."""
    devs = set()
    for p in ("/", "/usr", "/home", "/boot", "/var", sys.executable, str(Path.home())):
        try:
            devs.add(os.stat(p).st_dev)
        except OSError:
            pass
    return devs


@dataclass
class RemovalItem:
    path: str
    kind: str                      # "dir" | "file"
    size: int = 0


@dataclass
class RemovalPlan:
    install: WindowsInstall
    items: List[RemovalItem] = field(default_factory=list)
    refusals: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)      # listed names that are links: not followed, not removed
    include_users: bool = False
    token: str = ""

    @property
    def size(self) -> int:
        return sum(i.size for i in self.items)

    @property
    def allowed(self) -> bool:
        return not self.refusals and bool(self.items)


def confirm_token(install: WindowsInstall) -> str:
    """What must be typed to confirm: the volume's label, or its device name when it has none."""
    return install.label or Path(install.device).name or str(install.root)


def _same_install(a: WindowsInstall, b: WindowsInstall) -> bool:
    if os.path.realpath(a.root) == os.path.realpath(b.root):
        return True
    return any(x and x == y for x, y in ((a.uuid, b.uuid), (a.partuuid, b.partuuid), (a.device, b.device)))


def _allowed_names(include_users: bool) -> Dict[str, str]:
    names = {n.lower(): "dir" for n in REMOVABLE_DIRS}
    names.update({n.lower(): "file" for n in REMOVABLE_FILES})
    if include_users:
        names[USERS_DIR.lower()] = "dir"
    return names


def check_removal(install: WindowsInstall, main: Optional[WindowsInstall], include_users: bool = False,
                  mount_info: Callable = read_mount_info, running: Optional[set] = None) -> List[str]:
    """Every reason this volume must not be touched. An empty list is the only way forward."""
    from core.install_target import ESP_TYPE, MSR_TYPE, RECOVERY_TYPE
    refusals = []
    running = _running_devices() if running is None else running
    root = str(install.root)
    if install.kind != "windows":
        refusals.append("Only an old Windows can be removed here.")
    if main is None:
        refusals.append("Choose your main Windows first.")
    elif _same_install(install, main):
        refusals.append(f"{install.name} is the Windows you chose as main, so it stays.")
    if (install.parttype or "").lower() in (ESP_TYPE, MSR_TYPE, RECOVERY_TYPE):
        refusals.append(f"{install.name} is an EFI, reserved or Recovery partition. Those are never touched.")
    if is_link(root) or not os.path.isdir(root):
        refusals.append(f"{root} isn't a real folder.")
    elif not drives.is_windows_root(root):
        refusals.append(f"{root} doesn't hold a Windows (no Windows\\System32).")
    try:
        if os.stat(root).st_dev in running:
            refusals.append(f"{install.name} hosts the system that's running now.")
    except OSError as e:
        refusals.append(f"{root} can't be read: {e.strerror}.")
    info = mount_info(root)
    if info is None:
        refusals.append(f"{root} isn't a mounted volume.")
    else:
        if info.fstype.lower() not in drives.NTFS:
            refusals.append(f"{install.name} isn't NTFS ({info.fstype}).")
        if "rw" not in info.options.split(",") or "ro" in info.options.split(","):
            refusals.append(f"{install.name} isn't mounted read-write. Turn on writing for it in Drives first.")
        if install.device and info.source != install.device:
            refusals.append(f"{root} is {info.source}, not {install.device}.")
    if os.path.isdir(root) and drives.hibernated(root):
        refusals.append(f"{install.name} is hibernated (Fast Startup). {drives.FAST_STARTUP}")
    if include_users:
        if not migration_ran(install.uuid):
            refusals.append("Run the Files step for this Windows before removing its user files.")
        else:
            refusals += _links_into(install)
    return refusals


def _links_into(install: WindowsInstall) -> List[str]:
    """The Users folder must not hold what HalOS's home links to."""
    state = _load_state()
    if install.uuid in state.get("mounts", {}):
        return [f"Your home folder still links to {install.name}. Copy those folders instead, then remove them."]
    return []


def build_removal(install: WindowsInstall, main: Optional[WindowsInstall], include_users: bool = False,
                  mount_info: Callable = read_mount_info, running: Optional[set] = None,
                  measure: bool = True) -> RemovalPlan:
    """The exact list: direct children of the volume's root with an allowed name, each a real folder or file.
    Nothing else can get on it, however it's named."""
    plan = RemovalPlan(install, include_users=include_users, token=confirm_token(install),
                       refusals=check_removal(install, main, include_users, mount_info, running))
    allowed = _allowed_names(include_users)
    try:
        entries = list(os.scandir(install.root))
    except OSError as e:
        plan.refusals.append(f"{install.root} can't be listed: {e.strerror}.")
        return plan
    for e in sorted(entries, key=lambda x: x.name.lower()):
        kind = allowed.get(e.name.lower())
        if not kind:
            continue
        if is_link(e.path):
            plan.skipped.append(e.path)
            _log(f"removal plan: {e.path} is a link, not followed")
            continue
        try:
            st = os.lstat(e.path)
        except OSError:
            continue
        if kind == "dir" and stat.S_ISDIR(st.st_mode):
            plan.items.append(RemovalItem(e.path, "dir", _removal_size(e.path) if measure else 0))
        elif kind == "file" and stat.S_ISREG(st.st_mode):
            plan.items.append(RemovalItem(e.path, "file", st.st_size))
    return plan


def _removal_size(top) -> int:
    """Everything that will go, junk names included (unlike safe_walk, which skips what isn't worth copying)."""
    total, stack = 0, [str(top)]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for e in entries:
            if is_link(e.path):
                continue
            try:
                st = os.lstat(e.path)
            except OSError:
                continue
            if stat.S_ISDIR(st.st_mode):
                stack.append(e.path)
            else:
                total += st.st_size
    return total


def _assert_allowed(root, item: RemovalItem, include_users: bool) -> None:
    """Last check before anything goes, whatever the plan says."""
    path = item.path
    real_root = os.path.realpath(root)
    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(root) \
            or os.path.dirname(os.path.realpath(path)) != real_root:
        raise PermissionError(f"{path} isn't directly on the volume.")
    if os.path.basename(path).lower() not in _allowed_names(include_users):
        raise PermissionError(f"{path} isn't on the list of what may be removed.")
    if is_link(path):
        raise PermissionError(f"{path} is a link; links are never followed.")


def _unlink_entry(path: str, dry_run: bool) -> None:
    if dry_run:
        return
    try:
        os.unlink(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        os.unlink(path)


def _delete_tree(top: str, dry_run: bool, on_file: Callable, errors: List[str], cancel: Optional[threading.Event]) -> None:
    """Depth-first without ever entering a link, a junction or another filesystem. A link inside is removed as a
    link, so what it points at is untouched."""
    root_dev = os.lstat(top).st_dev
    stack = [(top, False)]
    while stack:
        if cancel is not None and cancel.is_set():
            return
        path, visited = stack.pop()
        if visited:
            if not dry_run:
                try:
                    os.rmdir(path)
                except OSError as e:
                    errors.append(f"{path}: {e.strerror or e}")
            continue
        stack.append((path, True))
        try:
            entries = list(os.scandir(path))
        except OSError as e:
            errors.append(f"{path}: {e.strerror or e}")
            continue
        for e in entries:
            try:
                st = os.lstat(e.path)
                if os.path.isjunction(e.path):        # on Windows a junction is removed with rmdir
                    if not dry_run:
                        os.rmdir(e.path)
                elif stat.S_ISLNK(st.st_mode):
                    if not dry_run:
                        os.unlink(e.path)
                elif stat.S_ISDIR(st.st_mode):
                    if st.st_dev != root_dev:
                        errors.append(f"{e.path}: another filesystem is mounted here; left alone")
                    else:
                        stack.append((e.path, False))
                else:
                    _unlink_entry(e.path, dry_run)
                    on_file(st.st_size)
            except OSError as err:
                errors.append(f"{e.path}: {err.strerror or err}")


def execute_removal(plan: RemovalPlan, main: Optional[WindowsInstall], typed: str, dry_run: bool = False,
                    mount_info: Callable = read_mount_info, running: Optional[set] = None,
                    progress: Optional[Callable] = None, cancel: Optional[threading.Event] = None) -> Dict:
    """Checks everything again (a plan can be minutes old), requires the typed confirmation, then removes the
    listed items only. ``dry_run`` walks the same path and deletes nothing."""
    install = plan.install
    refusals = check_removal(install, main, plan.include_users, mount_info, running)
    token = confirm_token(install)
    if typed != token:
        refusals.append(f"Type {token} exactly to confirm.")
    if not plan.items:
        refusals.append("There's nothing on the list to remove.")
    for item in plan.items:
        try:
            _assert_allowed(install.root, item, plan.include_users)
        except PermissionError as e:
            refusals.append(str(e))
    if refusals:
        _log(f"removal refused on {install.name}: {refusals}")
        return {"ok": False, "refused": refusals, "freed": 0, "errors": []}

    total = plan.size or 1
    state = {"freed": 0}
    errors: List[str] = []

    def on_file(size):
        state["freed"] += size
        if progress:
            progress(f"{state['freed'] / 1e9:.1f} GB", min(100, int(100 * state["freed"] / total)))

    verb = "DRY RUN would remove" if dry_run else "removing"
    _log(f"removal start on {install.name} ({install.device}) dry_run={dry_run}: {[i.path for i in plan.items]}")
    for item in plan.items:
        if cancel is not None and cancel.is_set():
            break
        _log(f"{verb} {item.path}")
        try:
            if item.kind == "dir":
                _delete_tree(item.path, dry_run, on_file, errors, cancel)
            else:
                st = os.lstat(item.path)
                _unlink_entry(item.path, dry_run)
                on_file(st.st_size)
        except OSError as e:
            errors.append(f"{item.path}: {e.strerror or e}")
    _log(f"removal done on {install.name}: {state['freed']} bytes, {len(errors)} errors, dry_run={dry_run}")
    for e in errors[:200]:
        _log(f"  {e}")
    return {"ok": not errors, "refused": [], "freed": state["freed"], "errors": errors[:50], "dry_run": dry_run,
            "cancelled": bool(cancel is not None and cancel.is_set()), "log": str(data_path(LOG_NAME))}


def read_bcd_for(partuuid: str, volumes: List[drives.Volume], run: Callable = subprocess.run) -> Optional[bytes]:
    """That EFI partition's Windows boot data, read-only; a temporary mount is taken away again."""
    v = next((x for x in volumes if x.partuuid.lower() == partuuid.lower() and x.is_esp), None)
    if v is None:
        return None
    path, mounted_here = v.mountpoint, False
    if not path:
        path, _err = drives._do_mount(v.device, "ro", run)
        mounted_here = bool(path)
    if not path:
        return None
    try:
        bcd = _ci_path(path, "EFI", "Microsoft", "Boot", "BCD")
        return Path(bcd).read_bytes() if bcd else None
    except OSError:
        return None
    finally:
        if mounted_here:
            drives._do_unmount(v.device, run)


if __name__ == "__main__":
    if sys.argv[1:] == ["login-mount"]:
        login_mount()
        raise SystemExit(0)
    print("usage: python -m core.windows_migration login-mount", file=sys.stderr)
    raise SystemExit(64)

