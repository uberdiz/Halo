"""
core/device_profile.py

What this PC can run: reads the hardware once (nvidia-smi, RAM, CPU, free disk) and maps it, deterministically,
to the Ollama model, the Whisper model and compute type, and the voice. No model is asked and nothing is
downloaded here: core/provision.py does the downloading on first boot, and SAINT copies the choices into the
user's config only for settings the user hasn't changed (apply_to_config).

Tiers (VRAM and RAM in GiB, rounded the way the box says: 8188 MiB is an "8 GB" card):

    tier     needs                Ollama model (download)     Whisper          compute        device
    gpu-24   NVIDIA, 24+ VRAM     qwen2.5:32b  (20 GB)        large-v3-turbo   float16        cuda
    gpu-16   NVIDIA, 16+ VRAM     qwen2.5:14b  (9 GB)         large-v3-turbo   float16        cuda
    gpu-12   NVIDIA, 12+ VRAM     llama3.1:8b  (4.9 GB)       medium.en        float16        cuda
    gpu-8    NVIDIA, 8+ VRAM      llama3.1:8b  (4.9 GB)       small.en         float16        cuda
    gpu-4    NVIDIA, 4+ VRAM      llama3.2:3b  (2 GB)         base.en          int8_float16   cuda
    cpu-8b   12+ RAM              llama3.1:8b  (4.9 GB)       base.en          int8           cpu
    cpu-3b   8+ RAM               llama3.2:3b  (2 GB)         base.en          int8           cpu
    cpu-1b   less                 llama3.2:1b  (1.3 GB)       tiny.en          int8           cpu

An NVIDIA card with under 4 GB, or one nvidia-smi can't reach (nouveau, no driver), counts as no GPU. Fewer than 4
CPU threads without a GPU means tiny.en. Disk comes last: 8 GB stay free for the user, the GPU libraries need 12 GB
(else the CPU tier is used and the reason says so), and the Ollama and Whisper models step down until they fit.

The voice is Kokoro on onnxruntime's CPU build on every tier: it's many times faster than real time on any CPU this
targets, and onnxruntime-gpu 1.31 needs CUDA 13's libcudnn.so.9 while ctranslate2 (Whisper) needs CUDA 12's, one
soname in one process. Whisper is the engine that benefits from the GPU, so it gets it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Download sizes in GB (ollama.com/library, huggingface.co), used only to decide what fits.
OLLAMA_GB = {"qwen2.5:32b": 20.0, "qwen2.5:14b": 9.0, "llama3.1:8b": 4.9, "llama3.2:3b": 2.0, "llama3.2:1b": 1.3}
OLLAMA_LADDER = ["qwen2.5:32b", "qwen2.5:14b", "llama3.1:8b", "llama3.2:3b", "llama3.2:1b"]
WHISPER_GB = {"large-v3-turbo": 1.6, "medium.en": 1.5, "small.en": 0.5, "base.en": 0.15, "tiny.en": 0.08}
WHISPER_LADDER = ["large-v3-turbo", "medium.en", "small.en", "base.en", "tiny.en"]
# Hugging Face repositories of those models (faster_whisper.utils._MODELS).
WHISPER_REPOS = {"large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo"}
for _name in ("medium.en", "small.en", "base.en", "tiny.en"):
    WHISPER_REPOS[_name] = f"Systran/faster-whisper-{_name}"

RESERVE_GB = 8.0            # stays free for the user
GPU_STACK_GB = 12.0         # ollama-cuda + cuda 6.1 GB, Whisper's CUDA 12 libraries 3 GB, pacman's package cache 3 GB
MIN_VRAM_GB = 4

# (minimum VRAM, tier, Ollama model, Whisper model, compute type), largest first
GPU_TIERS = [(24, "gpu-24", "qwen2.5:32b", "large-v3-turbo", "float16"),
             (16, "gpu-16", "qwen2.5:14b", "large-v3-turbo", "float16"),
             (12, "gpu-12", "llama3.1:8b", "medium.en", "float16"),
             (8, "gpu-8", "llama3.1:8b", "small.en", "float16"),
             (MIN_VRAM_GB, "gpu-4", "llama3.2:3b", "base.en", "int8_float16")]
# The same 12 GB line as core.config.choose_ollama_model and the ollama-model script.
CPU_TIERS = [(12, "cpu-8b", "llama3.1:8b", "base.en"), (8, "cpu-3b", "llama3.2:3b", "base.en"),
             (0, "cpu-1b", "llama3.2:1b", "tiny.en")]


@dataclass(frozen=True)
class Hardware:
    gpu_name: str = ""          # empty: no NVIDIA GPU answers nvidia-smi
    vram_gb: float = 0.0
    ram_gb: float = 0.0
    cpu_name: str = ""
    cpu_threads: int = 0
    disk_free_gb: float = 0.0
    gpu_note: str = ""          # why a card that's there can't be used


@dataclass
class Profile:
    tier: str
    ollama_model: str           # "" when not even the smallest fits
    whisper_model: str
    whisper_device: str
    whisper_compute: str
    use_gpu: bool
    tts_provider: str = "kokoro"
    tts_device: str = "cpu"
    reason: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


def _fit(ladder: List[str], sizes: Dict[str, float], want: str, room: float) -> str:
    """``want``, or the next smaller item of ``ladder`` that fits in ``room`` GB; "" when none does."""
    return next((m for m in ladder[ladder.index(want):] if sizes[m] <= room), "")


def choose(hw: Hardware) -> Profile:
    """The profile for this hardware. Pure: same input, same answer."""
    vram, ram = round(hw.vram_gb), round(hw.ram_gb)
    room = hw.disk_free_gb - RESERVE_GB
    notes = [hw.gpu_note] if hw.gpu_note else []
    gpu = next((t for t in GPU_TIERS if vram >= t[0]), None) if hw.gpu_name else None
    if hw.gpu_name and gpu is None:
        notes.append(f"{hw.gpu_name} has {vram} GB of memory; AI needs at least {MIN_VRAM_GB} GB, so it runs on the CPU.")
    if gpu and room - GPU_STACK_GB < OLLAMA_GB[OLLAMA_LADDER[-1]] + WHISPER_GB[WHISPER_LADDER[-1]]:
        notes.append(f"Only {hw.disk_free_gb:.0f} GB free: not enough for the GPU libraries ({GPU_STACK_GB:.0f} GB), "
                     "so AI runs on the CPU.")
        gpu = None
    if gpu:
        tier, model, whisper, compute = gpu[1:]
        device, room = "cuda", room - GPU_STACK_GB
        reason = f"{hw.gpu_name} with {vram} GB of memory"
    else:
        tier, model, whisper = next(t[1:] for t in CPU_TIERS if ram >= t[0])
        device, compute = "cpu", "int8"
        if hw.cpu_threads and hw.cpu_threads < 4:
            whisper = "tiny.en"
        reason = f"{ram} GB of RAM, no usable GPU"
    whisper_pick = _fit(WHISPER_LADDER, WHISPER_GB, whisper, room)
    model_pick = _fit(OLLAMA_LADDER, OLLAMA_GB, model, room - WHISPER_GB.get(whisper_pick, 0.0))
    if whisper_pick != whisper or model_pick != model:
        notes.append(f"Smaller models chosen: {hw.disk_free_gb:.0f} GB free, {RESERVE_GB:.0f} GB stay yours."
                     if model_pick else f"Only {hw.disk_free_gb:.0f} GB free: no language model is downloaded.")
    return Profile(tier=tier, ollama_model=model_pick, whisper_model=whisper_pick or WHISPER_LADDER[-1],
                   whisper_device=device, whisper_compute=compute, use_gpu=bool(gpu), reason=reason, notes=notes)


def cpu_fallback(profile: Profile, why: str, hw: Hardware) -> Profile:
    """The GPU libraries didn't install: the tier's models would be too slow, so use the CPU tier with the reason."""
    cpu = choose(Hardware(ram_gb=hw.ram_gb, cpu_threads=hw.cpu_threads, disk_free_gb=hw.disk_free_gb))
    cpu.notes = [*profile.notes, why]
    return cpu


# ---------------- reading the hardware ----------------

def _run(argv: List[str], timeout: float = 10) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def parse_nvidia_smi(out: str) -> Dict:
    """The card with the most memory from `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits`."""
    best = {"name": "", "vram_gb": 0.0}
    for line in (out or "").splitlines():
        name, _, mib = line.rpartition(",")
        try:
            gb = float(mib) / 1024
        except ValueError:
            continue
        if name.strip() and gb > best["vram_gb"]:
            best = {"name": name.strip(), "vram_gb": gb}
    return best


def _ram_gb(read: Callable[[str], str]) -> float:
    try:
        for line in read("/proc/meminfo").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 1048576
    except (OSError, ValueError, IndexError):
        pass
    try:
        import psutil
        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        return 0.0


def _cpu_name(read: Callable[[str], str]) -> str:
    try:
        for line in read("/proc/cpuinfo").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except (OSError, IndexError):
        pass
    return ""


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def detect(run: Callable = _run, read: Callable[[str], str] = _read, disk_usage: Callable = shutil.disk_usage,
           cpu_count: Callable[[], Optional[int]] = os.cpu_count, disk_path: str = "") -> Hardware:
    """The hardware as it answers now. Anything unreadable counts as absent, never as an error."""
    gpu = {"name": "", "vram_gb": 0.0}
    note = ""
    try:
        res = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if res.returncode == 0:
            gpu = parse_nvidia_smi(res.stdout)
    except (OSError, subprocess.SubprocessError):
        pass
    if not gpu["name"]:
        try:                                     # /usr/lib/halo/gpu-detect's choice at this boot
            if read("/run/halo/gpu").strip() == "nouveau":
                note = "This NVIDIA GPU runs on nouveau (older than nvidia-open supports), so AI runs on the CPU."
        except OSError:
            pass
    try:
        free = disk_usage(disk_path or ("/var/lib" if os.path.isdir("/var/lib") else os.path.abspath(os.sep))).free
    except OSError:
        free = 0
    return Hardware(gpu_name=gpu["name"], vram_gb=gpu["vram_gb"], ram_gb=_ram_gb(read), cpu_name=_cpu_name(read),
                    cpu_threads=int(cpu_count() or 0), disk_free_gb=free / 1e9, gpu_note=note)


# ---------------- SAINT's config ----------------

# config key -> profile field. ai.provider isn't here: Ollama stays the default and the choice stays the user's.
CONFIG_KEYS = {"ai.model": "ollama_model", "voice.stt_model": "whisper_model", "voice.stt_device": "whisper_device",
               "voice.stt_compute_type": "whisper_compute", "voice.tts_backend": "tts_provider",
               "voice.tts_device": "tts_device"}
APPLIED_KEY = "device_profile.applied"


def apply_to_config(profile: Dict, get: Callable, set_: Callable, default: Callable[[str], object]) -> List[str]:
    """Write the profile's choices, except where the user has made their own: a setting is theirs when it's
    neither the shipped default nor what the last profile wrote. Returns the keys changed."""
    applied = dict(get(APPLIED_KEY, {}) or {})
    changed = []
    for key, attr in CONFIG_KEYS.items():
        value = profile.get(attr)
        if not value:
            continue
        current = get(key, None)
        if current != default(key) and current != applied.get(key):
            continue                              # the user chose this one
        applied[key] = value
        if current != value:
            set_(key, value, persist=False)
            changed.append(key)
    set_(APPLIED_KEY, applied, persist=True)
    return changed


def main() -> int:
    """`python -m core.device_profile`: what this PC is detected as and what it would get."""
    hw = detect()
    json.dump({"hardware": asdict(hw), "profile": choose(hw).to_dict()}, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
