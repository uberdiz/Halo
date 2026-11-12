"""
core/agent_catalog.py

Which AI agents and models suit this PC, and installing them in one click (data/agent_catalog.json).

    rate(hw)                 -> [Rating]: each entry "recommended", "will_run" or "too_heavy", with a one-line reason
                                and an estimated speed. Pure: same hardware, same answer (core.device_profile.Hardware).
    install(entry_id)        -> starts the install: Claude Code through the SAINT Store's queue, local models through
                                core.model_pull (progress shows in the downloads tray)
    windows_model_stores()   -> Ollama model folders on a mounted Windows disk, so models already downloaded there are
                                copied instead of downloaded again (for slow connections)

Claude Code is the default agent (it uses the person's Claude subscription, no API key); local models are the
offline fallback.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core import device_profile as dp

CATALOG = Path(__file__).resolve().parents[1] / "data" / "agent_catalog.json"
RECOMMENDED, WILL_RUN, TOO_HEAVY = "recommended", "will_run", "too_heavy"
STATUS_LABEL = {RECOMMENDED: "Recommended", WILL_RUN: "Will run", TOO_HEAVY: "Too heavy for this PC"}
OLLAMA_STORE = "/var/lib/ollama"              # the Arch ollama package's model folder


@dataclass
class Rating:
    id: str
    name: str
    kind: str
    status: str
    reason: str
    good_for: str
    size_gb: float
    tokens_per_s: Optional[int] = None      # rough, for "about N words a second"
    installed: bool = False


def load(path: Path = CATALOG) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))["agents"]


def speed(entry: Dict, hw: dp.Hardware, on_gpu: bool) -> Optional[int]:
    """Tokens a second, roughly: memory bandwidth over model size. Only to tell "snappy" from "slow"."""
    size = float(entry.get("size_gb") or 0)
    if not size or entry.get("kind") != "local":
        return None
    if on_gpu:
        return max(1, int(400 / size))                       # ~400 GB/s on a mid-range NVIDIA card
    threads = hw.cpu_threads or 4
    return max(1, int(min(60, threads * 3) / size))          # dual-channel DDR4/5, capped by the CPU


def rate(hw: dp.Hardware, entries: Optional[List[Dict]] = None, installed: Optional[set] = None) -> List[Rating]:
    entries = load() if entries is None else entries
    installed = installed or set()
    pick = dp.choose(hw).ollama_model
    room = hw.disk_free_gb - dp.RESERVE_GB
    gpu_ok = bool(hw.gpu_name) and hw.vram_gb >= dp.MIN_VRAM_GB
    out = []
    for e in entries:
        size = float(e.get("size_gb") or 0)
        if e["kind"] == "cloud":
            status, reason, tps = RECOMMENDED, e.get("needs", ""), None
        else:
            # Rounded like core.device_profile: 47.9 GB of RAM is a 48 GB PC (the OS keeps a little back).
            on_gpu = gpu_ok and round(hw.vram_gb) >= e.get("min_vram_gb", 99)
            fits_ram = round(hw.ram_gb) >= e.get("min_ram_gb", 99)
            tps = speed(e, hw, on_gpu)
            if size > room:
                status, reason = TOO_HEAVY, f"Needs {size:.0f} GB of disk; {max(0, room):.0f} GB is free beyond what stays yours."
            elif not (on_gpu or fits_ram):
                need = f"{e.get('min_vram_gb')} GB of GPU memory or {e.get('min_ram_gb')} GB of RAM"
                status, reason = TOO_HEAVY, f"Needs {need}; this PC has {hw.ram_gb:.0f} GB of RAM" + (
                    f" and {hw.vram_gb:.0f} GB on {hw.gpu_name}." if hw.gpu_name else ".")
            else:
                status = RECOMMENDED if e["id"] == pick else WILL_RUN
                where = f"on {hw.gpu_name}" if on_gpu else "on the CPU"
                reason = f"Runs {where}, about {tps} words a second."
        out.append(Rating(e["id"], e["name"], e["kind"], status, reason, e.get("good_for", ""), size, tps,
                          e["id"] in installed))
    order = {RECOMMENDED: 0, WILL_RUN: 1, TOO_HEAVY: 2}
    return sorted(out, key=lambda r: (order[r.status], r.kind != "cloud", -r.size_gb))


def can_run(query: str, hw: Optional[dp.Hardware] = None, entries: Optional[List[Dict]] = None) -> Optional[Dict]:
    """"Can my computer run a 14B model?" — answered with the catalog entry nearest that size (or named) and
    the same rules as rate(). None when the question names no size or model."""
    import re
    entries = [e for e in (load() if entries is None else entries) if e.get("kind") == "local"]
    q = (query or "").lower()
    entry = next((e for e in entries if e["id"] in q or e["name"].lower() in q), None)
    m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", q)
    if entry is None and m:
        want = float(m.group(1))
        entry = min(entries, key=lambda e: abs(float(e.get("params_b") or 0) - want), default=None)
    if entry is None:
        return None
    hw = hw or dp.detect()
    r = rate(hw, [entry])[0]
    return {"id": r.id, "name": r.name, "status": r.status, "label": STATUS_LABEL[r.status], "reason": r.reason,
            "asked_b": float(m.group(1)) if m else None, "params_b": entry.get("params_b"), "size_gb": r.size_gb}


def installed_ids(which: Callable[[str], Optional[str]] = shutil.which, models: Optional[List[str]] = None) -> set:
    """What's already here: the claude command, and the models Ollama lists."""
    have = set()
    if which("claude"):
        have.add("claude-code")
    if models is None:
        try:
            from core.config import config
            from modules.ai.providers import OllamaProvider
            models = [m.get("name", "") for m in OllamaProvider().list_models(
                config.get("ai.base_url", "http://localhost:11434"), timeout=3)]
        except Exception:
            models = []
    for name in models:
        have.add(name if ":" in name else f"{name}:latest")
    return have


def install(entry_id: str, entries: Optional[List[Dict]] = None, on_wait: Optional[Callable[[str], None]] = None) -> Dict:
    """Start installing one entry. {"ok", "message"}; the work goes on in the background."""
    entry = next((e for e in (load() if entries is None else entries) if e["id"] == entry_id), None)
    if entry is None:
        return {"ok": False, "message": f"There's no agent called {entry_id}."}
    how, _, ref = entry["install"].partition(":")
    if how == "ollama":
        from core import model_pull
        from core.config import config
        started = model_pull.start(config.get("ai.base_url", "http://localhost:11434"), ref)
        return {"ok": started, "message": f"Downloading {entry['name']} ({entry['size_gb']:.1f} GB)." if started
                else "Another model is downloading; this one can start when it's done."}
    if how == "featured":
        import threading
        from core import pkg_queue, store
        result = store.Result("featured", ref, entry["name"])
        threading.Thread(target=lambda: pkg_queue.run_plan(store.plan(result), on_wait=on_wait,
                                                           on_line=lambda _l: None),
                         daemon=True, name=f"install-{ref}").start()
        return {"ok": True, "message": f"Installing {entry['name']}."}
    return {"ok": False, "message": f"Don't know how to install {entry['name']}."}


# --------------------------------------------------------------------------- models already on Windows
WINDOWS_GLOBS = ("/mnt/*/Users/*/.ollama/models", "/run/media/*/*/Users/*/.ollama/models",
                 "/media/*/Users/*/.ollama/models")


def models_in(store: Path) -> List[str]:
    """Model names in an Ollama store: manifests/<registry>/<namespace>/<model>/<tag>."""
    found = []
    for tag in sorted(store.glob("manifests/*/*/*/*")):
        if tag.is_file():
            ns, model = tag.parent.parent.name, tag.parent.name
            found.append(f"{model}:{tag.name}" if ns == "library" else f"{ns}/{model}:{tag.name}")
    return found


def windows_model_stores(globs=WINDOWS_GLOBS) -> List[Dict]:
    """Ollama stores on mounted Windows disks: [{"path", "models", "size_gb"}], largest first."""
    out = []
    for pattern in globs:
        for path in glob.glob(pattern):
            store = Path(path)
            models = models_in(store)
            if not models:
                continue
            size = sum(f.stat().st_size for f in store.glob("blobs/*") if f.is_file())
            out.append({"path": str(store), "models": models, "size_gb": round(size / 1e9, 1)})
    return sorted(out, key=lambda s: -s["size_gb"])


def ollama_models_dir(run: Callable = None) -> str:
    """Where this system's Ollama keeps models: OLLAMA_MODELS from its service, else Ollama's default under its
    home (/var/lib/ollama on Arch)."""
    import subprocess
    run = run or subprocess.run
    try:
        env = run(["systemctl", "show", "ollama.service", "-p", "Environment", "--value"], capture_output=True,
                  text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        env = ""
    for item in env.split():
        if item.startswith("OLLAMA_MODELS="):
            return item.split("=", 1)[1]
    return f"{OLLAMA_STORE}/.ollama/models"


def reuse_steps(store: str, dest: Optional[str] = None):
    """Copy a Windows Ollama store's blobs and manifests into HalOS's (existing files are kept, never
    overwritten), then give them to the ollama user. Argument lists only; one admin prompt through the queue."""
    from core import saintos_apps as sa
    src, dest = Path(store), dest or ollama_models_dir()
    copy = ["pkexec", "cp", "-rn", "--", str(src / "blobs"), str(src / "manifests"), dest.rstrip("/") + "/"]
    own = ["pkexec", "chown", "-R", "ollama:ollama", dest]
    return [sa.Step("Copying AI models from Windows", copy, ["windows-models"], needs_admin=True),
            sa.Step("Giving them to Ollama", own, ["windows-models"], needs_admin=True)]
