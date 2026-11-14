"""
core/followup.py

Talking to SAINT without the wake word while she's on screen: when the avatar appears (or finishes answering) the
microphone listens for ~20 s, and "what's the weather?" needs no "Hey SAINT". It stays shut during a game or a
fullscreen app, and during a voice call (Discord, Teams, a browser call...), where other voices would become
requests.

    open_followup_window(seconds=20.0, source="avatar")   the hook the avatar calls; returns False when blocked
    blocked() -> str                                      why an open mic isn't allowed now ("" when it is)
    in_call() -> bool                                     a voice app is capturing the microphone right now

The voice module (modules/voice/module.py) turns the event into its follow-up listening state: the COMMAND phase
with reason "follow-up (<source>)", which still needs speech that sounds like a request (the follow-up gate), so
room chatter doesn't become a command.
"""

import json
import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

from core.events import event_bus

log = logging.getLogger("saint.followup")

EVENT = "voice.followup.request"          # payload {"seconds": float, "source": str}
DEFAULT_SEC = 20.0
MAX_SEC = 60.0
CALL_TTL = 3.0

# Apps whose microphone stream means a conversation with people (not SAINT).
VOICE_APPS = re.compile(r"discord|vesktop|webcord|armcord|teams|zoom|skype|slack|telegram|signal|element|"
                        r"mumble|teamspeak|ts3client|jitsi|whatsapp|guilded|webex|firefox|chrom|brave|vivaldi|"
                        r"opera|msedge|obs", re.I)

_call = {"at": 0.0, "on": False}
_lock = threading.Lock()


def _capturing_apps(run: Callable = subprocess.run) -> list:
    """Names of the apps recording from a microphone now (PipeWire / PulseAudio), [] where that can't be read."""
    if not sys.platform.startswith("linux") or not shutil.which("pactl"):
        return []
    try:
        r = run(["pactl", "-f", "json", "list", "source-outputs"], capture_output=True, text=True, timeout=2)
        rows = json.loads(r.stdout or "[]") if r.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    names = []
    for row in rows if isinstance(rows, list) else []:
        props = (row or {}).get("properties") or {}
        names.append(" ".join(str(props.get(k, "")) for k in ("application.process.binary", "application.name")))
    return names


def in_call(now: Optional[float] = None, apps: Callable = _capturing_apps) -> bool:
    now = time.monotonic() if now is None else now
    with _lock:
        if now - _call["at"] < CALL_TTL:
            return bool(_call["on"])
    on = any(VOICE_APPS.search(n) for n in apps())
    with _lock:
        _call.update(at=now, on=on)
    return on


def blocked(call: Optional[Callable[[], bool]] = None) -> str:
    """Why SAINT mustn't listen without the wake word right now, or ""."""
    try:
        from core.game_mode import game_mode
        if game_mode.busy:
            return "game"
        if game_mode.overlays_blocked:
            return "fullscreen"
    except Exception:
        pass
    try:
        if (call or in_call)():
            return "call"
    except Exception:
        log.debug("followup.call_check_failed", exc_info=True)
    return ""


def open_followup_window(seconds: float = DEFAULT_SEC, source: str = "avatar") -> bool:
    """Listen without the wake word for ``seconds`` (the avatar calls this when she appears or finishes talking).
    False when a game, a fullscreen app or a call keeps the mic shut; the voice module also ignores it when the
    microphone or the wake word is off."""
    why = blocked()
    if why:
        log.info("followup.blocked source=%s reason=%s", source, why)
        return False
    seconds = max(1.0, min(float(seconds or DEFAULT_SEC), MAX_SEC))
    event_bus.emit_event(EVENT, {"seconds": seconds, "source": str(source or "avatar")[:24]})
    return True
