"""
core/health.py

One health model for every subsystem SAINT and Halo depend on. Each check answers from the running
system — a real inference, a real synthesis, a real transcription, the package manager's own files, a
real connection — never from the config alone, has a timeout, and says why in plain words. Results use
one vocabulary so every page shows the same words for the same facts:

    Working     the check ran and the subsystem did its job
    Degraded    it works, but not the way it should (fallback engine, low space, model still downloading)
    Missing     it isn't installed / downloaded
    Failed      it's there but the check failed (and ``detail`` says how)
    Not tested  the check couldn't or didn't run yet (e.g. heavy checks before "Run full check", or
                Linux-only checks on Windows)

``run_all(full=False)`` is cheap enough for a page that refreshes (no model calls); ``run_all(full=True)``
also runs the heavy checks (Ollama inference, Kokoro synthesis, Whisper transcription of a synthetic clip),
whose results are then remembered for the light runs. core/deps.py uses these checks to verify installs.
"""

from __future__ import annotations

import concurrent.futures as _cf
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, List, Optional

WORKING, DEGRADED, MISSING, FAILED, NOT_TESTED = "working", "degraded", "missing", "failed", "not tested"
STATES = (WORKING, DEGRADED, MISSING, FAILED, NOT_TESTED)
LABELS = {WORKING: "Working", DEGRADED: "Degraded", MISSING: "Missing", FAILED: "Failed", NOT_TESTED: "Not tested"}

# (key, label, heavy). Heavy checks call a model and only run in a full check.
SUBSYSTEMS = [
    ("ollama", "Language model", True),
    ("kokoro", "Voice (Kokoro)", True),
    ("whisper", "Speech recognition", True),
    ("ai_gpu", "AI on the GPU", True),
    ("flatpak", "Flatpak / Flathub", False),
    ("pacman", "Packages (pacman)", False),
    ("network", "Network", False),
    ("gpu", "GPU", False),
    ("storage", "Storage", False),
]
# Seconds each check may take before it's reported as Failed (light, full).
TIMEOUTS = {"ollama": (6, 120), "kokoro": (5, 90), "whisper": (5, 120), "ai_gpu": (12, 300)}
DEFAULT_TIMEOUT = 15

_linux = sys.platform.startswith("linux")


def _result(state: str, detail: str, **extra) -> Dict:
    return {"state": state, "detail": detail, "at": time.strftime("%H:%M:%S"), **extra}


def _run(argv: List[str], timeout: float = 8) -> subprocess.CompletedProcess:
    """Run a command with a timeout; raises FileNotFoundError / TimeoutExpired like subprocess does."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _cfg(key: str, default=""):
    try:
        from core.config import config
        return config.get(key, default)
    except Exception:
        return default


# --------------------------------------------------------------------------- Ollama
def ollama(base_url: str, model: str, get: Optional[Callable] = None) -> Dict:
    """Is Ollama answering, and is the configured model actually downloaded? (No inference: cheap enough to
    run every few seconds.)"""
    get = get or _get
    base = (base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        tags = get(base + "/api/tags")
    except Exception as e:
        if not shutil.which("ollama"):
            return _result(MISSING, "Ollama isn't installed")
        return _result(FAILED, f"Ollama is installed but not answering ({type(e).__name__})")
    names = [m.get("name", "") for m in (tags or {}).get("models", [])]
    want = (model or "").strip()
    pulling = _pull_line(want)
    if not names:
        return _result(DEGRADED, pulling or "Ollama is running but has no models", models=names)
    if want and not any(n == want or n.split(":")[0] == want or n == f"{want}:latest" for n in names):
        return _result(DEGRADED, pulling or f"model {want} isn't downloaded (have: {', '.join(names[:4])})",
                       models=names)
    return _result(WORKING, f"{want or names[0]} downloaded", models=names)


def _pull_line(model: str) -> str:
    """'Downloading llama3.1:8b — 43% …' while core/model_pull.py is pulling that model."""
    try:
        from core import model_pull
        s = model_pull.state()
        return model_pull.describe(s) if s.get("running") and (not model or s.get("model") == model) else ""
    except Exception:
        return ""


def ollama_inference(base_url: str, model: str, post: Optional[Callable] = None, timeout: float = 120) -> Dict:
    """Send one real prompt and check a non-empty answer comes back."""
    post = post or _post
    base = (base_url or "http://127.0.0.1:11434").rstrip("/")
    t0 = time.monotonic()
    try:
        res = post(base + "/api/generate", {"model": model, "prompt": "Reply with the single word: ready",
                                            "stream": False, "options": {"num_predict": 8}}, timeout)
    except Exception as e:
        return _result(FAILED, f"inference failed: {type(e).__name__}: {e}"[:300])
    text = ((res or {}).get("response") or "").strip()
    if not text:
        return _result(FAILED, "the model answered with nothing")
    return _result(WORKING, f"{model} answered {text[:40]!r} in {time.monotonic() - t0:.1f}s")


def ollama_check(full: bool = False, base_url: str = "", model: str = "", get=None, post=None,
                 timeout: float = 110) -> Dict:
    """Ollama for the dashboard: API + model present; with ``full`` also one real reply."""
    if (_cfg("ai.provider", "ollama") or "ollama") != "ollama" and not base_url:
        return _result(NOT_TESTED, f"SAINT uses the {_cfg('ai.provider')} provider, not Ollama")
    base = base_url or _cfg("ai.base_url", "http://localhost:11434")
    model = model or _cfg("ai.model", "")
    presence = ollama(base, model, get=get)
    if presence["state"] != WORKING or not full:
        return presence
    names = presence.get("models") or []
    use = next((n for n in names if n == model), None) or next(
        (n for n in names if n.split(":")[0] == model or n == f"{model}:latest"), model)
    return ollama_inference(base, use, post=post, timeout=timeout)


# --------------------------------------------------------------------------- voice
def tts(service) -> Dict:
    """What the running TTS service really speaks with."""
    if service is None:
        return _result(NOT_TESTED, "voice not started")
    engine = getattr(service, "_engine_type", "") or ""
    if not engine:
        err = getattr(service, "_last_error", None) or getattr(service, "_load_error", None)
        return _result(FAILED if err else NOT_TESTED, str(err) if err else "voice not loaded yet", engine="")
    if engine == "kokoro":
        fell_back = bool((getattr(service, "_device_info", {}) or {}).get("fell_back"))
        return _result(DEGRADED if fell_back else WORKING, "Kokoro" + (" on CPU fallback" if fell_back else ""),
                       engine=engine)
    if engine in ("espeak", "sapi"):
        return _result(DEGRADED, f"{'espeak-ng' if engine == 'espeak' else 'Windows voice'} — Kokoro isn't loaded",
                       engine=engine)
    return _result(WORKING, engine, engine=engine)


def _tts_service():
    try:
        from modules.voice.tts_service import TTSService
        return getattr(TTSService, "_instance", None)
    except Exception:
        return None


def _kokoro_available() -> bool:
    from modules.voice import kokoro_onnx
    return bool(kokoro_onnx.available())


def kokoro(full: bool = False, service=None, available: Optional[Callable[[], bool]] = None,
           test: Optional[Callable[..., Dict]] = None) -> Dict:
    """Kokoro: model files present; with ``full`` a real synthesis (not played). Also says when SAINT is
    speaking with a fallback engine although Kokoro works."""
    try:
        have = (available or _kokoro_available)()
    except Exception as e:
        return _result(FAILED, f"can't load the Kokoro runtime: {type(e).__name__}: {e}"[:300])
    if not have:
        return _result(MISSING, "Kokoro voice files aren't installed")
    service = service if service is not None else _tts_service()
    running = tts(service) if service is not None else None
    if not full:
        if running and running["state"] != NOT_TESTED:
            return running
        return _result(NOT_TESTED, "voice files present; synthesis not tested yet")
    if test is None:
        from core.voice_check import test_kokoro as test
    r = test(play=False, download=False)
    if not r.get("ok"):
        return _result(FAILED, f"synthesis failed: {r.get('detail', '')}"[:300])
    if running and running.get("engine") in ("espeak", "sapi"):
        return _result(DEGRADED, f"Kokoro works ({r.get('detail')}), but SAINT is speaking with "
                                 f"{'espeak-ng' if running['engine'] == 'espeak' else 'the Windows voice'}")
    return _result(WORKING, r.get("detail", "synthesised"))


WHISPER_PHRASE, WHISPER_EXPECT = "This is a test of speech recognition.", "test"


def _whisper_ready() -> bool:
    from core import model_assets
    return bool(model_assets.whisper_ready(_cfg("voice.stt_model", "base.en")))


def _synthetic_clip():
    """WHISPER_PHRASE spoken by Kokoro, resampled to Whisper's 16 kHz; None without Kokoro."""
    if not _kokoro_available():
        return None
    from core import voice_check
    from core.selftest import _resample
    audio, _secs = voice_check.synthesize_kokoro(WHISPER_PHRASE, "af_heart")
    return _resample(audio, voice_check.KOKORO_RATE, voice_check.WHISPER_RATE)


def whisper(full: bool = False, ready: Optional[Callable[[], bool]] = None, clip: Optional[Callable] = None,
            transcribe: Optional[Callable[..., Dict]] = None) -> Dict:
    """faster-whisper: model downloaded; with ``full`` it transcribes a short synthetic clip (Kokoro speaks a
    known sentence). No Kokoro → Not tested (the microphone test is on the Voice page)."""
    try:
        have = (ready or _whisper_ready)()
    except Exception as e:
        return _result(FAILED, f"can't check the Whisper model: {type(e).__name__}: {e}"[:300])
    if not have:
        return _result(MISSING, f"faster-whisper {_cfg('voice.stt_model', 'base.en')} isn't downloaded")
    if not full:
        return _result(NOT_TESTED, "model downloaded; transcription not tested yet")
    try:
        audio = (clip or _synthetic_clip)()
    except Exception as e:
        return _result(NOT_TESTED, f"couldn't make a test clip ({type(e).__name__}: {e})"[:300])
    if audio is None:
        return _result(NOT_TESTED, "no test clip (Kokoro missing) — use Test Whisper on the Voice page")
    if transcribe is None:
        from core.voice_check import test_whisper as transcribe
    r = transcribe(audio=audio, expect=WHISPER_EXPECT)
    return _result(WORKING if r.get("ok") else FAILED, r.get("detail", "")[:300])


# --------------------------------------------------------------------------- packages
def flatpak(run: Callable = _run, which: Callable = shutil.which, linux: Optional[bool] = None) -> Dict:
    """Flatpak installed and the Flathub remote configured (user or system)."""
    if not (_linux if linux is None else linux):
        return _result(NOT_TESTED, "Flatpak is Linux-only")
    if not which("flatpak"):
        return _result(MISSING, "Flatpak isn't installed")
    try:
        p = run(["flatpak", "remotes", "--columns=name,options"], timeout=10)
    except Exception as e:
        return _result(FAILED, f"`flatpak remotes` didn't run: {type(e).__name__}")
    if p.returncode != 0:
        return _result(FAILED, f"`flatpak remotes` failed: {(p.stderr or p.stdout or '').strip()[:200]}")
    rows = [l.split() for l in (p.stdout or "").splitlines() if l.strip()]
    hub = [r for r in rows if r and r[0] == "flathub"]
    if not hub:
        return _result(DEGRADED, "Flathub isn't configured — Store apps from Flathub can't install")
    where = sorted({("user" if "user" in r[1:] else "system") for r in hub})
    disabled = all("disabled" in ",".join(r[1:]) for r in hub)
    if disabled:
        return _result(DEGRADED, "the Flathub remote is disabled")
    return _result(WORKING, f"Flathub configured ({' and '.join(where)})")


def _process_running(name: str) -> bool:
    try:
        import psutil
        return any((p.info.get("name") or "") == name for p in psutil.process_iter(["name"]))
    except Exception:
        return False


def pacman(which: Callable = shutil.which, exists: Callable = os.path.exists, run: Callable = _run,
           running: Callable[[str], bool] = _process_running, linux: Optional[bool] = None) -> Dict:
    """pacman usable: no lock held (or a stale one left behind), keyring initialised, archlinux-keyring
    installed."""
    if not (_linux if linux is None else linux):
        return _result(NOT_TESTED, "pacman is Linux-only")
    if not which("pacman"):
        return _result(MISSING, "pacman isn't on this system")
    if exists("/var/lib/pacman/db.lck"):
        if running("pacman") or running("paru"):
            return _result(DEGRADED, "busy: another install or update is running")
        return _result(FAILED, "stale lock /var/lib/pacman/db.lck (no pacman is running) — installs will fail")
    if not any(exists(f"/etc/pacman.d/gnupg/{f}") for f in ("pubring.gpg", "pubring.kbx")):
        return _result(FAILED, "the pacman keyring isn't initialised (pacman-key --init; --populate archlinux)")
    try:
        p = run(["pacman", "-Q", "archlinux-keyring"], timeout=10)
    except Exception as e:
        return _result(FAILED, f"`pacman -Q` didn't run: {type(e).__name__}")
    if p.returncode != 0:
        return _result(DEGRADED, "archlinux-keyring isn't installed — package signatures may not verify")
    return _result(WORKING, f"database unlocked, keyring ready ({(p.stdout or '').strip()})")


# --------------------------------------------------------------------------- network
def _connect(host: str, port: int, timeout: float) -> None:
    socket.create_connection((host, port), timeout=timeout).close()


def network(resolve: Callable[[str], object] = socket.gethostbyname,
            connect: Callable[[str, int, float], None] = _connect, host: str = "archlinux.org",
            fallback_ip: str = "1.1.1.1", timeout: float = 4) -> Dict:
    """Name resolution and a real TCP connection (port 443)."""
    try:
        addr = resolve(host)
        connect(str(addr), 443, timeout)
        return _result(WORKING, f"online — {host} resolves and answers")
    except Exception as e:
        first = f"{type(e).__name__}"
    try:
        connect(fallback_ip, 443, timeout)
        return _result(DEGRADED, f"online, but {host} doesn't resolve or answer ({first}) — check DNS")
    except Exception as e:
        return _result(FAILED, f"no internet connection ({type(e).__name__})")


# --------------------------------------------------------------------------- GPU
_DISPLAY = ("VGA compatible controller", "3D controller", "Display controller")


def gpu(gpus: Optional[Callable[[], List[Dict]]] = None, run: Callable = _run,
        which: Callable = shutil.which, linux: Optional[bool] = None) -> Dict:
    """GPUs found (nvidia-smi, /sys/class/drm, lspci) and whether their driver is loaded. An NVIDIA card
    on nouveau or with no driver is reported: Halo ships nvidia-open for it."""
    linux = _linux if linux is None else linux
    if gpus is None:
        from core import sysinfo
        gpus = sysinfo.gpus
    try:
        devs = gpus() or []
    except Exception as e:
        devs, err = [], f"{type(e).__name__}"
    else:
        err = ""
    pci = []
    if linux and which("lspci"):
        try:
            out = run(["lspci"], timeout=8).stdout or ""
            pci = [l.split(": ", 1)[1] for l in out.splitlines() if ": " in l and any(k in l for k in _DISPLAY)]
        except Exception:
            pci = []
    nvidia_ok = [d for d in devs if d.get("vendor") == "NVIDIA" and str(d.get("driver", "")).startswith("nvidia")]
    if any("NVIDIA" in l for l in pci) and not nvidia_ok:
        nv = next((d for d in devs if d.get("vendor") == "NVIDIA"), None)
        if nv and nv.get("driver") == "nouveau":
            return _result(DEGRADED, f"{nv.get('name')} runs on nouveau — the NVIDIA driver (nvidia-open) isn't "
                                     "loaded, so AI runs on the CPU")
        return _result(FAILED, "NVIDIA GPU found but its driver isn't loaded (nvidia-smi doesn't answer)")
    if nvidia_ok:
        d = nvidia_ok[0]
        return _result(WORKING, f"{d.get('name')} ({d.get('driver')})", devices=devs)
    if devs:
        unbound = [d for d in devs if not d.get("driver")]
        if unbound:
            return _result(FAILED, f"{unbound[0].get('name')} has no driver loaded", devices=devs)
        d = devs[0]
        tone = WORKING if d.get("vendor") in ("AMD", "NVIDIA") else DEGRADED
        note = "" if tone == WORKING else " — integrated graphics; AI runs on the CPU"
        return _result(tone, f"{d.get('name')} ({d.get('driver')}){note}", devices=devs)
    if pci:
        return _result(DEGRADED, f"{pci[0][:80]} — no GPU acceleration; AI runs on the CPU")
    if not linux:
        return _result(NOT_TESTED, "no NVIDIA GPU answered (other GPUs are only checked on Linux)"
                                   + (f"; {err}" if err else ""))
    return _result(MISSING, "no GPU found")


# --------------------------------------------------------------------------- is each AI engine really on the GPU?
_WHISPER_PROBE = """
import json, sys
import numpy as np
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1], device="cuda", compute_type=sys.argv[2])
segments, _ = m.transcribe(np.zeros(16000, dtype="float32"), beam_size=1, vad_filter=False)
list(segments)
print(json.dumps({"device": m.model.device}))
"""
_KOKORO_PROBE = """
import json, sys
import onnxruntime as ort
s = ort.InferenceSession(sys.argv[1], providers=[*[p for p in ort.get_available_providers() if p == "CUDAExecutionProvider"],
                                                 "CPUExecutionProvider"])
print(json.dumps({"providers": s.get_providers()}))
"""


def _probe(script: str, args: List[str], run: Callable, timeout: float) -> Dict:
    """Run a probe in its own process: a CUDA library that's missing or wrong can abort the process that loads it."""
    try:
        p = run([sys.executable, "-c", script, *args], timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"no answer in {timeout:.0f} s"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    lines = (p.stdout or "").strip().splitlines()
    if p.returncode == 0 and lines:
        try:
            return json.loads(lines[-1])
        except ValueError:
            pass
    err = (p.stderr or p.stdout or "").strip().splitlines()
    return {"error": (err[-1] if err else f"exit code {p.returncode}")[:240]}


def gpu_ollama(base_url: str, model: str, post: Optional[Callable] = None, get: Optional[Callable] = None) -> Dict:
    """Load the model with one token, then read how much of it Ollama put in video memory (/api/ps)."""
    post, get = post or _post, get or _get
    base = (base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        post(base + "/api/generate", {"model": model, "prompt": "ok", "stream": False, "options": {"num_predict": 1}}, 120)
        loaded = (get(base + "/api/ps") or {}).get("models", [])
    except Exception as e:
        return {"on_gpu": False, "detail": f"Ollama didn't load {model}: {type(e).__name__}"}
    entry = next((m for m in loaded if m.get("name") == model or m.get("model") == model), None)
    if entry is None:
        return {"on_gpu": False, "detail": f"{model} isn't loaded after a request"}
    size, vram = int(entry.get("size") or 0), int(entry.get("size_vram") or 0)
    if vram <= 0:
        return {"on_gpu": False, "detail": f"{model} is 100% on the CPU (is ollama-cuda installed? `pacman -Q ollama-cuda`)"}
    pct = round(100 * vram / size) if size else 100
    return {"on_gpu": True, "detail": f"{model} {pct}% in video memory ({vram / 1e9:.1f} GB)"}


def gpu_whisper(model_source: str, compute: str, run: Callable = _run, timeout: float = 120) -> Dict:
    """Load the configured model on CUDA and encode a second of silence: this is where a missing libcublas fails."""
    res = _probe(_WHISPER_PROBE, [model_source, compute], run, timeout)
    if res.get("device") == "cuda":
        return {"on_gpu": True, "detail": f"transcribed on CUDA ({compute})"}
    return {"on_gpu": False, "detail": f"CUDA failed, SAINT uses the CPU: {res.get('error', res)}"}


def gpu_kokoro(model_path: str, run: Callable = _run, timeout: float = 90) -> Dict:
    """Which provider onnxruntime really gave a Kokoro session. CPU is this build's design (core/device_profile.py)."""
    res = _probe(_KOKORO_PROBE, [model_path], run, timeout)
    if res.get("error"):
        return {"on_gpu": False, "expected_cpu": True, "detail": f"can't open the model: {res['error']}"}
    on_gpu = (res.get("providers") or [""])[0] == "CUDAExecutionProvider"
    return {"on_gpu": on_gpu, "expected_cpu": True, "detail": "on CUDA" if on_gpu else "on the CPU by design"}


def _has_nvidia(run: Callable = _run) -> str:
    """The name of the NVIDIA GPU nvidia-smi answers for; "" when none does."""
    try:
        p = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=8)
    except Exception:
        return ""
    return (p.stdout or "").strip().splitlines()[0] if p.returncode == 0 and (p.stdout or "").strip() else ""


def ai_gpu(full: bool = False, nvidia: Optional[Callable[[], str]] = None, ollama_probe: Optional[Callable] = None,
           whisper_probe: Optional[Callable] = None, kokoro_probe: Optional[Callable] = None) -> Dict:
    """Whether Ollama, Whisper and Kokoro really run on the GPU, each proven by making it work (only with ``full``),
    never from the config. PCs with no NVIDIA GPU have nothing to check. A setting the user put on the CPU is theirs."""
    name = (nvidia or _has_nvidia)()
    if not name:
        return _result(NOT_TESTED, "no NVIDIA GPU answers; AI runs on the CPU", engines={})
    if not full:
        return _result(NOT_TESTED, f"{name}: GPU use not tested yet (Run full check)", engines={})
    engines, problems = {}, []
    if (_cfg("ai.provider", "ollama") or "ollama") == "ollama":
        res = (ollama_probe or (lambda: gpu_ollama(_cfg("ai.base_url", ""), _cfg("ai.model", ""))))()
        engines["Ollama"] = res
        if not res["on_gpu"]:
            problems.append("Ollama")
    if _cfg("voice.stt_device", "cuda") == "cuda":
        if whisper_probe is None:
            from core import model_assets
            source = model_assets.whisper_source(_cfg("voice.stt_model", "base.en"))
            compute = _cfg("voice.stt_compute_type", "float16")
            whisper_probe = lambda: gpu_whisper(source, compute)
        res = whisper_probe()
        engines["Whisper"] = res
        if not res["on_gpu"]:
            problems.append("Whisper")
    else:
        engines["Whisper"] = {"on_gpu": False, "detail": "set to the CPU in Voice settings"}
    if kokoro_probe is None:
        from modules.voice import kokoro_onnx
        kokoro_probe = lambda: gpu_kokoro(str(kokoro_onnx.model_dir() / kokoro_onnx.MODEL_FILE))
    engines["Kokoro"] = kokoro_probe()
    detail = "; ".join(f"{k}: {v['detail']}" for k, v in engines.items())
    if problems:
        return _result(DEGRADED, f"{name}: {' and '.join(problems)} not on the GPU. {detail}", engines=engines)
    return _result(WORKING, f"{name}. {detail}", engines=engines)


# --------------------------------------------------------------------------- storage
def storage(disk_usage: Callable = shutil.disk_usage, paths: Optional[List[str]] = None) -> Dict:
    """Free space where SAINT and apps write: / and the home folder (each filesystem once)."""
    paths = paths or ([os.path.abspath(os.sep), os.path.expanduser("~")])
    seen, worst, lines = set(), WORKING, []
    order = {WORKING: 0, DEGRADED: 1, FAILED: 2}
    for p in paths:
        try:
            u = disk_usage(p)
        except OSError as e:
            return _result(FAILED, f"can't read free space on {p}: {e}")
        key = (u.total, u.free)
        if key in seen:
            continue
        seen.add(key)
        free_gb, pct = u.free / 1e9, 100.0 * u.free / u.total if u.total else 0.0
        state = FAILED if free_gb < 1 else DEGRADED if free_gb < 10 or pct < 5 else WORKING
        worst = max(worst, state, key=order.get)
        lines.append(f"{free_gb:.1f} GB free of {u.total / 1e9:.0f} GB on {p}")
    detail = "; ".join(lines)
    if worst == DEGRADED:
        detail += " — low (the AI model alone needs ~5 GB)"
    elif worst == FAILED:
        detail += " — almost full: installs and downloads will fail"
    return _result(worst, detail)


# --------------------------------------------------------------------------- registry
_last_full: Dict[str, Dict] = {}
_cache_lock = threading.Lock()


def check(key: str, full: bool = False) -> Dict:
    """Run one subsystem's check (no timeout here; run_all applies them)."""
    if key == "ollama":
        return ollama_check(full=full)
    if key == "kokoro":
        return kokoro(full=full)
    if key == "whisper":
        return whisper(full=full)
    if key == "ai_gpu":
        return ai_gpu(full=full)
    fn = {"flatpak": flatpak, "pacman": pacman, "network": network, "gpu": gpu, "storage": storage}.get(key)
    if fn is None:
        raise KeyError(key)
    return fn()


def _label(key: str) -> str:
    return next((l for k, l, _ in SUBSYSTEMS if k == key), key)


def _heavy(key: str) -> bool:
    return next((h for k, _, h in SUBSYSTEMS if k == key), False)


def latest(key: str) -> Optional[Dict]:
    """The last full-check result of a heavy subsystem."""
    with _cache_lock:
        return dict(_last_full[key]) if key in _last_full else None


def run_all(full: bool = False, keys: Optional[List[str]] = None,
            checks: Optional[Dict[str, Callable[[bool], Dict]]] = None,
            timeouts: Optional[Dict[str, float]] = None) -> List[Dict]:
    """Every subsystem's result, in SUBSYSTEMS order, checked in parallel. A check that doesn't answer in
    time is Failed ("no answer within N s"); one that raises is Failed with the exception. Light runs show
    the last full result of a heavy check when the light check has nothing worse to say."""
    keys = keys or [k for k, _, _ in SUBSYSTEMS]
    run_one = (lambda k, f: checks[k](f)) if checks else check
    pool = _cf.ThreadPoolExecutor(max_workers=max(1, len(keys)), thread_name_prefix="health")
    futures = {k: pool.submit(run_one, k, full) for k in keys}
    deadline = time.monotonic()
    out = []
    for k in keys:
        limit = (timeouts or {}).get(k) or TIMEOUTS.get(k, (DEFAULT_TIMEOUT, DEFAULT_TIMEOUT))[1 if full else 0]
        remaining = max(0.05, deadline + limit - time.monotonic())
        try:
            r = futures[k].result(timeout=remaining)
        except _cf.TimeoutError:
            r = _result(FAILED, f"no answer within {limit:.0f} s")
        except Exception as e:
            r = _result(FAILED, f"check crashed: {type(e).__name__}: {e}"[:300])
        if r.get("state") not in STATES:
            r = _result(FAILED, f"check returned an unknown state {r.get('state')!r}")
        heavy = _heavy(k)
        with _cache_lock:
            if full and heavy:
                _last_full[k] = dict(r)
            elif heavy and k in _last_full and r["state"] in (WORKING, NOT_TESTED):
                cached = _last_full[k]
                r = {**cached, "detail": f"{cached['detail']} (tested {cached['at']})"}
        out.append({**r, "key": k, "label": _label(k), "heavy": heavy})
    pool.shutdown(wait=False, cancel_futures=True)
    return out


def summary(results: List[Dict]) -> str:
    """'6 working · 1 degraded · 1 not tested'."""
    counts = {s: sum(1 for r in results if r.get("state") == s) for s in STATES}
    return " · ".join(f"{n} {s}" for s, n in counts.items() if n) or "no checks"


def _get(url: str, timeout: float = 2.0):
    import requests
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _post(url: str, body: dict, timeout: float):
    import requests
    r = requests.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


def main() -> int:
    """`python -m core.health [--full]`: print every subsystem's state (for diagnostics and the VM tests)."""
    full = "--full" in sys.argv[1:]
    results = run_all(full=full)
    for r in results:
        print(f"{r['label']:<20} {LABELS[r['state']]:<11} {r['detail']}")
    print(summary(results))
    return 1 if any(r["state"] == FAILED for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
