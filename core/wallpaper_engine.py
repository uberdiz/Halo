"""
core/wallpaper_engine.py

Wallpaper Engine wallpapers on HalOS. Wallpaper Engine (Steam app 431960) keeps every subscribed workshop item in
<steam library>/steamapps/workshop/content/431960/<id>/project.json (title, preview image, type scene/video/web,
main file). This module finds them in every Steam library (native Steam, ~/.steam, the Flatpak Steam, and the
extra libraries in libraryfolders.vdf) and applies one:

    kde     the Plasma 6 wallpaper plugin com.github.catsout.wallpaperEngineKde (AUR wallpaper-engine-kde-plugin),
            switched to through the same plasmashell script as the living wallpaper (ui/settings_pages/wallpaper.py)
    cli     linux-wallpaperengine, started per monitor, when the plugin isn't there
    video   a video item (or any .mp4/.webm) without either: Plasma's video wallpaper plugin if one is installed

Neither installed: apply() says so, and install_support() installs the plugin through core/pkg_queue.py.
Workshop files are untrusted data: only project.json is parsed, and paths that would need escaping in the Plasma
script are refused.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("saint.wallpaper_engine")

APP_ID = "431960"
KDE_PLUGIN = "com.github.catsout.wallpaperEngineKde"
AUR_PACKAGE = "wallpaper-engine-kde-plugin"
CLI = "linux-wallpaperengine"
# Plasma 6 has no video wallpaper of its own; these are the ones people install (first found wins).
VIDEO_PLUGINS = ("luisbocanegra.smart.video.wallpaper.reborn", "smartvideowallpaper")
TYPES = ("scene", "video", "web")
VIDEO_EXT = (".mp4", ".webm", ".mkv", ".mov")
_ID = re.compile(r"\d{1,20}")
_VDF_PATH = re.compile(r'"path"\s+"([^"]+)"')
_NAME = re.compile(r"[^/\\\x00]{1,200}")


def migrated_dirs(home: Path) -> List[Tuple[Path, bool]]:
    """Where the Windows migration puts Wallpaper Engine items when HalOS has no Steam yet
    (~/.local/share/halos/wallpapers/431960/<id>) and your own projects (.../myprojects/<name>): (folder, named)."""
    base = home / ".local/share/halos/wallpapers"
    return [(base / APP_ID, False), (base / "myprojects", True)]


class EngineError(RuntimeError):
    """Why a Wallpaper Engine wallpaper couldn't be applied, in words fit for the user."""


# ---------------------------------------------------------------------- finding items
def steam_roots(home: Path) -> List[Path]:
    return [home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/data/Steam"]


def libraries(home: Optional[Path] = None) -> List[Path]:
    """Every Steam library folder: the roots, plus the extra ones Steam lists in libraryfolders.vdf."""
    home = Path(home or Path.home())
    out: List[Path] = []
    for root in steam_roots(home):
        cands = [root]
        try:
            vdf = (root / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
            cands += [Path(p.replace("\\\\", "\\")) for p in _VDF_PATH.findall(vdf)]
        except OSError:
            pass
        for c in cands:
            try:
                key = c.resolve()
            except OSError:
                continue
            if c.is_dir() and key not in {o.resolve() for o in out}:
                out.append(c)
    return out


# Where Steam lives on a Windows drive (its own folder, or a library made in Steam's Storage settings).
WINDOWS_STEAM = (("Program Files (x86)", "Steam"), ("Program Files", "Steam"), ("SteamLibrary",), ("Steam",),
                 ("Games", "Steam"), ("Games", "SteamLibrary"))
_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]+(.*)$")


def windows_mounts(run: Callable = subprocess.run) -> List[Path]:
    """Mount points of the Windows (NTFS) partitions that are mounted now. Nothing is mounted here: HalOS Files,
    the migration or the Wallpapers app's "Look on Windows drives" does that."""
    try:
        from core import drives
        return [Path(v.mountpoint) for v in drives.volumes(run) if v.is_ntfs and v.mountpoint and not v.protected]
    except Exception as e:                       # no lsblk (not Linux), or it failed: no Windows drives
        log.info("wallpaper_engine.no_windows_drives %s", type(e).__name__)
        return []


def windows_libraries(mounts: List[Path]) -> List[Path]:
    """Steam libraries on Windows drives: the usual folders, plus every library their libraryfolders.vdf lists
    (a Windows path like D:\\SteamLibrary is looked for on every mounted drive, as drive letters mean nothing
    here). Case is ignored, as on Windows; links and junctions are never followed."""
    from core.drives import ci_child, real_dir

    def walk(root: Path, parts) -> Optional[Path]:
        cur = root
        for p in parts:
            cur = ci_child(cur, p)
            if not real_dir(cur):
                return None
        return cur if real_dir(ci_child(cur, "steamapps")) else None
    out: List[Path] = []

    def add(p: Optional[Path]):
        if p is not None and p not in out:
            out.append(p)
    for m in mounts:
        for parts in WINDOWS_STEAM:
            add(walk(Path(m), parts))
    for lib in list(out):
        vdf = ci_child(ci_child(lib, "steamapps") or lib, "libraryfolders.vdf")
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace") if vdf else ""
        except OSError:
            text = ""
        for raw in _VDF_PATH.findall(text):
            w = _WIN_DRIVE.match(raw.replace("\\\\", "\\"))
            parts = [p for p in re.split(r"[\\/]+", w.group(1)) if p] if w else []
            if parts and ".." not in parts:
                for m in mounts:
                    add(walk(Path(m), parts))
    return out


def read_item(d: Path, named: bool = False) -> Optional[dict]:
    """One workshop folder -> {id, title, type, dir, file, preview, library}, or None if it isn't a wallpaper.
    ``named``: one of your own projects, whose folder has a name instead of a workshop id."""
    if not (named and _NAME.fullmatch(d.name) or _ID.fullmatch(d.name)):
        return None
    try:
        p = json.loads((d / "project.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(p, dict):
        return None

    def inside(name) -> Optional[Path]:
        if not isinstance(name, str) or not name or "\x00" in name:
            return None
        f = d / name
        try:
            return f if f.is_file() and f.resolve().is_relative_to(d.resolve()) else None
        except OSError:
            return None
    main = inside(p.get("file"))
    kind = str(p.get("type", "")).lower()
    if kind not in TYPES:
        kind = "video" if main and main.suffix.lower() in VIDEO_EXT else "scene"
    title = " ".join(str(p.get("title") or "").split())[:200] or f"Workshop item {d.name}"
    steam = len(d.parents) > 4 and d.parents[3].name.lower() == "steamapps"
    return {"id": f"myprojects:{d.name}" if named else d.name, "title": title, "type": kind, "dir": d, "file": main,
            "preview": inside(p.get("preview")),
            "library": d.parents[4] if steam else None}   # <library>/steamapps/workshop/content/431960/<id>


def items(home: Optional[Path] = None, windows: Optional[List[Path]] = None) -> List[dict]:
    """Every installed Wallpaper Engine wallpaper, by title: HalOS's Steam libraries first, then the Steam
    libraries on the Windows drives mounted at ``windows`` (their items say "source": "windows")."""
    seen, out = set(), []
    libs = [(lib, "halos") for lib in libraries(home)]
    libs += [(lib, "windows") for lib in windows_libraries(windows or []) if lib not in {l for l, _ in libs}]
    places = [(lib / "steamapps/workshop/content" / APP_ID, source, False) for lib, source in libs]
    places += [(folder, "migrated", named) for folder, named in migrated_dirs(Path(home or Path.home()))]
    for content, source, named in places:
        try:
            dirs = sorted(content.iterdir())
        except OSError:
            continue
        for d in dirs:
            it = read_item(d, named) if d.is_dir() and not d.is_symlink() else None
            if it and it["id"] not in seen:
                seen.add(it["id"])
                out.append({**it, "source": source})
    return sorted(out, key=lambda i: i["title"].lower())


def find(query: str, found: List[dict]) -> Optional[dict]:
    """An item by workshop id, or the first whose title has every word of ``query``."""
    q = (query or "").strip().lower()
    for it in found:
        if it["id"] == q:
            return it
    words = q.split()
    return next((it for it in found if all(w in it["title"].lower() for w in words)), None)


# ---------------------------------------------------------------------- what can show them
def _plugin_dirs(home: Path) -> List[Path]:
    return [Path("/usr/share/plasma/wallpapers"), home / ".local/share/plasma/wallpapers"]


def plugin_installed(plugin: str, home: Optional[Path] = None) -> bool:
    home = Path(home or Path.home())
    return any((d / plugin / "metadata.json").is_file() or (d / plugin / "metadata.desktop").is_file()
               for d in _plugin_dirs(home))


def video_plugin(home: Optional[Path] = None) -> str:
    return next((p for p in VIDEO_PLUGINS if plugin_installed(p, home)), "")


def support(home: Optional[Path] = None, which: Callable = shutil.which) -> str:
    """"kde", "cli" or "" (nothing that can show a scene or web wallpaper)."""
    if plugin_installed(KDE_PLUGIN, home):
        return "kde"
    return "cli" if which(CLI) else ""


def missing_text() -> str:
    return ("Wallpaper Engine wallpapers need the Wallpaper Engine plugin for Plasma (or linux-wallpaperengine). "
            "Choose Install support to add it.")


# ---------------------------------------------------------------------- applying
def kde_script(item: dict, screen: int = -1) -> str:
    from ui.settings_pages.wallpaper import desktop_script
    src = item["file"] or item["dir"]
    values = {"WallpaperWorkShopId": item["id"], "WallpaperSource": Path(src).as_uri(),
              "SteamLibraryPath": Path(item.get("library") or Path(item["dir"]).parent).as_posix()}
    try:
        return desktop_script(KDE_PLUGIN, values, screen)
    except ValueError:
        raise EngineError("This wallpaper's folder has a character in its path that Plasma's script can't take.")


def video_script(path: Path, plugin: str, screen: int = -1) -> str:
    from ui.settings_pages.wallpaper import desktop_script
    uri = Path(path).as_uri()
    # 🔧 unverified on real HalOS: the key differs between versions of the plugin, so both are written.
    return desktop_script(plugin, {"VideoUrls": uri, "VideoWallpaperBackgroundVideo": uri}, screen)


def monitors(run: Callable = subprocess.run) -> List[str]:
    """Connected monitor names (DP-1, HDMI-A-1 ...) from kscreen-doctor."""
    try:
        r = run(["kscreen-doctor", "-j"], capture_output=True, text=True, timeout=10)
        outs = json.loads(r.stdout or "{}").get("outputs", [])
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        return []
    return [o["name"] for o in outs if isinstance(o, dict) and o.get("enabled") and isinstance(o.get("name"), str)]


def cli_argv(item: dict, screens: List[str]) -> List[str]:
    argv = [CLI]
    for s in screens:
        argv += ["--screen-root", s, "--bg", str(item["dir"])]
    return argv


def _plasma(script: str, run) -> None:
    from ui.settings_pages.wallpaper import run_script
    why = run_script(script, run)
    if why:
        raise EngineError(why)


def apply_video(path: Path, screen: int = -1, run: Callable = subprocess.run, home: Optional[Path] = None) -> str:
    plugin = video_plugin(home)
    if not plugin:
        raise EngineError("Video wallpapers need a video wallpaper plugin for Plasma (Smart Video Wallpaper "
                          "Reborn, from Get New Wallpapers).")
    _plasma(video_script(path, plugin, screen), run)
    return "Video wallpaper applied."


def apply(item: dict, screen: int = -1, run: Callable = subprocess.run, popen: Callable = subprocess.Popen,
          home: Optional[Path] = None, which: Callable = shutil.which) -> str:
    """Show ``item`` on the desktop with the best thing installed. Returns what happened; raises EngineError."""
    how = support(home, which)
    if how == "kde":
        _plasma(kde_script(item, screen), run)
        log.info("wallpaper_engine.applied kde %s", item["id"])
        return f"{item['title']} is your wallpaper now."
    if item["type"] == "video" and item["file"] and video_plugin(home):
        return apply_video(item["file"], screen, run, home)
    if how == "cli":
        screens = monitors(run)
        if not screens:
            raise EngineError("I couldn't find the monitor names to give linux-wallpaperengine.")
        if screen >= 0:
            screens = screens[screen:screen + 1] or screens
        try:
            run(["pkill", "-x", CLI], capture_output=True, timeout=5)     # one at a time
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            # ponytail: not restarted at login; an autostart entry is the upgrade if people use the fallback.
            popen(cli_argv(item, screens), start_new_session=True, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL)
        except OSError as e:
            raise EngineError(f"linux-wallpaperengine couldn't start: {e}")
        log.info("wallpaper_engine.applied cli %s", item["id"])
        return f"{item['title']} is playing through linux-wallpaperengine."
    raise EngineError(missing_text())


# ---------------------------------------------------------------------- installing support
def install_steps():
    from core.saintos_apps import Step
    return [Step("Wallpaper Engine for Plasma (AUR)", ["paru", "-S", "--needed", "--noconfirm", "--skipreview",
                                                       "--sudo", "pkexec", AUR_PACKAGE], ["wallpaper-engine"],
                 needs_admin=True)]


def install_support(on_line: Callable[[str], None] = log.info, on_wait: Optional[Callable[[str], None]] = None,
                    errors: Optional[Dict[str, str]] = None) -> bool:
    """Install the Plasma plugin through the package queue (waits its turn and for pacman). True when it worked;
    Plasma picks a new wallpaper plugin up after plasmashell restarts (logging out and in)."""
    from core import pkg_queue
    errors = {} if errors is None else errors
    ok = pkg_queue.run_plan(install_steps(), on_wait=on_wait, on_line=on_line, errors=errors).get("wallpaper-engine",
                                                                                                    False)
    log.info("wallpaper_engine.install_support ok=%s %s", ok, errors.get("wallpaper-engine", ""))
    return ok
