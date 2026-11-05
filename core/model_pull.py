"""
core/model_pull.py

Downloading SAINT's Ollama model with the progress visible in SAINT.

On Halo the saint-ollama-model service starts the download after install; ``auto_start()`` (called once
SAINT's window is up) follows that same pull through Ollama's streamed /api/pull — Ollama shares one
download between callers — so the System page and the AI settings can show "Downloading llama3.1:8b —
43 %" and a notification says when it's ready or why it failed. ``start()`` is the "Download model"
button. One pull at a time; ``state()`` is what the UI reads.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

log = logging.getLogger("saint.model_pull")

_lock = threading.Lock()
_state: Dict = {"model": "", "running": False, "status": "", "percent": None, "completed": 0, "total": 0,
                "error": "", "done": False, "started": 0.0}
_cancel = threading.Event()


def state() -> Dict:
    with _lock:
        return dict(_state)


def describe(s: Optional[Dict] = None) -> str:
    """One line for the UI: 'Downloading llama3.1:8b — 43% (2.1 of 4.9 GB)'."""
    s = s or state()
    if not s.get("model"):
        return ""
    if s.get("running"):
        if s.get("percent") is None:
            return f"Preparing {s['model']} — {s.get('status') or 'starting'}"
        gb = lambda n: f"{n / 1e9:.1f}"
        return f"Downloading {s['model']} — {s['percent']:.0f}% ({gb(s['completed'])} of {gb(s['total'])} GB)"
    if s.get("done"):
        return f"{s['model']} downloaded"
    if s.get("error"):
        return f"Downloading {s['model']} failed: {s['error']}"
    return ""


def _notify(title: str, message: str):
    try:
        from core.events import EventType, event_bus
        event_bus.emit_event(EventType.NOTIFY, {"title": title, "message": message, "icon": "download"})
    except Exception:                                  # no event bus (CLI, tests)
        log.info("%s: %s", title, message)


def start(base_url: str, model: str, provider=None, notify: Callable[[str, str], None] = None,
          wait: bool = False) -> bool:
    """Pull ``model`` in the background (or in this thread with ``wait``). False when a pull is running."""
    model = (model or "").strip()
    if not model:
        return False
    with _lock:
        if _state["running"]:
            return False
        _state.update(model=model, running=True, status="starting", percent=None, completed=0, total=0,
                      error="", done=False, started=time.time())
    _cancel.clear()
    say = notify or _notify

    def progress(p: Dict):
        with _lock:
            _state.update(status=p.get("status", ""), percent=p.get("percent"),
                          completed=p.get("completed", 0), total=p.get("total", 0))

    def run():
        if provider is None:
            from modules.ai.providers import OllamaProvider
            prov = OllamaProvider()
        else:
            prov = provider
        say("Downloading SAINT's AI model", f"{model} is downloading in the background. Progress: System page.")
        try:
            res = prov.pull_model_stream(base_url, model, progress, _cancel)
        except Exception as e:                         # never let a pull thread die silently
            res = {"success": False, "error": f"{type(e).__name__}: {e}"}
        with _lock:
            _state.update(running=False, done=bool(res.get("success")), error="" if res.get("success")
                          else str(res.get("error") or "unknown error"))
            if res.get("success"):
                _state["percent"] = 100.0
        if res.get("success"):
            try:
                from modules.ai.providers import OllamaProvider
                OllamaProvider._cache_time = 0                 # the model list changed
            except Exception:
                pass
            say("SAINT's AI model is ready", f"{model} is downloaded; chat and planning use it now.")
        elif not res.get("cancelled"):
            log.warning("Pulling %s failed: %s", model, res.get("error"))
            say("SAINT's AI model didn't download", f"{model}: {res.get('error')}")

    if wait:
        run()
    else:
        threading.Thread(target=run, daemon=True, name="ollama-pull").start()
    return True


def cancel():
    _cancel.set()


def auto_start(get_config=None, check=None) -> bool:
    """On Halo: when Ollama runs but the configured model isn't downloaded yet, follow (or start) its pull.
    Returns True when a pull was started."""
    from core import health
    from core.paths import system_install
    if get_config is None:
        from core.config import config
        get_config = config.get
    if not system_install() or get_config("ai.provider", "ollama") != "ollama":
        return False
    base, model = get_config("ai.base_url", "http://localhost:11434"), get_config("ai.model", "")
    r = (check or health.ollama)(base, model)
    if r["state"] == health.WORKING or r["state"] in (health.MISSING, health.FAILED):
        return False                                   # already there / Ollama not running: nothing to follow
    return start(base, model)
