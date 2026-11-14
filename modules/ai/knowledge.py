"""
modules/ai/knowledge.py

What SAINT knows about itself and this computer when it chats, built by plain code (no model call) and cached:

    persona(configured)   SAINT's voice: short for commands, a real conversation partner for chat
    system_knowledge()    HalOS / SAINT version, the hardware, what SAINT can do (the action registry), cached 10 min
    current_state()       what's going on right now (a game, Gaming Mode) - cheap, never cached

The block is a few hundred characters, so it costs the 8B local model almost nothing and stops it guessing ("I'm
just an AI, I can't see your system"). The model still never *does* anything from here: actions go through the
router and the action registry.
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

log = logging.getLogger("saint.ai.knowledge")

PERSONA = (
    "You are SAINT, the assistant built into HalOS (an Arch Linux desktop with KDE Plasma). You live on the "
    "user's computer and talk with them by voice and text, like a friendly, sharp companion who knows this "
    "machine well. "
    "When they give a command, confirm in a few words ('Done, Spotify is open.'). When they chat, chat back "
    "naturally: one to three short spoken sentences, warm and specific, and ask a follow-up question when it "
    "helps. Use what you know about the system below to answer questions about it accurately; if something "
    "isn't listed, say you'll check rather than guessing. "
    "Never use markdown, lists, JSON, code fences or tool names - your words are spoken aloud. "
    "Only say an action happened if a tool result confirms it; in plain chat you can't run anything yourself, "
    "so tell them what to say instead ('Say \"open Steam\" and I'll do it.'). "
    "Each conversation starts fresh: don't bring up earlier topics unless the user does."
)

# Defaults SAINT shipped before: a config still holding one of them gets the current persona.
_OLD_DEFAULTS = {
    "You are SAINT, a helpful AI assistant. Be concise.",
    ("You are SAINT, a voice-first assistant on the user's PC. "
     "Answer in ONE short sentence — usually under 15 words. "
     "For actions, a short confirmation like 'Skipped it.' or 'Spotify is open.' "
     "is enough; do not narrate steps. For facts, give the direct answer only "
     "(e.g. '828 meters.'). Never repeat the user's request, never explain what you're "
     "about to do, never use markdown, JSON, code fences or tool names. "
     "Only say an action happened if a tool result confirms it. "
     "Expand only when the user explicitly asks for detail."),
}


def persona(configured: str = "") -> str:
    """The system prompt to use: the user's own prompt if they wrote one, else the current persona."""
    text = (configured or "").strip()
    return PERSONA if not text or text in _OLD_DEFAULTS or text == PERSONA else text


# --------------------------------------------------------------------------- the system, built by code
TTL = 600.0
_cache: Dict[str, object] = {"at": 0.0, "text": ""}
_lock = threading.Lock()


def _gib(n) -> str:
    return f"{round((n or 0) / 2 ** 30)} GB"


def hardware_line(sysinfo=None) -> str:
    """"Ryzen 7 5800X (16 threads), 32 GB RAM, NVIDIA GeForce RTX 3070" - whatever of it can be read."""
    if sysinfo is None:
        from core import sysinfo
    parts: List[str] = []
    for fn in (lambda: "{model} ({threads} threads)".format(**sysinfo.cpu_info()),
               lambda: _gib(sysinfo.memory()["total"]) + " RAM",
               lambda: ", ".join(g["name"] for g in sysinfo.gpus()) or ""):
        try:
            part = fn()
        except Exception:
            part = ""
        if part:
            parts.append(part)
    return ", ".join(parts)


def abilities(registry=None, per_category: int = 4) -> str:
    """What SAINT can do, from the typed action registry: each category with a few of its actions."""
    try:
        if registry is None:
            from core.actions import load_builtin, registry
            load_builtin()
        rows = []
        for cat in registry.categories():
            titles = [a.title for a in registry.list(cat)][:per_category]
            if titles:
                rows.append(f"{cat}: {', '.join(titles).lower()}")
        return "; ".join(rows)
    except Exception:
        log.debug("knowledge.abilities_failed", exc_info=True)
        return ""


def build(sysinfo=None, registry=None, claude: Optional[Callable[[], bool]] = None) -> str:
    from core.version import VERSION
    lines = ["About this computer and you (facts, read by SAINT itself; use them, don't recite them):"]
    try:
        if sysinfo is None:
            from core import sysinfo as _s
            sysinfo = _s
        osname = sysinfo.system().get("os", "")
    except Exception:
        osname = ""
    lines.append(f"- System: {osname or 'HalOS'}; SAINT {VERSION}.")
    hw = hardware_line(sysinfo)
    if hw:
        lines.append(f"- Hardware: {hw}.")
    can = abilities(registry)
    if can:
        lines.append(f"- System actions you can run when asked (through your own commands): {can}.")
    try:
        if claude is None:
            from core.claude_chat import available as claude
        if claude():
            lines.append("- Claude Code is signed in: long tasks can go to it in the background.")
    except Exception:
        pass
    return "\n".join(lines)


def system_knowledge(now: Optional[float] = None) -> str:
    """The cached system block (rebuilt every TTL seconds; hardware and abilities don't change mid-session)."""
    now = time.time() if now is None else now
    with _lock:
        if _cache["text"] and now - float(_cache["at"]) < TTL:
            return str(_cache["text"])
    try:
        text = build()
    except Exception:
        log.debug("knowledge.build_failed", exc_info=True)
        text = ""
    with _lock:
        _cache.update(at=now, text=text)
    return text


def current_state() -> str:
    """Right now, in one line ("" when nothing's worth saying)."""
    bits = []
    try:
        from core.game_mode import game_mode
        if game_mode.running:
            bits.append(f"the user is playing {game_mode.game or 'a game'}")
        elif game_mode.active:
            bits.append("Gaming Mode is on")
    except Exception:
        pass
    return ("Right now: " + "; ".join(bits) + ".") if bits else ""
