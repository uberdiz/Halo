"""
core/audio_doctor.py

"I have no sound": find and fix the usual Linux audio failures with plain commands (pactl, systemctl --user).

    check()   -> what's wrong, nothing changed
    repair()  -> fixes it and says what it did

Fixes, in order:
1. A sound card whose profile is "off" (the usual NVIDIA HDMI/DisplayPort case: the monitor's ELD wasn't read, so
   every HDMI profile says "unavailable" and WirePlumber turned the card off - the output isn't even listed):
   switch it to its best output profile. With no output at all, the best profile even if it says unavailable.
2. Still no real output (none, or only PipeWire's "Dummy Output" / auto_null): restart wireplumber, pipewire and
   pipewire-pulse (user units) and look again. Dummy Output usually means the sound card's UCM profile
   (alsa-ucm-conf) or firmware (sof-firmware) is missing, which a restart can't fix: the report says so.
3. The default output is missing, Dummy Output, or unplugged while a plugged-in one exists: make the best real
   one the default (an analog/HDMI sink whose port is available beats one whose ports are all unplugged) and
   move what's playing to it.
4. The default output is muted or at 0%: unmute it, raise it to 50%.
5. The default microphone is muted or at 0%: unmute it, raise it to 70%.

SAINT runs repair() once a little after it starts on Linux (app.py), as the action ``audio.repair`` and from
Settings > Sound > Fix the sound (ui/settings_pages/sound.py). core/sound.py is the mixer it shares commands with.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

from core.actions import proc

log = logging.getLogger("saint.audio")

DUMMY = "auto_null"
SINK_VOLUME, MIC_VOLUME = "50%", "70%"
UNITS = ["wireplumber", "pipewire", "pipewire-pulse"]


def _sh(argv: List[str]) -> str:          # tests replace this with canned output
    return proc.try_run(argv, timeout=10)


def _list(kind: str) -> List[Dict]:
    try:
        rows = json.loads(_sh(["pactl", "-f", "json", "list", kind]) or "[]")
    except ValueError:
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("name")]


def _real(rows: List[Dict], mic: bool = False) -> List[Dict]:
    return [r for r in rows if r["name"] != DUMMY and not (mic and r["name"].endswith(".monitor"))]


def _percent(row: Dict) -> Optional[int]:
    vals = []
    for ch in (row.get("volume") or {}).values():
        try:
            vals.append(int(str(ch.get("value_percent", "")).rstrip("%")))
        except (ValueError, AttributeError):
            pass
    return max(vals) if vals else None


def _score(row: Dict) -> int:
    """Higher is better: a plugged-in port first, then analog/HDMI over the rest."""
    ports = row.get("ports") or []
    plugged = not ports or any(p.get("availability") != "not available" for p in ports)
    text = f"{row['name']} {row.get('description', '')}".lower()
    kind = 2 if "analog" in text else 1 if ("hdmi" in text or "displayport" in text) else 0
    return (10 if plugged else 0) + kind


def _plugged(row: Dict) -> bool:
    return _score(row) >= 10


def _best_profile(card: Dict, any_state: bool) -> str:
    """The card's best output profile, "" if none (or none available unless ``any_state``)."""
    from core.sound import _OUTPUT_KIND
    best, key = "", None
    for name, p in (card.get("profiles") or {}).items():
        if not _OUTPUT_KIND.match(name) or not p.get("sinks", 1) or not (any_state or p.get("available", True)):
            continue
        k = (bool(p.get("available", True)), name.startswith("output:analog"), int(p.get("priority") or 0))
        if key is None or k > key:
            best, key = name, k
    return best


def _wake_cards(any_state: bool, did: List[str]) -> int:
    """Switch every card that's "off" to its best output profile. ``any_state``: even one that says unavailable."""
    from core import sound
    n = 0
    for c in sound._rows("cards"):
        if c.get("active_profile") != "off" or not c.get("name"):
            continue
        prof = _best_profile(c, any_state)
        if not prof:
            continue
        _sh(["pactl", "set-card-profile", c["name"], prof])
        p = c["profiles"][prof]
        did.append(f"turned on {c.get('properties', {}).get('device.description') or c['name']} "
                   f"({p.get('description') or prof})")
        n += 1
    return n


def _state() -> Dict:
    sinks, sources = _list("sinks"), _list("sources")
    return {"sinks": sinks, "sources": sources, "sink": _sh(["pactl", "get-default-sink"]),
            "source": _sh(["pactl", "get-default-source"])}


def check(state: Optional[Dict] = None) -> List[str]:
    """Plain-English problems, empty when sound looks fine."""
    s = state or _state()
    real = _real(s["sinks"])
    if not real:
        return ["There's no sound output, only “Dummy Output”."]
    out = []
    default = next((r for r in real if r["name"] == s["sink"]), None)
    if default is None:
        out.append("The default output isn't a real device.")
    elif default.get("mute") or _percent(default) == 0:
        out.append(f"{default.get('description') or default['name']} is muted or at 0%.")
    mic = next((r for r in _real(s["sources"], mic=True) if r["name"] == s["source"]), None)
    if mic is not None and (mic.get("mute") or _percent(mic) == 0):
        out.append(f"The microphone ({mic.get('description') or mic['name']}) is muted or at 0%.")
    return out


def repair(settle: float = 2.0) -> Dict:
    """Fix what check() finds. Returns {"ok", "did": [...], "problems": [...left over...], "message"}."""
    did: List[str] = []
    s = _state()
    # 1. cards switched off: with outputs elsewhere only the ones whose monitor/jack says plugged in
    if _wake_cards(any_state=not _real(s["sinks"]), did=did):
        time.sleep(settle / 2)
        s = _state()
    # 2. nothing real: restart PipeWire, then try the cards again
    if not _real(s["sinks"]):
        _sh(["systemctl", "--user", "restart", *UNITS])
        did.append("restarted the sound service (PipeWire)")
        time.sleep(settle)
        if _wake_cards(any_state=True, did=did):
            time.sleep(settle / 2)
        s = _state()
    real = _real(s["sinks"])
    if real:
        default = next((r for r in real if r["name"] == s["sink"]), None)
        best = max(real, key=_score)
        if default is None or (not _plugged(default) and _plugged(best)):
            default = best
            _sh(["pactl", "set-default-sink", default["name"]])
            did.append(f"made {default.get('description') or default['name']} the output")
            from core import sound
            moved = sound.move_all(default["name"])
            if moved:
                did.append(f"moved {moved} playing app{'s' if moved > 1 else ''} to it")
        if default.get("mute"):
            _sh(["pactl", "set-sink-mute", default["name"], "0"])
            did.append("unmuted the sound")
        if _percent(default) == 0:
            _sh(["pactl", "set-sink-volume", default["name"], SINK_VOLUME])
            did.append(f"raised the volume to {SINK_VOLUME}")
    mic = next((r for r in _real(s["sources"], mic=True) if r["name"] == s["source"]), None)
    if mic is not None:
        if mic.get("mute"):
            _sh(["pactl", "set-source-mute", mic["name"], "0"])
            did.append("unmuted the microphone")
        if _percent(mic) == 0:
            _sh(["pactl", "set-source-volume", mic["name"], MIC_VOLUME])
            did.append(f"raised the microphone to {MIC_VOLUME}")
    after = _state() if did else s
    left = check(after)
    if left and not _real(after["sinks"]):
        left.append("The sound card needs a driver profile: check that alsa-ucm-conf, sof-firmware and "
                    "alsa-firmware are installed, then restart the PC.")
    hidden = _hidden_hdmi()                 # sound works elsewhere, so a note, not a problem
    note = (f"{hidden} reports no screen with speakers, so I can't tell which HDMI/DisplayPort output is your "
            "monitor: pick it in Settings \u203a Sound (Test plays a chime on it).") if hidden else ""
    if did:
        msg = "I " + ", ".join(did) + "." + (" Still: " + " ".join(left) if left else "")
    else:
        msg = "Sound looks fine: nothing needed fixing." if not left else " ".join(left)
    msg = f"{msg} {note}".strip()
    log.info("audio.repair did=%s left=%s note=%s", did, left, bool(note))
    return {"ok": not left, "did": did, "problems": left, "note": note, "message": msg}


def _hidden_hdmi() -> str:
    """A card that's still off although it has HDMI/DP outputs (they all say "unavailable"): its name, else ""."""
    from core import sound
    for c in sound._rows("cards"):
        if c.get("active_profile") == "off" and any(k.startswith("output:hdmi") for k in c.get("profiles") or {}):
            return c.get("properties", {}).get("device.description") or c.get("name", "A graphics card")
    return ""
