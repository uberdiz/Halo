"""
core/provision.py

First-boot setup of SAINT's AI for this PC, in the installed system only (never /run/archiso: its RAM overlay would
fill). Run as root by saint-ollama-model.service before it pulls the Ollama model:

    1. core/device_profile.py picks the tier; written to /var/lib/saint/device-profile.json (+ .env for the script)
    2. NVIDIA tiers only: the CUDA pieces (below); a failure falls back to the CPU tier and records why
    3. the Whisper model is downloaded to /var/lib/saint/whisper, which every user's SAINT reads
       (core/model_assets.whisper_source), so the first spoken word has no wait
    4. the service's own ExecStart then pulls the model the profile names (usr/libexec/saintos/ollama-model)

Exit 1 (systemd retries in 2 minutes) while there's no network or pacman's database is busy. Every step is resumable:
pacman and pip skip what's there, Hugging Face resumes partial files, and progress is kept in provision.json.

CUDA is installed here rather than shipped in the ISO, only on PCs with a working NVIDIA driver:
    ollama-cuda + cuda     412 MB + 2.6 GB download, 6.1 GB installed. Would add 3 GB to a ~4 GB image for every PC.
    Whisper's libraries    CUDA 12 (ctranslate2 links libcublas.so.12 and libcudnn.so.9; Arch's cuda is 13 and has no
                           cuDNN) as NVIDIA's wheels: 1.4 GB download, ~3 GB in /var/lib/saint/gpu, which /usr/bin/saint
                           puts on LD_LIBRARY_PATH through /var/lib/saint/gpu/env.

SAINT's side (on_saint_start) copies the profile into the user's config unless they changed it, and says what's going on
through its usual notifications. The Ollama download's progress is core/model_pull.py's.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core import device_profile as dp

log = logging.getLogger("saint.provision")

STATE_DIR = Path(os.environ.get("HALO_SAINT_STATE") or "/var/lib/saint")
PY = "/opt/saint/python/bin/python3.12"       # has pip; the venv doesn't, and /opt stays as the package left it
# ctranslate2 4.8 needs these sonames. Pinned like everything else SAINT runs.
GPU_WHEELS = ["nvidia-cublas-cu12==12.9.3.13", "nvidia-cudnn-cu12==9.28.1.4"]
_RETRYABLE = re.compile(r"could not resolve|failed retrieving|failed to synchronize|unable to lock|timed? ?out|"
                        r"temporary failure|connection|network is unreachable|no route to host|failed to download", re.I)
RETRY = 1


class Retry(Exception):
    """Try again in a while (no network, pacman busy)."""


def _paths(root: Path) -> Dict[str, Path]:
    return {"state": root / "provision.json", "profile": root / "device-profile.json",
            "env": root / "device-profile.env", "gpu": root / "gpu", "gpu_env": root / "gpu" / "env",
            "whisper": root / "whisper"}


def is_live() -> bool:
    """The live ISO session."""
    if os.path.isdir("/run/archiso"):
        return True
    try:
        return "archisobasedir" in Path("/proc/cmdline").read_text(encoding="utf-8")
    except OSError:
        return False


def _write_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o644)                        # read by every user's SAINT; holds no secrets
    os.replace(tmp, path)


def read_json(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_profile(profile: dp.Profile, root: Path):
    p = _paths(root)
    _write_json(p["profile"], profile.to_dict())
    p["env"].write_text(f"HALO_PROFILE_MODEL={profile.ollama_model}\n", encoding="utf-8")
    os.chmod(p["env"], 0o644)


def _online(host: str = "registry.ollama.ai", port: int = 443, timeout: float = 5) -> bool:
    import socket
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def _cmd(run: Callable, argv: List[str], timeout: float = 7200) -> subprocess.CompletedProcess:
    log.info("running: %s", " ".join(argv))
    return run(argv, capture_output=True, text=True, timeout=timeout)


def _tail(res) -> str:
    return ((res.stdout or "") + (res.stderr or "")).strip()[-400:]


def install_ollama_cuda(run: Callable) -> bool:
    """ollama-cuda, without a system upgrade if this system's package database still matches the mirror (a fresh
    install). Otherwise a full upgrade, Arch's only safe way. Returns True when that upgrade ran: its new NVIDIA
    user-space libraries need a restart to match the loaded driver."""
    if _cmd(run, ["pacman", "-Q", "ollama-cuda"]).returncode == 0:
        return False
    if _cmd(run, ["pacman", "-S", "--needed", "--noconfirm", "ollama-cuda"]).returncode == 0:
        return False
    res = _cmd(run, ["pacman", "-Syu", "--needed", "--noconfirm", "ollama-cuda"])
    if res.returncode != 0:
        text = _tail(res)
        if _RETRYABLE.search(text):
            raise Retry(text)
        raise RuntimeError(f"pacman couldn't install ollama-cuda: {text}")
    return True


def find_library_dirs(site: Path) -> List[str]:
    """The folders of the wheels' libcublas.so.12 and libcudnn.so.9 (their layout is the wheel's, not ours)."""
    dirs = []
    for lib in ("libcublas.so.12", "libcudnn.so.9"):
        found = next(iter(sorted(site.rglob(lib))), None)
        if found is None:
            return []
        if str(found.parent) not in dirs:
            dirs.append(str(found.parent))
    return dirs


def install_whisper_libraries(run: Callable, root: Path):
    p = _paths(root)
    site = p["gpu"] / "site"
    dirs = find_library_dirs(site) if site.is_dir() else []
    if not dirs:
        res = _cmd(run, [PY, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "--only-binary", ":all:",
                         "--upgrade", "--target", str(site), *GPU_WHEELS])
        if res.returncode != 0:
            text = _tail(res)
            if _RETRYABLE.search(text):
                raise Retry(text)
            raise RuntimeError(f"pip couldn't install Whisper's CUDA libraries: {text}")
        dirs = find_library_dirs(site)
        if not dirs:
            raise RuntimeError("the CUDA wheels installed but libcublas.so.12 / libcudnn.so.9 aren't in them")
    p["gpu_env"].write_text('export LD_LIBRARY_PATH="%s${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n' % ":".join(dirs),
                            encoding="utf-8")
    os.chmod(p["gpu_env"], 0o644)


def download_whisper(model: str, cache_dir: str):
    from faster_whisper.utils import download_model
    download_model(model, cache_dir=cache_dir)


def whisper_present(model: str, root: Path) -> bool:
    return whisper_snapshot(model, _paths(root)["whisper"]) is not None


def whisper_snapshot(model: str, cache: Path) -> Optional[Path]:
    """A complete downloaded model in a Hugging Face cache folder, or None."""
    repo = dp.WHISPER_REPOS.get(model)
    if not repo:
        return None
    folder = Path(cache) / ("models--" + repo.replace("/", "--"))
    try:
        commit = (folder / "refs" / "main").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    snap = folder / "snapshots" / commit
    return snap if (snap / "model.bin").is_file() and (snap / "config.json").is_file() else None


def run(hardware: Optional[dp.Hardware] = None, runner: Callable = subprocess.run, online: Callable[[], bool] = _online,
        fetch: Callable[[str, str], None] = download_whisper, root: Path = None, force: bool = False,
        restart_ollama: bool = True) -> int:
    """One pass of the setup. 0: done, go on to the Ollama model. RETRY: no network yet."""
    root = Path(root or STATE_DIR)
    p = _paths(root)
    state = {} if force else read_json(p["state"])

    def stage(name: str, **extra):
        state.update(stage=name, updated=time.strftime("%Y-%m-%dT%H:%M:%S"), **extra)
        _write_json(p["state"], state)

    hw = hardware or dp.detect()
    profile = dp.choose(hw)
    gpu = state.get("gpu") or {}
    if gpu.get("status") == "failed":            # stays failed until `device-setup --force`: never loop on a real error
        profile = dp.cpu_fallback(profile, f"GPU setup failed: {gpu.get('why')}", hw)
    save_profile(profile, root)                  # the tier is known even while offline
    stage("waiting for network")
    if not online():
        print("no network yet")
        return RETRY
    try:
        if profile.use_gpu and gpu.get("status") != "ready":
            stage("gpu", gpu={"status": "installing"})
            try:
                upgraded = install_ollama_cuda(runner)
                install_whisper_libraries(runner, root)
            except Retry:
                raise
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                why = str(e)[:400]
                log.warning("GPU setup failed: %s", why)
                print(f"GPU setup failed, using the CPU: {why}")
                state["gpu"] = {"status": "failed", "why": why}
                profile = dp.cpu_fallback(profile, f"GPU setup failed: {why}", hw)
                save_profile(profile, root)
            else:
                state["gpu"] = {"status": "ready", "restart_needed": upgraded}
                if restart_ollama:
                    _cmd(runner, ["systemctl", "restart", "ollama.service"], timeout=60)
        if not whisper_present(profile.whisper_model, root):
            stage("whisper")
            try:
                fetch(profile.whisper_model, str(p["whisper"]))
            except Exception as e:                   # huggingface_hub and requests raise many kinds
                raise Retry(f"{type(e).__name__}: {e}") from e
            if not whisper_present(profile.whisper_model, root):
                raise Retry(f"{profile.whisper_model} isn't complete after the download")
    except Retry as e:
        print(f"retrying later: {e}")
        stage("waiting to retry", detail=str(e)[:300])
        return RETRY
    stage("ready", detail="")
    print(f"tier {profile.tier}: Ollama {profile.ollama_model or '(none)'}, Whisper {profile.whisper_model} "
          f"({profile.whisper_device}/{profile.whisper_compute})")
    return 0


# ---------------- SAINT's side ----------------

def status(root: Path = None) -> Dict:
    root = Path(root or STATE_DIR)
    p = _paths(root)
    return {"state": read_json(p["state"]), "profile": read_json(p["profile"])}


STAGE_WORDS = {"waiting for network": "Waiting for a network", "waiting to retry": "Waiting to try again",
               "gpu": "Installing CUDA for your NVIDIA GPU (about 4 GB)", "whisper": "Downloading the speech model"}


def describe(st: Optional[Dict] = None) -> str:
    """One line for the AI page: what's set up for this PC, or what's happening now."""
    st = st if st is not None else status()
    profile, state = st.get("profile") or {}, st.get("state") or {}
    if not profile:
        return ""
    device = "GPU" if profile.get("whisper_device") == "cuda" else "CPU"
    line = (f"This PC: {profile.get('reason')}. Tier {profile.get('tier')}: {profile.get('ollama_model') or 'no local model'}, "
            f"Whisper {profile.get('whisper_model')} on the {device}, Kokoro voice.")
    now = STAGE_WORDS.get(state.get("stage", ""))
    if now:
        line += f" {now}…"
    if (state.get("gpu") or {}).get("restart_needed"):
        line += " Restart once to finish the GPU setup."
    for note in profile.get("notes") or []:
        line += f" {note}"
    return line


def sync_config(st: Optional[Dict] = None, cfg=None) -> List[str]:
    """Copy a finished profile into this user's config (settings they changed stay). Returns the keys changed."""
    st = st if st is not None else status()
    if (st.get("state") or {}).get("stage") != "ready" or not st.get("profile"):
        return []
    if cfg is None:
        from core.config import config as cfg
    from core.config import DEFAULT_CONFIG

    def default(key):
        node = DEFAULT_CONFIG
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        return node
    return dp.apply_to_config(st["profile"], cfg.get, cfg.set, default)


def _notify(title: str, message: str):
    from core.events import EventType, event_bus
    event_bus.emit_event(EventType.NOTIFY, {"title": title, "message": message, "icon": "download"})


def _apply_and_announce(st: Dict, say: Callable[[str, str], None], sync: Callable = sync_config):
    changed = sync(st)
    if changed:
        from core.events import EventType, event_bus
        event_bus.emit_event(EventType.SETTINGS_CHANGED, {})
        log.info("device profile applied: %s", changed)
    from core.config import config
    gpu = (st.get("state") or {}).get("gpu") or {}
    notice = f"{(st.get('profile') or {}).get('tier')}/{gpu.get('status', 'none')}"
    if changed or config.get("device_profile.notice", "") != notice:
        config.set("device_profile.notice", notice)
        if gpu.get("status") == "failed":
            say("SAINT's AI is using the CPU", f"The GPU setup failed: {gpu.get('why')}")
        elif gpu.get("restart_needed"):
            say("Restart to finish GPU setup", "CUDA is installed; a restart makes the driver and libraries match.")
        elif changed:
            say("SAINT's AI is set up for this PC", describe(st))


def on_saint_start(say: Callable[[str, str], None] = None, interval: float = 15, wait: Callable = time.sleep) -> bool:
    """Called from a worker thread once SAINT is up, on HalOS. Applies the profile, following the setup while the
    system service works, then hands over to core/model_pull.py for the Ollama download. False when not on HalOS."""
    from core.paths import system_install
    if not system_install() or not _paths(STATE_DIR)["profile"].exists():
        return False
    say = say or _notify
    announced = ""
    while True:
        st = status()
        current = (st.get("state") or {}).get("stage", "")
        if current != "ready":
            if current != announced and current in STAGE_WORDS:
                announced = current
                say("Setting up SAINT's AI", describe(st))
            wait(interval)
            continue
        _apply_and_announce(st, say)
        return True


def main(argv: Optional[List[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if is_live():
        print("the live session: nothing to set up")
        return 0
    return run(force="--force" in args)


if __name__ == "__main__":
    threading.current_thread().name = "provision"
    sys.exit(main())
