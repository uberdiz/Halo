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
_refusal = ""                                          # why the last start() said no, for the UI


def refusal() -> str:
    return _refusal


def _installed(base_url: str, prov) -> Optional[set]:
    """Model names Ollama lists (":latest" filled in); None when Ollama doesn't answer."""
    try:
        try:
            models = prov.list_models(base_url, timeout=3, force_refresh=True)
        except TypeError:
            models = prov.list_models(base_url, timeout=3)
    except Exception:
        return None
    return {n if ":" in n else n + ":latest" for n in (m.get("name", "") for m in models or [])}


def precheck(model: str, installed: Optional[set], hw=None, entries=None) -> str:
    """Why not to pull ``model`` now ("" = go): already here, already downloading, or too big for this PC
    (then the largest catalog model that fits). core.agent_catalog's rules; models not in the catalog pass."""
    full = model if ":" in model else model + ":latest"
    if installed and full in installed:
        return f"{model} is already installed."
    with _lock:
        if _state["running"]:
            return (f"{model} is already downloading." if _state["model"] == model
                    else f"{_state['model']} is downloading; this one can start when it's done.")
    from core import agent_catalog as ac
    entries = [e for e in (ac.load() if entries is None else entries) if e.get("kind") == "local"]
    if not any(e["id"] in (model, full) for e in entries):
        return ""
    if hw is None:
        from core import device_profile as dp
        hw = dp.detect()
    rated = ac.rate(hw, entries)
    mine = next(r for r in rated if r.id in (model, full))
    if mine.status != ac.TOO_HEAVY:
        return ""
    fits = sorted((r for r in rated if r.status != ac.TOO_HEAVY), key=lambda r: -r.size_gb)
    return f"{mine.name} is too big for this PC: {mine.reason}" + (
        f" Try {fits[0].name} ({fits[0].id}, {fits[0].size_gb:.1f} GB) instead." if fits else "")


def _http(base_url: str, path: str, body: Optional[Dict] = None, timeout: float = 5) -> Dict:
    import json
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base_url.rstrip("/") + path, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def verify(base_url: str, model: str, provider=None, http=_http, gpu_procs=None) -> Dict:
    """After a pull: is it listed, does a tiny real generation work, and is it on the GPU? device is "CUDA" when
    Ollama's /api/ps reports VRAM for it or nvidia-smi shows ollama holding GPU memory, else "CPU"."""
    if provider is None:
        from modules.ai.providers import OllamaProvider
        provider = OllamaProvider()
    full = model if ":" in model else model + ":latest"
    out = {"model": model, "listed": full in (_installed(base_url, provider) or set()), "inference": False,
           "reply": "", "device": "", "message": ""}
    if not out["listed"]:
        out["message"] = f"{model} downloaded, but Ollama doesn't list it."
        return out
    try:
        r = http(base_url, "/api/generate", {"model": model, "prompt": "Reply with the word OK.", "stream": False,
                                             "options": {"num_predict": 4}, "keep_alive": "2m"}, 180)
        out["reply"], out["inference"] = (r.get("response") or "").strip(), "error" not in r
    except Exception as e:
        out["message"] = f"{model} is installed but didn't answer a test prompt ({type(e).__name__}: {e})."
        return out
    vram = 0
    try:
        vram = sum(m.get("size_vram") or 0 for m in http(base_url, "/api/ps").get("models", [])
                   if full in (m.get("name"), m.get("model")) or model in (m.get("name"), m.get("model")))
    except Exception:
        pass
    if gpu_procs is None:
        from core import sysinfo
        gpu_procs = sysinfo.gpu_processes()
    on_gpu = vram > 0 or any("ollama" in p["name"].lower() and p.get("memory_mb") for p in gpu_procs)
    out["device"] = "CUDA" if on_gpu else "CPU"
    out["message"] = f"{model} works and is running on {'CUDA (the GPU)' if on_gpu else 'the CPU'}."
    return out


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
        if s.get("status") == "verifying":
            return f"{s['model']} downloaded — testing it"
        return (s.get("verify") or {}).get("message") or f"{s['model']} downloaded"
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
          wait: bool = False, hw=None) -> bool:
    """Pull ``model`` in the background (or in this thread with ``wait``). False — refusal() says why — when
    it's already installed or downloading, another pull runs, or it's too big for this PC."""
    global _refusal
    model = (model or "").strip()
    if not model:
        return False
    if provider is None:
        from modules.ai.providers import OllamaProvider
        provider = OllamaProvider()
    try:
        _refusal = precheck(model, _installed(base_url, provider), hw=hw)
    except Exception as e:                             # a failed check never blocks a pull
        log.debug("pull precheck failed: %s", e)
        _refusal = ""
    if _refusal:
        return False
    with _lock:
        if _state["running"]:
            _refusal = f"{_state['model']} is downloading; this one can start when it's done."
            return False
        _state.update(model=model, running=True, status="starting", percent=None, completed=0, total=0,
                      error="", done=False, started=time.time(), verify=None)
    _cancel.clear()
    say = notify or _notify

    def progress(p: Dict):
        with _lock:
            _state.update(status=p.get("status", ""), percent=p.get("percent"),
                          completed=p.get("completed", 0), total=p.get("total", 0))

    def run():
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
            with _lock:
                _state["status"] = "verifying"
            try:
                v = verify(base_url, model, provider=prov)
            except Exception as e:
                v = {"message": f"{model} downloaded; testing it failed ({e}).", "inference": False}
            with _lock:
                _state.update(verify=v, status="verified" if v.get("inference") else "unverified")
            say("SAINT's AI model is ready" if v.get("inference") else "SAINT's AI model needs a look", v["message"])
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


def auto_start(get_config=None, check=None, live=None) -> bool:
    """On installed Halo: when Ollama runs but the configured model isn't downloaded yet, follow (or start) its
    pull. Not in the live session: its disk is RAM, so gigabytes of model would fill memory and be gone on the
    next boot (the "Download model" button still works there). Returns True when a pull was started."""
    from core import health
    from core.paths import system_install
    if get_config is None:
        from core.config import config
        get_config = config.get
    if live is None:
        from core.provision import is_live as live
    if not system_install() or live() or get_config("ai.provider", "ollama") != "ollama":
        return False
    base, model = get_config("ai.base_url", "http://localhost:11434"), get_config("ai.model", "")
    r = (check or health.ollama)(base, model)
    if r["state"] == health.WORKING or r["state"] in (health.MISSING, health.FAILED):
        return False                                   # already there / Ollama not running: nothing to follow
    return start(base, model)
