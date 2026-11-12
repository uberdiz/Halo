"""
core/actions/sets/settings.py

System settings as actions. On HalOS (Linux) they drive the KDE/Plasma tools
directly - kscreen-doctor, kwriteconfig6, plasma-apply-colorscheme, wpctl,
pactl, powerprofilesctl, timedatectl - through core/actions/proc.py (argument
lists only). On Windows the sound and brightness actions reuse SAINT's
existing modules/desktop/system_controls.py.

Every action reads the current value first and returns it as the undo token.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from core.config import config

from .. import proc
from ..registry import RISKY, SAFE, Action, ActionError, ActionResult, P, platform_name

LINUX = ("linux",)


def ok(message: str, undo: Optional[Dict[str, Any]] = None, **data) -> ActionResult:
    return ActionResult(True, message=message, data=data, undo=undo)


def _is_windows() -> bool:
    return platform_name() == "windows"


# ---------------------------------------------------------------------- #
# KConfig helpers
# ---------------------------------------------------------------------- #
def kread(file: str, groups: List[str], key: str, default: str = "") -> str:
    argv = ["kreadconfig6", "--file", file]
    for g in groups:
        argv += ["--group", g]
    return proc.try_run(argv + ["--key", key], default) or default


def kwrite(file: str, groups: List[str], key: str, value: Optional[str], type_: str = "", notify: bool = False):
    """Write (or with ``value=None`` delete) one KConfig key."""
    argv = ["kwriteconfig6", "--file", file]
    for g in groups:
        argv += ["--group", g]
    argv += ["--key", key]
    if notify:
        argv.append("--notify")
    if value is None:
        argv.append("--delete")
    else:
        if type_:
            argv += ["--type", type_]
        argv.append(str(value))
    proc.run(argv)


def _kwin_reconfigure():
    proc.try_run([proc.qdbus(), "org.kde.KWin", "/KWin", "reconfigure"])


def _bool(text: str) -> bool:
    return str(text).strip().lower() in ("true", "1", "yes", "on")


# ---------------------------------------------------------------------- #
# Display: scale, resolution, night light, brightness
# ---------------------------------------------------------------------- #
_OUTPUT = r"[A-Za-z0-9_-]{1,32}"


def _outputs() -> List[Dict[str, Any]]:
    try:
        data = json.loads(proc.run(["kscreen-doctor", "-j"]))
        return [o for o in data.get("outputs", []) if o.get("enabled", True) and o.get("name")]
    except (ValueError, AttributeError):
        raise ActionError("I couldn't read the display setup from kscreen-doctor.", "FAILED")


def _output(name: str = "") -> Dict[str, Any]:
    outs = _outputs()
    if not outs:
        raise ActionError("I can't find a connected display.", "NOT_FOUND")
    if name:
        for o in outs:
            if o["name"].lower() == name.lower():
                return o
        raise ActionError(f"There's no display called {name} (I see {', '.join(o['name'] for o in outs)}).",
                          "NOT_FOUND")
    return sorted(outs, key=lambda o: o.get("priority") or 99)[0]


def _set_scale(p):
    out = _output(p.get("output", ""))
    scale = round(float(p["scale"]), 2)
    proc.run(["kscreen-doctor", f"output.{out['name']}.scale.{scale:g}"])
    return ok(f"Display scale on {out['name']} is now {round(scale * 100)}%.",
              undo={"output": out["name"], "scale": out.get("scale", 1)}, output=out["name"], scale=scale)


def _undo_scale(t):
    if not re.fullmatch(_OUTPUT, str(t["output"])):
        raise ActionError("That display name isn't valid.", "INVALID")
    proc.run(["kscreen-doctor", f"output.{t['output']}.scale.{float(t['scale']):g}"])
    return f"Display scale is back to {round(float(t['scale']) * 100)}%."


def _mode_label(m: Dict[str, Any]) -> str:
    size = m.get("size") or {}
    return f"{size.get('width')}x{size.get('height')}"


def _set_resolution(p):
    out = _output(p.get("output", ""))
    want = f"{p['width']}x{p['height']}"
    modes = [m for m in out.get("modes", []) if _mode_label(m) == want]
    if not modes:
        have = sorted({_mode_label(m) for m in out.get("modes", [])}, key=lambda s: -int(s.split("x")[0] or 0))
        raise ActionError(f"{out['name']} doesn't offer {want}. It offers: {', '.join(have[:8]) or 'nothing'}.",
                          "UNSUPPORTED")
    refresh = p.get("refresh")
    mode = (min(modes, key=lambda m: abs(float(m.get("refreshRate", 0)) - refresh)) if refresh
            else max(modes, key=lambda m: float(m.get("refreshRate", 0))))
    proc.run(["kscreen-doctor", f"output.{out['name']}.mode.{mode['id']}"])
    return ok(f"{out['name']} is now {want} at {round(float(mode.get('refreshRate', 0)))} Hz.",
              undo={"output": out["name"], "mode": str(out.get("currentModeId", ""))},
              output=out["name"], mode=str(mode["id"]))


def _undo_resolution(t):
    if not t.get("mode") or not re.fullmatch(_OUTPUT, str(t["output"])) or \
            not re.fullmatch(r"[A-Za-z0-9@x._-]{1,40}", str(t["mode"])):
        raise ActionError("I don't know what the resolution was before.", "NO_UNDO")
    proc.run(["kscreen-doctor", f"output.{t['output']}.mode.{t['mode']}"])
    return "The resolution is back to what it was."


def _night_light(p):
    was = _bool(kread("kwinrc", ["NightColor"], "Active", "false"))
    was_temp = kread("kwinrc", ["NightColor"], "NightTemperature", "")
    kwrite("kwinrc", ["NightColor"], "Active", "true" if p["on"] else "false", "bool")
    if p.get("temperature"):
        kwrite("kwinrc", ["NightColor"], "NightTemperature", str(p["temperature"]))
    _kwin_reconfigure()
    return ok(f"Night light is {'on' if p['on'] else 'off'}.", undo={"on": was, "temperature": was_temp})


def _undo_night_light(t):
    kwrite("kwinrc", ["NightColor"], "Active", "true" if t.get("on") else "false", "bool")
    if str(t.get("temperature") or "").isdigit():
        kwrite("kwinrc", ["NightColor"], "NightTemperature", str(t["temperature"]))
    _kwin_reconfigure()
    return f"Night light is {'on' if t.get('on') else 'off'} again."


_BRIGHTNESS_DBUS = ["org.kde.Solid.PowerManagement", "/org/kde/Solid/PowerManagement/Actions/BrightnessControl"]
_BRIGHTNESS_IFACE = "org.kde.Solid.PowerManagement.Actions.BrightnessControl"


def _brightness_now() -> Optional[int]:
    if proc.have("brightnessctl"):
        m = re.search(r"(\d+)%", proc.try_run(["brightnessctl", "-m"]))
        return int(m.group(1)) if m else None
    q = [proc.qdbus(), *_BRIGHTNESS_DBUS]
    cur, top = proc.try_run(q + [f"{_BRIGHTNESS_IFACE}.brightness"]), proc.try_run(
        q + [f"{_BRIGHTNESS_IFACE}.brightnessMax"])
    return round(int(cur) * 100 / int(top)) if cur.isdigit() and top.isdigit() and int(top) else None


def _brightness_set(percent: int):
    percent = max(1, min(100, int(percent)))            # 0 can leave a laptop screen black
    if proc.have("brightnessctl"):
        proc.run(["brightnessctl", "set", f"{percent}%"])
        return
    q = [proc.qdbus(), *_BRIGHTNESS_DBUS]
    top = proc.try_run(q + [f"{_BRIGHTNESS_IFACE}.brightnessMax"])
    if not top.isdigit() or not int(top):
        raise ActionError("This screen doesn't let the system change its brightness; use the monitor's own "
                          "buttons.", "UNSUPPORTED")
    proc.run(q + [f"{_BRIGHTNESS_IFACE}.setBrightness", str(round(int(top) * percent / 100))])


def _brightness(p):
    if _is_windows():
        from modules.desktop import system_controls as sc
        return ok(f"Brightness is {sc.brightness(percent=p['percent'])['percent']}%.")
    was = _brightness_now()
    _brightness_set(p["percent"])
    return ok(f"Brightness is {max(1, p['percent'])}%.", undo=None if was is None else {"percent": was})


def _undo_brightness(t):
    _brightness_set(int(t["percent"]))
    return f"Brightness is back to {int(t['percent'])}%."


# ---------------------------------------------------------------------- #
# Appearance: dark / light, wallpaper colour, text size
# ---------------------------------------------------------------------- #
_SCHEME = r"[A-Za-z0-9_.-]{1,64}"


def _scheme_for(mode: str) -> str:
    name = (config.get("actions.color_schemes", {}) or {}).get(mode) or \
        {"dark": "BreezeDark", "light": "BreezeLight"}[mode]
    if not re.fullmatch(_SCHEME, name):
        raise ActionError(f"The {mode} colour scheme name in the settings isn't valid.", "INVALID")
    return name


def _theme(p):
    scheme = _scheme_for(p["mode"])
    was = kread("kdeglobals", ["General"], "ColorScheme", "")
    proc.run(["plasma-apply-colorscheme", scheme])
    return ok(f"Switched to the {p['mode']} theme.", undo={"scheme": was} if was else None, scheme=scheme)


def _undo_theme(t):
    if not re.fullmatch(_SCHEME, str(t.get("scheme", ""))):
        raise ActionError("I don't know which theme was in use before.", "NO_UNDO")
    proc.run(["plasma-apply-colorscheme", t["scheme"]])
    return "The theme is back to what it was."


_COLOR = r"#[0-9a-fA-F]{6}"
_PLUGIN = r"[A-Za-z0-9_.]{1,80}"
_SHELL = ["org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript"]


def _wallpaper_script(plugin: str, color: str = "") -> str:
    # Only values that passed the regexes above are ever put into this script.
    lines = ["var out = [];", "desktops().forEach(function (d) {",
             "  d.currentConfigGroup = ['Wallpaper', 'org.kde.color', 'General'];",
             "  out.push(d.wallpaperPlugin + '|' + d.readConfig('Color'));",
             f"  d.wallpaperPlugin = '{plugin}';"]
    if color:
        lines += ["  d.currentConfigGroup = ['Wallpaper', 'org.kde.color', 'General'];",
                  f"  d.writeConfig('Color', '{color}');"]
    return "\n".join(lines + ["});", "print(out[0]);"])


def _wallpaper_color(p):
    color = p["color"].lower()
    before = proc.run([proc.qdbus(), *_SHELL, _wallpaper_script("org.kde.color", color)])
    plugin, _, old = before.strip().partition("|")
    undo = {"plugin": plugin, "color": old} if re.fullmatch(_PLUGIN, plugin) else None
    return ok(f"The wallpaper is now a solid colour ({color}).", undo=undo, color=color)


def _undo_wallpaper_color(t):
    plugin, color = str(t.get("plugin", "")), str(t.get("color", ""))
    if not re.fullmatch(_PLUGIN, plugin):
        raise ActionError("I don't know what the wallpaper was before.", "NO_UNDO")
    proc.run([proc.qdbus(), *_SHELL, _wallpaper_script(plugin, color if re.fullmatch(_COLOR, color) else "")])
    return "The wallpaper is back to what it was."


_FONT_KEYS = ("font", "menuFont", "toolBarFont")
_FONT_DEFAULT = "Noto Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"


def _fonts_changed():
    proc.try_run(["dbus-send", "--session", "--type=signal", "/KGlobalSettings",
                  "org.kde.KGlobalSettings.notifyChange", "int32:2", "int32:0"])


def _text_size(p):
    current = {k: kread("kdeglobals", ["General"], k, "") for k in _FONT_KEYS}
    base = (current["font"] or _FONT_DEFAULT).split(",")
    now = int(base[1]) if len(base) > 1 and base[1].isdigit() else 10
    if p.get("size") is None and not p.get("step"):
        raise ActionError("say a size in points, or a step such as 1 or -1", "INVALID_PARAMS")
    size = max(6, min(28, p["size"] if p.get("size") is not None else now + p["step"]))
    for key in _FONT_KEYS:
        parts = (current[key] or _FONT_DEFAULT).split(",")
        if len(parts) < 2:
            parts = _FONT_DEFAULT.split(",")
        parts[1] = str(size)
        kwrite("kdeglobals", ["General"], key, ",".join(parts))
    _fonts_changed()
    return ok(f"Text size is now {size} pt (it was {now}). Apps pick it up when they next open.",
              undo={"fonts": current}, size=size)


def _undo_text_size(t):
    for key in _FONT_KEYS:
        value = (t.get("fonts") or {}).get(key) or None
        kwrite("kdeglobals", ["General"], key, value)
    _fonts_changed()
    return "Text size is back to what it was."


# ---------------------------------------------------------------------- #
# Sound
# ---------------------------------------------------------------------- #
_SINK, _SOURCE = "@DEFAULT_AUDIO_SINK@", "@DEFAULT_AUDIO_SOURCE@"


def _wp_state(target: str) -> Dict[str, Any]:
    text = proc.try_run(["wpctl", "get-volume", target])
    m = re.search(r"([0-9]*\.?[0-9]+)", text)
    return {"percent": round(float(m.group(1)) * 100) if m else None, "muted": "MUTED" in text}


def _volume(p):
    if _is_windows():
        from modules.desktop import system_controls as sc
        was = sc.system_volume().get("percent")
        sc.system_volume(percent=p["percent"])
        return ok(f"Volume is {p['percent']}%.", undo=None if was is None else {"percent": was})
    was = _wp_state(_SINK)["percent"]
    proc.run(["wpctl", "set-volume", "-l", "1.0", _SINK, f"{p['percent'] / 100:.2f}"])
    return ok(f"Volume is {p['percent']}%.", undo=None if was is None else {"percent": was})


def _undo_volume(t):
    _volume({"percent": max(0, min(100, int(t["percent"])))})
    return f"Volume is back to {int(t['percent'])}%."


def _mute(p):
    mic = p.get("device", "output") == "mic"
    what = "The microphone" if mic else "Sound"
    if _is_windows():
        from modules.desktop import system_controls as sc
        r = sc.mic_mute(p["state"]) if mic else sc.system_volume(mute=p["state"])
        muted = bool(r.get("muted"))
        return ok(f"{what} is {'muted' if muted else 'on'}.", undo={"device": p.get("device", "output"),
                                                                    "state": "off" if muted else "on"})
    target = _SOURCE if mic else _SINK
    was = _wp_state(target)["muted"]
    proc.run(["wpctl", "set-mute", target, {"on": "1", "off": "0", "toggle": "toggle"}[p["state"]]])
    muted = {"on": True, "off": False, "toggle": not was}[p["state"]]
    return ok(f"{what} is {'muted' if muted else 'on'}.",
              undo={"device": "mic" if mic else "output", "state": "on" if was else "off"})


def _undo_mute(t):
    return _mute({"device": t.get("device", "output"), "state": "on" if t.get("state") == "on" else "off"}).message


def _sinks() -> List[Dict[str, str]]:
    try:
        rows = json.loads(proc.run(["pactl", "-f", "json", "list", "sinks"]))
        return [{"name": r["name"], "label": r.get("description") or r["name"]} for r in rows if r.get("name")]
    except (ValueError, TypeError, KeyError):
        out = proc.run(["pactl", "list", "short", "sinks"])
        names = [ln.split("\t")[1] for ln in out.splitlines() if ln.count("\t")]
        return [{"name": n, "label": n} for n in names]


def _match_sink(spoken: str, sinks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    labels = [s["label"] for s in sinks]
    try:                                    # SAINT's existing "headphones"/"speakers"/"the monitor" matcher
        from modules.desktop.system_controls import match_output
        hits = match_output(spoken, labels)
    except Exception:
        words = re.findall(r"[a-z0-9]+", spoken.lower())
        hits = [n for n in labels if all(w in n.lower() for w in words)]
    return [s for s in sinks if s["label"] in hits or s["name"] == spoken]


def _sound_output(p):
    if _is_windows():
        from modules.desktop import system_controls as sc
        return ok(f"Sound now plays through {sc.output_device(p['name'])['device']}.")
    sinks = _sinks()
    hits = _match_sink(p["name"], sinks)
    if not hits:
        raise ActionError(f"I can't find an output called {p['name']}. I see: "
                          f"{', '.join(s['label'] for s in sinks) or 'none'}.", "NOT_FOUND")
    was = proc.try_run(["pactl", "get-default-sink"])
    proc.run(["pactl", "set-default-sink", hits[0]["name"]])
    return ok(f"Sound now plays through {hits[0]['label']}.", undo={"sink": was} if was else None,
              sink=hits[0]["name"])


def _undo_sound_output(t):
    if not re.fullmatch(r"[A-Za-z0-9_.:+-]{1,200}", str(t.get("sink", ""))):
        raise ActionError("I don't know which output was in use before.", "NO_UNDO")
    proc.run(["pactl", "set-default-sink", t["sink"]])
    return "Sound is back on the output it used before."


# ---------------------------------------------------------------------- #
# Default apps
# ---------------------------------------------------------------------- #
DEFAULT_APP_KINDS = {
    "browser": ["x-scheme-handler/http", "x-scheme-handler/https", "text/html"],
    "mail": ["x-scheme-handler/mailto"],
    "files": ["inode/directory"],
    "text": ["text/plain"],
    "pdf": ["application/pdf"],
    "images": ["image/png", "image/jpeg", "image/webp", "image/gif"],
    "video": ["video/mp4", "video/x-matroska", "video/webm"],
    "music": ["audio/mpeg", "audio/flac", "audio/ogg"],
}
_DESKTOP = r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,127}\.desktop"


def _desktop_exists(app: str) -> bool:
    home = os.path.expanduser("~")
    dirs = [os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share"), "applications"),
            os.path.join(home, ".local/share/flatpak/exports/share/applications"),
            "/var/lib/flatpak/exports/share/applications", "/usr/local/share/applications",
            "/usr/share/applications"]
    return any(os.path.isfile(os.path.join(d, app)) for d in dirs)


def _desktop_id(app: str) -> str:
    app = app.strip()
    if not app.endswith(".desktop"):
        app += ".desktop"
    if not re.fullmatch(_DESKTOP, app):
        raise ActionError(f"“{app}” isn't an app id (want something like firefox.desktop).", "INVALID_PARAMS")
    return app


def _default_app(p):
    app = _desktop_id(p["app"])
    if not _desktop_exists(app):
        raise ActionError(f"{app} isn't installed.", "NOT_FOUND")
    mimes = DEFAULT_APP_KINDS[p["kind"]]
    before = {m: proc.try_run(["xdg-mime", "query", "default", m]) for m in mimes}
    proc.run(["xdg-mime", "default", app, *mimes])
    return ok(f"{app[:-8]} now opens {p['kind']}.", undo={"before": before}, app=app)


def _undo_default_app(t):
    known = {m for ms in DEFAULT_APP_KINDS.values() for m in ms}
    done = 0
    for mime, app in (t.get("before") or {}).items():
        if mime in known and re.fullmatch(_DESKTOP, str(app)):
            proc.run(["xdg-mime", "default", app, mime])
            done += 1
    if not done:
        raise ActionError("There was no default app set before, so there's nothing to go back to.", "NO_UNDO")
    return "The default app is back to what it was."


# ---------------------------------------------------------------------- #
# Power profile, sleep and lock timeouts
# ---------------------------------------------------------------------- #
PROFILES = ["power-saver", "balanced", "performance"]


def _power_profile(p):
    was = proc.try_run(["powerprofilesctl", "get"])
    proc.run(["powerprofilesctl", "set", p["profile"]])
    return ok(f"Power profile is now {p['profile'].replace('-', ' ')}.",
              undo={"profile": was} if was in PROFILES else None)


def _undo_power_profile(t):
    if t.get("profile") not in PROFILES:
        raise ActionError("I don't know which power profile was in use before.", "NO_UNDO")
    proc.run(["powerprofilesctl", "set", t["profile"]])
    return f"Power profile is back to {t['profile'].replace('-', ' ')}."


_POWER_GROUPS = {"plugged_in": ["AC"], "battery": ["Battery"], "both": ["AC", "Battery"]}


def _powerdevil_reload():
    proc.try_run([proc.qdbus(), "org.kde.Solid.PowerManagement", "/org/kde/Solid/PowerManagement",
                  "org.kde.Solid.PowerManagement.reparseConfiguration"])
    proc.try_run([proc.qdbus(), "org.kde.Solid.PowerManagement", "/org/kde/Solid/PowerManagement",
                  "org.kde.Solid.PowerManagement.refreshStatus"])


def _sleep_timeout(p):
    before = {}
    for profile in _POWER_GROUPS[p.get("when", "both")]:
        group = [profile, "SuspendAndShutdown"]
        before[profile] = {"action": kread("powerdevilrc", group, "AutoSuspendAction", ""),
                           "seconds": kread("powerdevilrc", group, "AutoSuspendIdleTimeoutSec", "")}
        if p["minutes"] == 0:
            kwrite("powerdevilrc", group, "AutoSuspendAction", "0")
        else:
            kwrite("powerdevilrc", group, "AutoSuspendAction", "1")
            kwrite("powerdevilrc", group, "AutoSuspendIdleTimeoutSec", str(p["minutes"] * 60))
    _powerdevil_reload()
    text = "The PC won't go to sleep on its own." if p["minutes"] == 0 else \
        f"The PC goes to sleep after {p['minutes']} minutes idle."
    return ok(text, undo={"before": before})


def _undo_sleep_timeout(t):
    for profile, old in (t.get("before") or {}).items():
        if profile not in ("AC", "Battery"):
            continue
        group = [profile, "SuspendAndShutdown"]
        for key, name in (("AutoSuspendAction", "action"), ("AutoSuspendIdleTimeoutSec", "seconds")):
            value = str(old.get(name) or "")
            kwrite("powerdevilrc", group, key, value if value.isdigit() else None)
    _powerdevil_reload()
    return "The sleep timer is back to what it was."


def _locker_reload():
    proc.try_run([proc.qdbus(), "org.freedesktop.ScreenSaver", "/ScreenSaver", "configure"])


def _lock_timeout(p):
    before = {"autolock": kread("kscreenlockerrc", ["Daemon"], "Autolock", ""),
              "timeout": kread("kscreenlockerrc", ["Daemon"], "Timeout", "")}
    if p["minutes"] == 0:
        kwrite("kscreenlockerrc", ["Daemon"], "Autolock", "false", "bool")
    else:
        kwrite("kscreenlockerrc", ["Daemon"], "Autolock", "true", "bool")
        kwrite("kscreenlockerrc", ["Daemon"], "Timeout", str(p["minutes"]))
    _locker_reload()
    text = "The screen won't lock on its own." if p["minutes"] == 0 else \
        f"The screen locks after {p['minutes']} minutes idle."
    return ok(text, undo=before)


def _undo_lock_timeout(t):
    auto, timeout = str(t.get("autolock") or ""), str(t.get("timeout") or "")
    kwrite("kscreenlockerrc", ["Daemon"], "Autolock", ("true" if _bool(auto) else "false") if auto else None,
           "bool" if auto else "")
    kwrite("kscreenlockerrc", ["Daemon"], "Timeout", timeout if timeout.isdigit() else None)
    _locker_reload()
    return "The lock timer is back to what it was."


# ---------------------------------------------------------------------- #
# Input: pointer speed, keyboard layout
# ---------------------------------------------------------------------- #
_INPUT = ["org.kde.KWin", "/org/kde/KWin/InputDevice"]
_EVENT = r"event[0-9]{1,4}"


def _pointer_devices(kind: str) -> List[str]:
    q = proc.qdbus()
    names = proc.run([q, *_INPUT, "org.kde.KWin.InputDeviceManager.devicesSysNames"]).split()
    found = []
    for name in names:
        if not re.fullmatch(_EVENT, name):
            continue
        path = f"{_INPUT[1]}/{name}"
        touchpad = _bool(proc.try_run([q, _INPUT[0], path, "org.kde.KWin.InputDevice.touchpad"]))
        pointer = _bool(proc.try_run([q, _INPUT[0], path, "org.kde.KWin.InputDevice.pointer"]))
        if (kind == "touchpad" and touchpad) or (kind == "mouse" and pointer and not touchpad):
            found.append(name)
    return found


def _set_accel(name: str, value: float):
    proc.run([proc.qdbus(), _INPUT[0], f"{_INPUT[1]}/{name}", "org.kde.KWin.InputDevice.pointerAcceleration",
              f"{max(-1.0, min(1.0, float(value))):.2f}"])


def _pointer_speed(p):
    kind = p.get("device", "mouse")
    devices = _pointer_devices(kind)
    if not devices:
        raise ActionError(f"I can't find a {kind}.", "NOT_FOUND")
    before = {}
    for name in devices:
        before[name] = proc.try_run([proc.qdbus(), _INPUT[0], f"{_INPUT[1]}/{name}",
                                     "org.kde.KWin.InputDevice.pointerAcceleration"])
        _set_accel(name, p["speed"] / 100)
    return ok(f"{kind.capitalize()} speed is now {p['speed']:+d}.", undo={"before": before})


def _undo_pointer_speed(t):
    done = 0
    for name, value in (t.get("before") or {}).items():
        try:
            if re.fullmatch(_EVENT, str(name)):
                _set_accel(name, float(value))
                done += 1
        except (TypeError, ValueError):
            continue
    if not done:
        raise ActionError("I don't know what the speed was before.", "NO_UNDO")
    return "Pointer speed is back to what it was."


_LAYOUT = r"[a-z]{2,8}(,[a-z]{2,8}){0,3}"


def _keyboard_reload():
    proc.try_run(["dbus-send", "--session", "--type=signal", "/Layouts", "org.kde.keyboard.reloadConfig"])


def _keyboard_layout(p):
    before = {"layouts": kread("kxkbrc", ["Layout"], "LayoutList", ""), "use": kread("kxkbrc", ["Layout"], "Use", "")}
    kwrite("kxkbrc", ["Layout"], "LayoutList", p["layout"])
    kwrite("kxkbrc", ["Layout"], "Use", "true", "bool")
    _keyboard_reload()
    return ok(f"Keyboard layout is now {p['layout']}.", undo=before)


def _undo_keyboard_layout(t):
    layouts = str(t.get("layouts") or "")
    kwrite("kxkbrc", ["Layout"], "LayoutList", layouts if re.fullmatch(_LAYOUT, layouts) else None)
    if not layouts:
        kwrite("kxkbrc", ["Layout"], "Use", "false", "bool")
    _keyboard_reload()
    return "The keyboard layout is back to what it was."


# ---------------------------------------------------------------------- #
# Time zone, do not disturb
# ---------------------------------------------------------------------- #
_ZONE = r"[A-Za-z0-9_+-]{1,32}(/[A-Za-z0-9_+-]{1,32}){0,2}"


def _timezone(p):
    was = proc.try_run(["timedatectl", "show", "-p", "Timezone", "--value"])
    proc.run(["timedatectl", "set-timezone", p["zone"]], timeout=60)      # may show an admin prompt
    return ok(f"The time zone is now {p['zone']}.", undo={"zone": was} if re.fullmatch(_ZONE, was) else None)


def _undo_timezone(t):
    if not re.fullmatch(_ZONE, str(t.get("zone", ""))):
        raise ActionError("I don't know what the time zone was before.", "NO_UNDO")
    proc.run(["timedatectl", "set-timezone", t["zone"]], timeout=60)
    return f"The time zone is back to {t['zone']}."


_DND_FOREVER = "2099-01-01T00:00:00"


def _dnd(p):
    was = kread("plasmanotifyrc", ["DoNotDisturb"], "Until", "")
    kwrite("plasmanotifyrc", ["DoNotDisturb"], "Until", _DND_FOREVER if p["on"] else None, notify=True)
    return ok("Do not disturb is on." if p["on"] else "Do not disturb is off.", undo={"until": was})


def _undo_dnd(t):
    until = str(t.get("until") or "")
    kwrite("plasmanotifyrc", ["DoNotDisturb"], "Until",
           until if re.fullmatch(r"[0-9T:.+Z-]{10,40}", until) else None, notify=True)
    return "Do not disturb is back to how it was."


# ---------------------------------------------------------------------- #
def register(registry):
    out = P("string", "display name, e.g. DP-1; empty = main display", required=False, pattern=_OUTPUT)
    actions = [
        Action("settings.display.scale", "Change display scale", _set_scale,
               {"scale": P("number", "1 = 100%, 1.5 = 150%", minimum=0.5, maximum=3), "output": out},
               risk=SAFE, undo=_undo_scale, platforms=LINUX, keywords="zoom everything bigger smaller size dpi",
               preview=lambda p: f"Set the display scale to {round(p['scale'] * 100)}%"
                                 f"{' on ' + p['output'] if p.get('output') else ''}."),
        Action("settings.display.resolution", "Change screen resolution", _set_resolution,
               {"width": P("integer", minimum=640, maximum=16384), "height": P("integer", minimum=480, maximum=16384),
                "refresh": P("number", "Hz", required=False, minimum=20, maximum=600), "output": out},
               risk=RISKY, undo=_undo_resolution, platforms=LINUX, keywords="monitor mode refresh rate hz 4k 1080p",
               preview=lambda p: f"Change the screen resolution to {p['width']}x{p['height']}"
                                 f"{' on ' + p['output'] if p.get('output') else ''}. The screen may go black "
                                 f"for a moment."),
        Action("settings.display.night_light", "Turn night light on or off", _night_light,
               {"on": P("boolean"), "temperature": P("integer", "Kelvin, lower = warmer", required=False,
                                                     minimum=1000, maximum=6500)},
               undo=_undo_night_light, platforms=LINUX, keywords="night color warm blue light filter evening",
               preview=lambda p: f"Turn night light {'on' if p['on'] else 'off'}."),
        Action("settings.display.brightness", "Change screen brightness", _brightness,
               {"percent": P("integer", minimum=0, maximum=100)}, undo=_undo_brightness,
               keywords="brighter dimmer dim backlight",
               preview=lambda p: f"Set screen brightness to {p['percent']}%."),
        Action("settings.appearance.theme", "Switch dark or light theme", _theme,
               {"mode": P("string", enum=["dark", "light"])}, undo=_undo_theme, platforms=LINUX,
               keywords="dark mode light mode colour color scheme look",
               preview=lambda p: f"Switch to the {p['mode']} theme."),
        Action("settings.appearance.wallpaper_color", "Set a solid wallpaper colour", _wallpaper_color,
               {"color": P("string", "#rrggbb", pattern=_COLOR)}, undo=_undo_wallpaper_color, platforms=LINUX,
               keywords="background desktop color colour plain",
               preview=lambda p: f"Make the wallpaper a solid colour ({p['color']})."),
        Action("settings.appearance.text_size", "Change text size", _text_size,
               {"size": P("integer", "points", required=False, minimum=6, maximum=28),
                "step": P("integer", "relative: 1 bigger, -1 smaller", required=False, minimum=-8, maximum=8)},
               undo=_undo_text_size, platforms=LINUX, keywords="font bigger smaller larger letters readable",
               preview=lambda p: (f"Set the text size to {p['size']} pt." if p.get("size") is not None else
                                  f"Make text {abs(p.get('step') or 0)} pt "
                                  f"{'bigger' if (p.get('step') or 0) > 0 else 'smaller'}.")),
        Action("settings.sound.volume", "Set the volume", _volume,
               {"percent": P("integer", minimum=0, maximum=100)}, undo=_undo_volume,
               keywords="louder quieter audio sound level",
               preview=lambda p: f"Set the volume to {p['percent']}%."),
        Action("settings.sound.mute", "Mute or unmute sound or the microphone", _mute,
               {"state": P("string", enum=["on", "off", "toggle"]),
                "device": P("string", required=False, enum=["output", "mic"], default="output")},
               undo=_undo_mute, keywords="silence unmute microphone audio speakers",
               preview=lambda p: {"on": "Mute", "off": "Unmute", "toggle": "Toggle mute on"}[p["state"]] +
                                 (" the microphone." if p.get("device") == "mic" else " the sound.")),
        Action("settings.sound.output", "Switch the sound output device", _sound_output,
               {"name": P("string", "device name or 'headphones', 'speakers'")}, undo=_undo_sound_output,
               keywords="audio speakers headphones headset hdmi device play through",
               preview=lambda p: f"Play sound through {p['name']}."),
        Action("settings.apps.default", "Choose a default app", _default_app,
               {"kind": P("string", enum=sorted(DEFAULT_APP_KINDS)), "app": P("string", "e.g. firefox.desktop")},
               undo=_undo_default_app, platforms=LINUX,
               keywords="default browser mail email file manager player viewer open with",
               preview=lambda p: f"Open {p['kind']} with {p['app']} by default."),
        Action("settings.power.profile", "Change the power profile", _power_profile,
               {"profile": P("string", enum=PROFILES)}, undo=_undo_power_profile, platforms=LINUX,
               keywords="battery saver performance balanced power mode energy",
               preview=lambda p: f"Switch the power profile to {p['profile'].replace('-', ' ')}."),
        Action("settings.power.sleep_timeout", "Change when the PC goes to sleep", _sleep_timeout,
               {"minutes": P("integer", "0 = never", minimum=0, maximum=600),
                "when": P("string", required=False, enum=sorted(_POWER_GROUPS), default="both")},
               undo=_undo_sleep_timeout, platforms=LINUX, keywords="suspend idle timer never sleep after",
               preview=lambda p: ("Stop the PC going to sleep on its own." if p["minutes"] == 0 else
                                  f"Put the PC to sleep after {p['minutes']} minutes idle.")),
        Action("settings.power.lock_timeout", "Change when the screen locks", _lock_timeout,
               {"minutes": P("integer", "0 = never", minimum=0, maximum=240)}, undo=_undo_lock_timeout,
               platforms=LINUX, keywords="screen lock idle timer auto lock after",
               preview=lambda p: ("Stop the screen locking on its own." if p["minutes"] == 0 else
                                  f"Lock the screen after {p['minutes']} minutes idle.")),
        Action("settings.input.pointer_speed", "Change mouse or touchpad speed", _pointer_speed,
               {"speed": P("integer", "-100 slowest, 0 default, 100 fastest", minimum=-100, maximum=100),
                "device": P("string", required=False, enum=["mouse", "touchpad"], default="mouse")},
               undo=_undo_pointer_speed, platforms=LINUX, keywords="cursor sensitivity acceleration faster slower",
               preview=lambda p: f"Set the {p.get('device', 'mouse')} speed to {p['speed']:+d}."),
        Action("settings.input.keyboard_layout", "Change the keyboard layout", _keyboard_layout,
               {"layout": P("string", "xkb code(s): us, gb, de or us,de", pattern=_LAYOUT)},
               undo=_undo_keyboard_layout, platforms=LINUX, keywords="language keys qwerty azerty typing",
               preview=lambda p: f"Change the keyboard layout to {p['layout']}."),
        Action("settings.system.timezone", "Change the time zone", _timezone,
               {"zone": P("string", "e.g. Europe/London", pattern=_ZONE)}, risk=RISKY, undo=_undo_timezone,
               platforms=LINUX, keywords="clock time region date",
               preview=lambda p: f"Change the time zone to {p['zone']} (asks for the admin password)."),
        Action("settings.notifications.dnd", "Turn do not disturb on or off", _dnd,
               {"on": P("boolean")}, undo=_undo_dnd, platforms=LINUX,
               keywords="notifications quiet silence focus popups",
               preview=lambda p: f"Turn do not disturb {'on' if p['on'] else 'off'}."),
    ]
    for a in actions:
        registry.register(a, replace=True)
