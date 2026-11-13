"""
core/audio_doctor.py

"I have no sound": find and fix the usual Linux audio failures with plain commands (pactl, systemctl --user).

    check()   -> what's wrong, nothing changed
    repair()  -> fixes it and says what it did

Fixes, in order:
1. No real output (none, or only PipeWire's "Dummy Output" / auto_null): restart wireplumber, pipewire and
   pipewire-pulse (user units) and look again. Dummy Output usually means the sound card's UCM profile
   (alsa-ucm-conf) or firmware (sof-firmware) is missing, which a restart can't fix: the report says so.
2. The default output is missing or Dummy Output while a real one exists: make the best real one the default
   (an analog/HDMI sink whose port is available beats one whose ports are all unplugged).
3. The default output is muted or at 0%: unmute it, raise it to 50%.
4. The default microphone is muted or at 0%: unmute it, raise it to 70%.

SAINT runs repair() once a little after it starts on Linux (app.py) and as the action ``audio.repair``.
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
    if not _real(s["sinks"]):
        _sh(["systemctl", "--user", "restart", *UNITS])
        did.append("restarted the sound service (PipeWire)")
        time.sleep(settle)
        s = _state()
    real = _real(s["sinks"])
    if real:
        default = next((r for r in real if r["name"] == s["sink"]), None)
        if default is None:
            default = max(real, key=_score)
            _sh(["pactl", "set-default-sink", default["name"]])
            did.append(f"made {default.get('description') or default['name']} the output")
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
    left = check(_state()) if did else check(s)
    if left and not _real(s["sinks"]):
        left.append("The sound card needs a driver profile: check that alsa-ucm-conf, sof-firmware and "
                    "alsa-firmware are installed, then restart the PC.")
    if did:
        msg = "I " + ", ".join(did) + "." + (" Still: " + " ".join(left) if left else "")
    else:
        msg = "Sound looks fine." if not left else " ".join(left)
    log.info("audio.repair did=%s left=%s", did, left)
    return {"ok": not left, "did": did, "problems": left, "message": msg}
