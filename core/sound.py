"""
core/sound.py

HalOS's mixer, with plain pactl commands (PipeWire's pulse server): every output including the HDMI/DisplayPort
ones a card has switched off, per-device and per-app volume and mute, moving an app to another output, and
playing on several outputs at once (module-combine-sink). Settings › Sound (ui/settings_pages/sound.py) and
core/audio_doctor.py use it. Nothing here asks a model anything.

    outputs()               every sink, then every HDMI/DP/analog output profile no sink exists for yet
    apps()                  what's playing now: {"id", "app", "sink", "percent", "mute"}
    use_output(o)           turn the card profile on if needed, make it the default, move the apps to it
    combine(names)          one "Several outputs" sink that plays on all of them (uncombine() removes it)
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

from core import audio_doctor as ad

COMBINED = "halo_combined"
_NAME = re.compile(r"[A-Za-z0-9_.:+@-]{1,200}")
_OUTPUT_KIND = re.compile(r"^output:(hdmi|iec958|analog)")


def _pactl(*args: str) -> str:
    return ad._sh(["pactl", *args])


def _rows(kind: str) -> List[Dict]:
    """``pactl -f json list <kind>`` (cards and sink-inputs have no "name" requirement)."""
    try:
        rows = json.loads(_pactl("-f", "json", "list", kind) or "[]")
    except ValueError:
        return []
    return [r for r in rows if isinstance(r, dict)]


def _check(name: str) -> str:
    if not _NAME.fullmatch(str(name or "")):
        raise ValueError(f"not a sound device name: {name!r}")
    return name


def _pct(value) -> str:
    return f"{max(0, min(150, int(value)))}%"


def _card_key(card: Dict) -> str:
    """alsa_card.pci-0000_01_00.1 -> pci-0000_01_00.1, which its sinks' names contain."""
    return str(card.get("name", "")).split(".", 1)[-1]


def monitor_name(card: Dict, port: str = "", profile: str = "") -> str:
    """The monitor's own name from its ELD (PipeWire puts it on the card port), or ""."""
    for pname, p in (card.get("ports") or {}).items():
        if (port and pname != port) or (profile and profile not in (p.get("profiles") or [])):
            continue
        name = ((p.get("properties") or {}).get("device.product.name") or "").strip()
        if name:
            return name
    return ""


def _label(base: str, monitor: str) -> str:
    return f"{monitor} ({base})" if monitor and monitor not in base else base


def outputs(cards: Optional[List[Dict]] = None, sinks: Optional[List[Dict]] = None,
            default: Optional[str] = None) -> List[Dict]:
    """Every output, hidden ones included. Each: {"kind": "sink"|"profile", "name", "label", "card",
    "profile", "available", "default", "percent", "mute", "bluetooth", "hdmi"}."""
    cards = _rows("cards") if cards is None else cards
    sinks = ad._list("sinks") if sinks is None else sinks
    default = _pactl("get-default-sink") if default is None else default
    out: List[Dict] = []
    for s in sinks:
        if s["name"] == ad.DUMMY:
            continue
        card = next((c for c in cards if _card_key(c) and _card_key(c) in s["name"]), {})
        ports = s.get("ports") or []
        text = f"{s['name']} {s.get('description', '')}".lower()
        out.append({"kind": "sink", "name": s["name"], "card": card.get("name", ""), "profile": "",
                    "label": _label(s.get("description") or s["name"], monitor_name(card, s.get("active_port", ""))),
                    "available": not ports or any(p.get("availability") != "not available" for p in ports),
                    "default": s["name"] == default, "percent": ad._percent(s), "mute": bool(s.get("mute")),
                    "bluetooth": s["name"].startswith("bluez_"),
                    "hdmi": "hdmi" in text or "displayport" in text, "combined": s["name"] == COMBINED})
    for c in cards:
        active = c.get("active_profile", "")
        has_sink = any(o["card"] == c.get("name") for o in out)
        for prof, p in (c.get("profiles") or {}).items():
            # The card's other output profiles: the only way to reach an HDMI port whose profile isn't active
            # (NVIDIA cards have 4 HDMI/DP profiles, one of them is the monitor). Duplex/input-only ones aren't
            # outputs; while a sink of this card exists only offer HDMI/DP alternatives, not every analog mix.
            if prof == active or not _OUTPUT_KIND.match(prof) or "+input" in prof or not p.get("sinks", 1):
                continue
            hdmi = prof.startswith("output:hdmi")
            if has_sink and not hdmi:
                continue
            base = f"{c.get('properties', {}).get('device.description') or c.get('name')} · {p.get('description') or prof}"
            out.append({"kind": "profile", "name": "", "card": c["name"], "profile": prof,
                        "label": _label(base, monitor_name(c, profile=prof)), "available": p.get("available", True),
                        "default": False, "percent": None, "mute": False, "bluetooth": False, "hdmi": hdmi,
                        "combined": False})
    return out


def apps(sinks: Optional[List[Dict]] = None) -> List[Dict]:
    """What's playing: each app stream with the output (sink name) it plays on."""
    sinks = ad._list("sinks") if sinks is None else sinks
    by_index = {s.get("index"): s["name"] for s in sinks}
    out = []
    for r in _rows("sink-inputs"):
        props = r.get("properties") or {}
        if props.get("media.role") == "event" and not props.get("application.name"):
            continue
        app = props.get("application.name") or props.get("application.process.binary") or "An app"
        media = props.get("media.name") or ""
        out.append({"id": int(r.get("index", -1)), "app": app, "media": media if media != app else "",
                    "sink": by_index.get(r.get("sink"), ""), "percent": ad._percent(r), "mute": bool(r.get("mute"))})
    return [a for a in out if a["id"] >= 0]


# --------------------------------------------------------------------------- changes
def set_volume(sink: str, percent: int):
    _pactl("set-sink-volume", _check(sink), _pct(percent))


def set_mute(sink: str, mute: bool):
    _pactl("set-sink-mute", _check(sink), "1" if mute else "0")


def set_app_volume(app_id: int, percent: int):
    _pactl("set-sink-input-volume", str(int(app_id)), _pct(percent))


def set_app_mute(app_id: int, mute: bool):
    _pactl("set-sink-input-mute", str(int(app_id)), "1" if mute else "0")


def move_app(app_id: int, sink: str):
    _pactl("move-sink-input", str(int(app_id)), _check(sink))


def move_all(sink: str) -> int:
    """Move every playing app to ``sink``; how many moved."""
    n = 0
    for a in apps():
        if a["sink"] != sink:
            move_app(a["id"], sink)
            n += 1
    return n


def set_profile(card: str, profile: str):
    _pactl("set-card-profile", _check(card), _check(profile))


def use_output(o: Dict, settle: float = 1.0) -> str:
    """Play everything on output ``o`` (from outputs()). Returns the sink name, "" if the card made none."""
    sink = o.get("name") or ""
    if o.get("kind") == "profile":
        set_profile(o["card"], o["profile"])
        key = o["card"].split(".", 1)[-1]
        for _ in range(5):                          # the sink appears a moment after the profile switch
            sink = next((s["name"] for s in ad._list("sinks") if key in s["name"]), "")
            if sink:
                break
            time.sleep(settle / 5)
    if not sink:
        return ""
    _pactl("set-default-sink", _check(sink))
    move_all(sink)
    return sink


def combine(sinks: List[str]) -> str:
    """One sink that plays on all of ``sinks`` at once, made the default (replaces an earlier one)."""
    names = [_check(s) for s in sinks if s != COMBINED]
    if len(names) < 2:
        raise ValueError("pick at least two outputs")
    uncombine()
    # ponytail: the description quoting is what PulseAudio's modargs accept; checked against pipewire-pulse docs,
    # not yet on hardware. A wrong parse only costs the pretty name (the sink is still called halo_combined).
    _pactl("load-module", "module-combine-sink", f"sink_name={COMBINED}", f"slaves={','.join(names)}",
           "sink_properties='device.description=\"Several outputs\"'")
    _pactl("set-default-sink", COMBINED)
    move_all(COMBINED)
    return COMBINED


def uncombine():
    _pactl("unload-module", "module-combine-sink")


def test_sound(sink: str) -> bool:
    """A short chime on ``sink`` so you can tell which output is the monitor."""
    import shutil
    import subprocess
    from pathlib import Path
    wav = next((p for p in (Path("/usr/share/sounds/saint/stereo/saint-star-open.wav"),
                            Path("/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga"),
                            Path("/usr/share/sounds/freedesktop/stereo/bell.oga")) if p.is_file()), None)
    player = shutil.which("pw-play") or shutil.which("paplay")
    if not wav or not player:
        return False
    flag = "--target" if player.endswith("pw-play") else "--device"
    try:
        subprocess.Popen([player, flag, _check(sink), str(wav)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False
