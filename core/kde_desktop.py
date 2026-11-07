"""
core/kde_desktop.py

HalOS's desktop behaviour in KDE's own config files: the screen edge that opens SAINT's overlay, virtual
desktops, the mouse wheel. Pure logic with the commands injectable (``run``); nothing here goes through a shell.

Reads parse the KConfig files directly (user file over /etc/xdg). Writes go through kwriteconfig6, then KWin
is told over D-Bus so nothing needs a new session:

    kwinrc [Script-saint-shell]  OverlayEdge, OverlayEdgeDelayMs, CloseBurst   -> unload + start the script
    kwinrc [MouseBindings]       CommandAllWheel                               -> /KWin reconfigure
    /VirtualDesktopManager       createDesktop, removeDesktop                  -> live
    plasma-org.kde.plasma.desktop-appletsrc [ActionPlugins][0]                 -> plasmashell restarts (2 s)
"""

import logging
import os
import re
import shutil
import subprocess
import time
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("saint.kde_desktop")

KWINRC = "kwinrc"
APPLETSRC = "plasma-org.kde.plasma.desktop-appletsrc"
SHELL_GROUP = "Script-saint-shell"

EDGES = {"off": "Off (Alt+` only)", "top": "Top edge", "topright": "Top right corner", "right": "Right edge",
         "bottomright": "Bottom right corner", "bottom": "Bottom edge", "bottomleft": "Bottom left corner",
         "left": "Left edge", "topleft": "Top left corner"}
MAX_EDGE_DELAY_MS = 3000
MAX_DESKTOPS = 20

WHEEL_ON = "Previous/Next Desktop"       # KWin's Options::mouseWheelCommand (it compares case-insensitively)
WHEEL_OFF = "Nothing"
BACKGROUND_WHEEL_KEY = "wheel:Vertical;NoModifier"
BACKGROUND_WHEEL_PLUGIN = "org.kde.switchdesktop"

# (component, action, keys as they should be, KWin's/Plasma's registered default). KDE resets an entry whose
# default doesn't match what the owner registers, so these are its exact strings. A tab separates two keys.
_DESKTOP_KEYS = [("kwin", f"Switch to Desktop {n}", f"Meta+{n}\tCtrl+F{n}", f"Ctrl+F{n}") for n in range(1, 5)]
_ARROWS = [("kwin", "Switch One Desktop to the Left", "Meta+Ctrl+Left", "Meta+Ctrl+Left"),
           ("kwin", "Switch One Desktop to the Right", "Meta+Ctrl+Right", "Meta+Ctrl+Right")]
# Plasma's task manager owns Meta+1..4 by default; it has to let go or the desktop shortcuts never fire.
_RELEASED = [("plasmashell", f"activate task manager entry {n}", "none", f"Meta+{n}") for n in range(1, 5)]
SHORTCUT_ENTRIES = _ARROWS + _DESKTOP_KEYS + _RELEASED
_PLASMASHELL_FRIENDLY = "Activate Task Manager Entry {}"

SHORTCUTS_SHOWN = [("Ctrl+Meta+Left / Right", "Previous / next desktop"),
                   ("Meta+1 ... Meta+4", "Go to desktop 1 ... 4"),
                   ("Ctrl+F1 ... Ctrl+F4", "Go to desktop 1 ... 4 (KDE's own)"),
                   ("Ctrl+Alt+mouse wheel", "Previous / next desktop (KDE's own)")]


def shortcut_line(action: str, keys: str, default: str, friendly: str = "") -> str:
    """One kglobalshortcutsrc value: active,default,friendly name (tabs in the file are written \\t)."""
    return f"{keys.replace(chr(9), chr(92) + 't')},{default},{friendly or action}"


def friendly_name(action: str) -> str:
    m = re.fullmatch(r"activate task manager entry (\d)", action)
    return _PLASMASHELL_FRIENDLY.format(m.group(1)) if m else action


def skel_shortcut_lines() -> Dict[str, List[str]]:
    """What the image's /etc/skel/.config/kglobalshortcutsrc has to hold, by component (tests compare it)."""
    out: Dict[str, List[str]] = {}
    for component, action, keys, default in SHORTCUT_ENTRIES:
        out.setdefault(component, []).append(f"{action}={shortcut_line(action, keys, default, friendly_name(action))}")
    return out


# ------------------------------------------------------------------ commands
def _run(argv: List[str]) -> Tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        log.info("kde.command_failed %s: %s", argv[0], e)
        return False, str(e)
    if r.returncode != 0:
        log.info("kde.command_failed %s: %s", argv[:4], (r.stderr or "").strip()[:200])
    return r.returncode == 0, (r.stdout if r.returncode == 0 else r.stderr or "").strip()


def qdbus(which: Callable = shutil.which) -> str:
    return next((n for n in ("qdbus6", "qdbus-qt6", "qdbus") if which(n)), "qdbus6")


def available(which: Callable = shutil.which) -> bool:
    return bool(which("kwriteconfig6"))


# ------------------------------------------------------------------ KConfig files
def _unescape(value: str) -> str:
    table = {"\\": "\\", "n": "\n", "t": "\t", "r": "\r", "s": " "}
    return re.sub(r"\\(.)", lambda m: table.get(m.group(1), m.group(0)), value)


def parse_kconfig(text: str) -> Dict[str, Dict[str, str]]:
    """KConfig text -> {group: {key: value}}; nested groups are "A/B". Localised keys are skipped."""
    groups: Dict[str, Dict[str, str]] = {}
    cur: Dict[str, str] = groups.setdefault("", {})
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = groups.setdefault("/".join(re.findall(r"\[([^\]]*)\]", line)), {})
        elif "=" in line:
            key, value = line.split("=", 1)
            key = re.sub(r"\[\$[a-z]+\]$", "", key.strip())
            if "[" not in key:
                cur[key] = _unescape(value.strip())
    return groups


def config_home() -> str:
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def read_config(name: str, dirs: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
    """A KConfig file as KDE sees it: the user's over /etc/xdg's."""
    merged: Dict[str, Dict[str, str]] = {}
    for d in reversed(dirs if dirs is not None else [config_home(), "/etc/xdg"]):
        try:
            with open(os.path.join(d, name), encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        for group, values in parse_kconfig(text).items():
            merged.setdefault(group, {}).update(values)
    return merged


def read_value(name: str, group: str, key: str, default: str = "", dirs: Optional[List[str]] = None) -> str:
    return read_config(name, dirs).get(group, {}).get(key, default)


def write_value(name: str, group: str, key: str, value: Optional[str], run: Callable = _run) -> bool:
    """kwriteconfig6; ``None`` deletes the key. "A/B" is a nested group."""
    groups: List[str] = []
    for g in group.split("/"):
        groups += ["--group", g]
    tail = ["--delete"] if value is None else [value]
    return run(["kwriteconfig6", "--file", name, *groups, "--key", key, *tail])[0]


# ------------------------------------------------------------------ KWin reloads
def reconfigure_kwin(run: Callable = _run) -> bool:
    return run([qdbus(), "org.kde.KWin", "/KWin", "reconfigure"])[0]


def reload_shell_script(run: Callable = _run, sleep: Callable = time.sleep) -> bool:
    """Make the running saint-shell script read its settings again, the way Plasma's KWin Scripts page does it.
    Blocks for a moment (KWin rereads kwinrc 200 ms after reconfigure), so call it off the UI thread."""
    reconfigure_kwin(run)
    sleep(0.4)
    bus = qdbus()
    run([bus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", "saint-shell"])
    return run([bus, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start"])[0]


# ------------------------------------------------------------------ the overlay's screen edge
def overlay_edge(dirs: Optional[List[str]] = None) -> Tuple[str, int]:
    """(edge, hover delay in ms). A fresh install has no entry: off."""
    edge = read_value(KWINRC, SHELL_GROUP, "OverlayEdge", "off", dirs).strip().lower()
    try:
        delay = int(read_value(KWINRC, SHELL_GROUP, "OverlayEdgeDelayMs", "0", dirs))
    except ValueError:
        delay = 0
    return (edge if edge in EDGES else "off"), max(0, min(delay, MAX_EDGE_DELAY_MS))


def set_overlay_edge(edge: str, delay_ms: int = 0, run: Callable = _run) -> bool:
    """Write the setting. The caller then runs reload_shell_script (off the UI thread)."""
    if edge not in EDGES:
        raise ValueError(f"unknown screen edge: {edge!r}")
    delay = max(0, min(int(delay_ms), MAX_EDGE_DELAY_MS))
    return write_value(KWINRC, SHELL_GROUP, "OverlayEdge", edge, run) and \
        write_value(KWINRC, SHELL_GROUP, "OverlayEdgeDelayMs", str(delay), run)


# ------------------------------------------------------------------ virtual desktops
_VDM = ["org.kde.KWin", "/VirtualDesktopManager"]
_VDM_IFACE = "org.kde.KWin.VirtualDesktopManager"
_DESKTOP_ROW = re.compile(r'\(uss\)\s*(\d+),\s*"([^"]*)",\s*"([^"]*)"')


def parse_desktops(literal: str) -> List[Tuple[int, str, str]]:
    """``qdbus --literal`` output of the desktops property -> [(position, id, name)]."""
    return sorted((int(p), i, n) for p, i, n in _DESKTOP_ROW.findall(literal))


def desktops(run: Callable = _run) -> List[Tuple[int, str, str]]:
    ok, out = run([qdbus(), "--literal", *_VDM, "org.freedesktop.DBus.Properties.Get", _VDM_IFACE, "desktops"])
    return parse_desktops(out) if ok else []


def set_desktop_count(count: int, run: Callable = _run) -> Tuple[bool, str]:
    """Add at the end or remove from the end, live. KWin moves windows off a removed desktop and saves the count."""
    want = max(1, min(int(count), MAX_DESKTOPS))
    have = desktops(run)
    if not have:
        return False, "KWin didn't answer, so the desktops weren't changed."
    bus = qdbus()
    ok = True
    for n in range(len(have), want):
        ok = run([bus, *_VDM, f"{_VDM_IFACE}.createDesktop", str(n), f"Desktop {n + 1}"])[0] and ok
    for _pos, desktop_id, _name in reversed(have[want:]):
        ok = run([bus, *_VDM, f"{_VDM_IFACE}.removeDesktop", desktop_id])[0] and ok
    return ok, (f"{want} desktops." if ok else "KWin refused part of that change.")


def meta_wheel_on(dirs: Optional[List[str]] = None) -> bool:
    return read_value(KWINRC, "MouseBindings", "CommandAllWheel", WHEEL_OFF, dirs).lower() == WHEEL_ON.lower()


def set_meta_wheel(on: bool, run: Callable = _run) -> bool:
    ok = write_value(KWINRC, "MouseBindings", "CommandAllWheel", WHEEL_ON if on else WHEEL_OFF, run)
    return ok and reconfigure_kwin(run)


def background_wheel_on(dirs: Optional[List[str]] = None) -> bool:
    return read_value(APPLETSRC, "ActionPlugins/0", BACKGROUND_WHEEL_KEY, "", dirs) == BACKGROUND_WHEEL_PLUGIN


def set_background_wheel(on: bool, run: Callable = _run) -> bool:
    """Plasma's Mouse Actions for the desktop, read when plasmashell starts: it restarts, windows stay."""
    ok = write_value(APPLETSRC, "ActionPlugins/0", BACKGROUND_WHEEL_KEY, BACKGROUND_WHEEL_PLUGIN if on else None, run)
    return ok and run(["systemctl", "--user", "restart", "plasma-plasmashell.service"])[0]


def write_shortcuts(run: Callable = _run) -> bool:
    """HalOS's desktop shortcuts for an account older than them (new accounts get /etc/skel's file). KDE's
    shortcut service reads this file when the session starts, so these work from the next sign-in."""
    ok = True
    for component, action, keys, default in SHORTCUT_ENTRIES:
        value = f"{keys},{default},{friendly_name(action)}"
        ok = write_value("kglobalshortcutsrc", component, action, value, run) and ok
    return ok
