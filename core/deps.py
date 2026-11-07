"""
core/deps.py

Dependency manager: what each subsystem needs, declared once, and one path to get it working:

    detect   which of the subsystem's dependencies are present (package, module, file, remote, service)
    install  a plan for the missing ones, shown to the user and run only after they confirm; admin steps
             go through pkexec (its own password prompt) exactly like the App Installer
             (core/saintos_apps.run_plan, which also explains failures in plain words)
    verify   the subsystem's light health check (core/health.py)
    test     its full health check (a real inference / synthesis / transcription) for the heavy ones

The manifests below are data: kinds are pacman, pip, flatpak-remote, service, asset (a SAINT model
download) and ollama-model. ``when`` limits a dependency to machines it applies to ("linux", "pacman",
"nvidia"). Names are checked against strict patterns before they reach a command.

    python -m core.deps                 detect every subsystem
    python -m core.deps ollama --install
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from core import health

FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"

# subsystem -> {"label", "deps": [{"kind", "name", ...}]}. Optional per dep: "binary" (present when on PATH),
# "module" (pip: import name), "when" (condition), "why" (shown in the plan).
MANIFESTS: Dict[str, Dict] = {
    "ollama": {"label": "Local AI (Ollama)", "deps": [
        {"kind": "pacman", "name": "ollama", "binary": "ollama", "when": "pacman", "why": "runs the local model"},
        {"kind": "service", "name": "ollama.service", "when": "linux", "why": "starts Ollama with the PC"},
        {"kind": "ollama-model", "name": "@configured", "why": "the model SAINT talks to"},
    ]},
    "kokoro": {"label": "Voice (Kokoro)", "deps": [
        {"kind": "pip", "name": "onnxruntime", "module": "onnxruntime", "why": "runs Kokoro"},
        {"kind": "pip", "name": "kokoro-onnx", "module": "kokoro_onnx", "why": "the Kokoro voice engine"},
        {"kind": "pip", "name": "misaki[en]", "module": "misaki", "why": "turns text into phonemes"},
        {"kind": "pip", "name": "sounddevice", "module": "sounddevice", "why": "plays the voice"},
        {"kind": "asset", "name": "kokoro", "why": "Kokoro's voice files (~340 MB)"},
    ]},
    "whisper": {"label": "Speech recognition (Whisper)", "deps": [
        {"kind": "pip", "name": "faster-whisper", "module": "faster_whisper", "why": "speech-to-text"},
        {"kind": "asset", "name": "whisper", "why": "the base.en model (~150 MB)"},
    ]},
    "flatpak": {"label": "Flatpak / Flathub", "deps": [
        {"kind": "pacman", "name": "flatpak", "binary": "flatpak", "when": "pacman", "why": "installs Store apps"},
        {"kind": "flatpak-remote", "name": "flathub", "when": "linux", "why": "where Flatpak apps come from"},
    ]},
    "pacman": {"label": "Packages (pacman)", "deps": [
        {"kind": "pacman", "name": "archlinux-keyring", "when": "pacman", "why": "verifies package signatures"},
    ]},
    "network": {"label": "Network", "deps": [
        {"kind": "pacman", "name": "networkmanager", "binary": "nmcli", "when": "pacman", "why": "connects"},
        {"kind": "service", "name": "NetworkManager.service", "when": "pacman", "why": "starts networking"},
    ]},
    "gpu": {"label": "GPU driver", "deps": [
        {"kind": "pacman", "name": "nvidia-open", "when": "nvidia", "why": "the NVIDIA driver (RTX 50 needs it)"},
        {"kind": "pacman", "name": "nvidia-utils", "binary": "nvidia-smi", "when": "nvidia",
         "why": "CUDA for the local AI"},
    ]},
    "ai_gpu": {"label": "AI on the GPU", "deps": [
        {"kind": "pacman", "name": "ollama-cuda", "when": "nvidia", "why": "Ollama on the GPU (core/provision.py)"},
    ]},
    "storage": {"label": "Storage", "deps": []},
}

_SAFE_PKG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_SAFE_PIP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,_-]+\])?$")
_SAFE_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9@._-]*\.service$")
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*(:[A-Za-z0-9._-]+)?$")


@dataclass
class Action:
    """One step of an install plan: a command (argv) or an in-process call (fn)."""
    label: str
    argv: List[str] = field(default_factory=list)
    fn: Optional[Callable[[], bool]] = None
    needs_admin: bool = False
    deps: List[str] = field(default_factory=list)


@dataclass
class Env:
    """What the manager may touch — all injectable for tests."""
    which: Callable[[str], Optional[str]] = shutil.which
    run: Callable = health._run
    find_spec: Callable = importlib.util.find_spec
    linux: bool = sys.platform.startswith("linux")
    has_nvidia: Optional[Callable[[], bool]] = None
    asset_ready: Optional[Callable[[str], bool]] = None
    model_present: Optional[Callable[[str], bool]] = None
    flathub: Optional[Callable[[], bool]] = None
    python: str = sys.executable
    prefix_writable: Optional[bool] = None


def _nvidia_present(env: Env) -> bool:
    if env.has_nvidia is not None:
        return env.has_nvidia()
    if os.path.exists("/proc/driver/nvidia/gpus"):
        return True
    if env.which("lspci"):
        try:
            out = env.run(["lspci"], timeout=8).stdout or ""
            return any("NVIDIA" in l and any(k in l for k in health._DISPLAY) for l in out.splitlines())
        except Exception:
            return False
    return False


def applies(dep: Dict, env: Env) -> bool:
    when = dep.get("when", "")
    if not when:
        return True
    if when == "linux":
        return env.linux
    if when == "pacman":
        return env.linux and bool(env.which("pacman"))
    if when == "nvidia":
        return env.linux and bool(env.which("pacman")) and _nvidia_present(env)
    return False


def _configured_model() -> str:
    from core.config import OLLAMA_DEFAULT_MODEL, config
    return config.get("ai.model", "") or OLLAMA_DEFAULT_MODEL


def _model_name(dep: Dict) -> str:
    return _configured_model() if dep["name"] == "@configured" else dep["name"]


def present(dep: Dict, env: Env) -> bool:
    """Is this one dependency already there?"""
    kind, name = dep["kind"], dep["name"]
    if dep.get("binary") and env.which(dep["binary"]):
        return True
    if kind == "pacman":
        if dep.get("binary"):
            return False
        try:
            return env.run(["pacman", "-Q", name], timeout=10).returncode == 0
        except Exception:
            return False
    if kind == "pip":
        try:
            return env.find_spec(dep.get("module") or name) is not None
        except (ImportError, ValueError):
            return False
    if kind == "asset":
        if env.asset_ready is not None:
            return env.asset_ready(name)
        from core import model_assets
        return bool({"kokoro": model_assets.kokoro_ready, "whisper": model_assets.whisper_ready}[name]())
    if kind == "flatpak-remote":
        if env.flathub is not None:
            return env.flathub()
        return health.flatpak(run=env.run, which=env.which, linux=env.linux)["state"] == health.WORKING
    if kind == "service":
        try:
            return env.run(["systemctl", "is-enabled", "--quiet", name], timeout=10).returncode == 0
        except Exception:
            return False
    if kind == "ollama-model":
        model = _model_name(dep)
        if env.model_present is not None:
            return env.model_present(model)
        return health.ollama(_base_url(), model)["state"] == health.WORKING
    raise ValueError(f"unknown dependency kind {kind!r}")


def _base_url() -> str:
    from core.config import config
    return config.get("ai.base_url", "http://localhost:11434")


def detect(key: str, env: Optional[Env] = None) -> List[Dict]:
    """[{"kind", "name", "why", "present"}] for the dependencies that apply to this machine."""
    env = env or Env()
    out = []
    for dep in MANIFESTS[key]["deps"]:
        if not applies(dep, env):
            continue
        name = _model_name(dep) if dep["kind"] == "ollama-model" else dep["name"]
        out.append({"kind": dep["kind"], "name": name, "why": dep.get("why", ""), "present": present(dep, env)})
    return out


def _pip_argv(names: List[str], env: Env) -> (List[str], bool):
    writable = env.prefix_writable if env.prefix_writable is not None else os.access(sys.prefix, os.W_OK)
    argv = [env.python, "-m", "pip", "install", "--disable-pip-version-check", *names]
    return (argv if writable else ["pkexec", *argv]), not writable


def plan(key: str, env: Optional[Env] = None, missing: Optional[List[Dict]] = None) -> List[Action]:
    """The steps that install what ``key`` is missing, in a safe order: system packages (one admin prompt),
    services, Python packages, remotes, downloads."""
    env = env or Env()
    deps = [d for d in MANIFESTS[key]["deps"] if applies(d, env)]
    if missing is None:
        missing = [d for d in deps if not present(d, env)]
    by_kind: Dict[str, List[Dict]] = {}
    for d in missing:
        by_kind.setdefault(d["kind"], []).append(d)
    actions: List[Action] = []
    pk = [d["name"] for d in by_kind.get("pacman", []) if _SAFE_PKG.match(d["name"])]
    if pk:
        actions.append(Action(f"Install {', '.join(pk)} (pacman, asks for your password)",
                              ["pkexec", "pacman", "-Syu", "--needed", "--noconfirm", *pk], needs_admin=True,
                              deps=pk))
    for d in by_kind.get("service", []):
        if _SAFE_UNIT.match(d["name"]):
            actions.append(Action(f"Start {d['name']} now and at every boot",
                                  ["pkexec", "systemctl", "enable", "--now", d["name"]], needs_admin=True,
                                  deps=[d["name"]]))
    pip = [d["name"] for d in by_kind.get("pip", []) if _SAFE_PIP.match(d["name"])]
    if pip:
        argv, admin = _pip_argv(pip, env)
        actions.append(Action(f"Install Python packages {', '.join(pip)} into SAINT", argv, needs_admin=admin,
                              deps=pip))
    for d in by_kind.get("flatpak-remote", []):
        if d["name"] == "flathub":
            actions.append(Action("Add the Flathub source for your user",
                                  ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB],
                                  deps=["flathub"]))
    for d in by_kind.get("asset", []):
        name = d["name"]

        def fetch(name=name):
            from core import model_assets
            return bool({"kokoro": model_assets.ensure_kokoro, "whisper": model_assets.ensure_whisper}[name]())
        actions.append(Action(f"Download SAINT's {name} model files", fn=fetch, deps=[name]))
    for d in by_kind.get("ollama-model", []):
        model = _model_name(d)
        if not _SAFE_MODEL.match(model):
            continue

        def pull(model=model):
            from core import model_pull
            model_pull.start(_base_url(), model, wait=True)
            return bool(model_pull.state().get("done"))
        actions.append(Action(f"Download the AI model {model} (progress on the System page)", fn=pull,
                              deps=[model]))
    return actions


def install(key: str, confirm: Callable[[List[Action]], bool], env: Optional[Env] = None,
            on_line: Callable[[str], None] = lambda _l: None, popen: Callable = subprocess.Popen,
            verify: Optional[Callable[[str, bool], Dict]] = None, test: bool = True,
            blockers: Optional[Callable[[], tuple]] = None) -> Dict:
    """detect → (confirm) → install → verify → test. Nothing runs unless ``confirm(plan)`` returns True.

    Returns {"key", "status": "ok"|"failed"|"cancelled"|"blocked"|"nothing to do", "steps": [labels],
    "errors": {dep: why}, "verify": health result, "test": health result or None}."""
    from core import saintos_apps as sa
    env = env or Env()
    check = verify or (lambda k, full: health.check(k, full=full))
    actions = plan(key, env)
    labels = [a.label for a in actions]
    out = {"key": key, "steps": labels, "errors": {}, "verify": None, "test": None}
    if actions:
        if any(a.argv[1:2] == ["pacman"] for a in actions):
            errs, _warn = (blockers or sa.blockers)()
            if errs:
                return {**out, "status": "blocked", "errors": {"pacman": errs[0]}}
        if not confirm(actions):
            return {**out, "status": "cancelled"}
        for a in actions:
            if a.fn is not None:
                on_line(f"==> {a.label}")
                try:
                    ok = bool(a.fn())
                    why = "" if ok else "it didn't finish (see SAINT's log)"
                except Exception as e:
                    ok, why = False, f"{type(e).__name__}: {e}"
                on_line("    done" if ok else f"    FAILED: {why}")
                if not ok:
                    for d in a.deps:
                        out["errors"][d] = why
            else:
                errors: Dict[str, str] = {}
                result = sa.run_plan([sa.Step(a.label, a.argv, list(a.deps), a.needs_admin)], on_line=on_line,
                                     popen=popen, errors=errors)
                for d, ok in result.items():
                    if not ok:
                        out["errors"][d] = errors.get(d, "failed")
    out["verify"] = check(key, False)
    heavy = any(k == key and h for k, _, h in health.SUBSYSTEMS)
    if test and heavy and out["verify"]["state"] in (health.WORKING, health.NOT_TESTED, health.DEGRADED):
        out["test"] = check(key, True)
    final = out["test"] or out["verify"]
    if not actions:
        out["status"] = "nothing to do"
    else:
        out["status"] = "ok" if not out["errors"] and final["state"] in (health.WORKING, health.DEGRADED,
                                                                          health.NOT_TESTED) else "failed"
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="SAINT dependency manager")
    ap.add_argument("subsystem", nargs="?", choices=sorted(MANIFESTS))
    ap.add_argument("--install", action="store_true", help="install what's missing (asks first)")
    args = ap.parse_args(argv)
    keys = [args.subsystem] if args.subsystem else list(MANIFESTS)
    for key in keys:
        found = detect(key)
        print(f"{MANIFESTS[key]['label']}: " + (", ".join(f"{d['name']} {'ok' if d['present'] else 'MISSING'}"
                                                       for d in found) or "nothing to install"))
    if args.install and args.subsystem:
        def ask(actions):
            print("\n".join(f"  - {a.label}" for a in actions))
            return input("Go ahead? [y/N] ").strip().lower() == "y"
        res = install(args.subsystem, ask, on_line=print)
        print(f"{res['status']}: {res['verify'] and res['verify']['detail']}")
        return 0 if res["status"] in ("ok", "nothing to do") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
