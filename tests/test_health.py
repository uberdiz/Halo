"""core/health.py (one health model per subsystem), core/model_pull.py and the default Ollama model rule.
Linux-only checks run here with mocked commands and files."""

import json
import re
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import health

ROOT = Path(__file__).resolve().parent.parent


def proc(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


# --------------------------------------------------------------------------- Ollama
def test_ollama_check_light_does_not_call_the_model():
    tags = {"models": [{"name": "llama3.1:8b"}]}
    post = lambda *a: pytest.fail("light check must not run inference")
    r = health.ollama_check(full=False, base_url="http://x", model="llama3.1:8b", get=lambda u: tags, post=post)
    assert r["state"] == health.WORKING


def test_ollama_check_full_runs_a_real_prompt_against_the_installed_tag():
    seen = {}

    def post(url, body, timeout):
        seen.update(url=url, model=body["model"])
        return {"response": "ready"}
    tags = {"models": [{"name": "llama3.1:latest"}]}
    r = health.ollama_check(full=True, base_url="http://x", model="llama3.1", get=lambda u: tags, post=post)
    assert r["state"] == health.WORKING and seen == {"url": "http://x/api/generate", "model": "llama3.1:latest"}


def test_ollama_check_full_skips_inference_when_model_missing():
    r = health.ollama_check(full=True, base_url="http://x", model="llama3.1:8b",
                            get=lambda u: {"models": [{"name": "llama3.2:3b"}]},
                            post=lambda *a: pytest.fail("no inference without the model"))
    assert r["state"] == health.DEGRADED and "llama3.1:8b" in r["detail"]


def test_ollama_reports_the_download_while_pulling(monkeypatch):
    from core import model_pull
    monkeypatch.setitem(model_pull._state, "model", "llama3.1:8b")
    monkeypatch.setitem(model_pull._state, "running", True)
    monkeypatch.setitem(model_pull._state, "percent", 43.0)
    monkeypatch.setitem(model_pull._state, "completed", int(2.1e9))
    monkeypatch.setitem(model_pull._state, "total", int(4.9e9))
    r = health.ollama("http://x", "llama3.1:8b", get=lambda u: {"models": []})
    assert r["state"] == health.DEGRADED and r["detail"] == "Downloading llama3.1:8b — 43% (2.1 of 4.9 GB)"


# --------------------------------------------------------------------------- voice
def test_kokoro_missing_light_and_full():
    assert health.kokoro(available=lambda: False)["state"] == health.MISSING
    assert health.kokoro(full=False, available=lambda: True, service=None)["state"] in (health.NOT_TESTED,
                                                                                        health.WORKING)
    ok = health.kokoro(full=True, available=lambda: True, service=SimpleNamespace(_engine_type="kokoro"),
                       test=lambda **k: {"ok": True, "detail": "2.1s of speech"})
    assert ok["state"] == health.WORKING and "2.1s" in ok["detail"]
    bad = health.kokoro(full=True, available=lambda: True, test=lambda **k: {"ok": False, "detail": "boom"})
    assert bad["state"] == health.FAILED and "boom" in bad["detail"]


def test_kokoro_full_never_plays_or_downloads():
    seen = {}
    health.kokoro(full=True, available=lambda: True, test=lambda **k: seen.update(k) or {"ok": True, "detail": ""})
    assert seen == {"play": False, "download": False}


def test_kokoro_works_but_saint_speaks_with_espeak_is_degraded():
    r = health.kokoro(full=True, available=lambda: True, service=SimpleNamespace(_engine_type="espeak"),
                      test=lambda **k: {"ok": True, "detail": "fine"})
    assert r["state"] == health.DEGRADED and "espeak-ng" in r["detail"]


def test_whisper_states():
    assert health.whisper(ready=lambda: False)["state"] == health.MISSING
    assert health.whisper(full=False, ready=lambda: True)["state"] == health.NOT_TESTED
    # No synthetic clip (Kokoro missing) -> Not tested, never a fake pass
    assert health.whisper(full=True, ready=lambda: True, clip=lambda: None)["state"] == health.NOT_TESTED
    got = {}

    def transcribe(audio, expect):
        got.update(n=len(audio), expect=expect)
        return {"ok": True, "detail": "heard 'This is a test.'"}
    r = health.whisper(full=True, ready=lambda: True, clip=lambda: [0.0] * 16000, transcribe=transcribe)
    assert r["state"] == health.WORKING and got == {"n": 16000, "expect": "test"}
    r = health.whisper(full=True, ready=lambda: True, clip=lambda: [0.0],
                       transcribe=lambda **k: {"ok": False, "detail": "heard ''"})
    assert r["state"] == health.FAILED


# --------------------------------------------------------------------------- flatpak / pacman
def test_flatpak():
    which = lambda n: "/usr/bin/" + n
    assert health.flatpak(linux=False)["state"] == health.NOT_TESTED
    assert health.flatpak(which=lambda n: None, linux=True)["state"] == health.MISSING
    r = health.flatpak(run=lambda a, timeout: proc(0, "flathub\tuser\n"), which=which, linux=True)
    assert r["state"] == health.WORKING and "user" in r["detail"]
    r = health.flatpak(run=lambda a, timeout: proc(0, "fedora\tsystem\n"), which=which, linux=True)
    assert r["state"] == health.DEGRADED and "Flathub" in r["detail"]
    r = health.flatpak(run=lambda a, timeout: proc(1, "", "error: oops"), which=which, linux=True)
    assert r["state"] == health.FAILED and "oops" in r["detail"]

    def slow(a, timeout):
        raise subprocess.TimeoutExpired(a, timeout)
    assert health.flatpak(run=slow, which=which, linux=True)["state"] == health.FAILED


def test_pacman_lock_keyring_and_ok():
    which = lambda n: "/usr/bin/" + n
    files = {"/etc/pacman.d/gnupg/pubring.gpg"}
    ok_run = lambda a, timeout: proc(0, "archlinux-keyring 20261001-1\n")
    kw = dict(which=which, run=ok_run, linux=True)
    assert health.pacman(linux=False)["state"] == health.NOT_TESTED
    assert health.pacman(which=lambda n: None, linux=True)["state"] == health.MISSING
    r = health.pacman(exists=files.__contains__, running=lambda n: False, **kw)
    assert r["state"] == health.WORKING and "archlinux-keyring" in r["detail"]
    locked = files | {"/var/lib/pacman/db.lck"}
    assert health.pacman(exists=locked.__contains__, running=lambda n: n == "pacman", **kw)["state"] == health.DEGRADED
    r = health.pacman(exists=locked.__contains__, running=lambda n: False, **kw)
    assert r["state"] == health.FAILED and "stale lock" in r["detail"]
    r = health.pacman(exists=set().__contains__, running=lambda n: False, **kw)
    assert r["state"] == health.FAILED and "keyring" in r["detail"]
    r = health.pacman(exists=files.__contains__, running=lambda n: False, which=which, linux=True,
                      run=lambda a, timeout: proc(1, "", "error: package not found"))
    assert r["state"] == health.DEGRADED


# --------------------------------------------------------------------------- network
def test_network():
    ok = lambda h, p, t: None

    def down(h, p, t):
        raise OSError("unreachable")

    def no_dns(h):
        raise OSError("name resolution")
    assert health.network(resolve=lambda h: "1.2.3.4", connect=ok)["state"] == health.WORKING
    assert health.network(resolve=no_dns, connect=ok)["state"] == health.DEGRADED
    assert health.network(resolve=lambda h: "1.2.3.4", connect=down)["state"] == health.FAILED


# --------------------------------------------------------------------------- GPU
def test_gpu_nvidia_driver_loaded():
    devs = [{"name": "NVIDIA GeForce RTX 5070", "vendor": "NVIDIA", "driver": "nvidia 580.1"}]
    r = health.gpu(gpus=lambda: devs, which=lambda n: None, linux=True)
    assert r["state"] == health.WORKING and "RTX 5070" in r["detail"]


def test_gpu_nvidia_without_driver_or_on_nouveau():
    lspci = "01:00.0 VGA compatible controller: NVIDIA Corporation GB205 [GeForce RTX 5070]\n"
    run = lambda a, timeout: proc(0, lspci)
    which = lambda n: "/usr/bin/lspci"
    r = health.gpu(gpus=lambda: [], run=run, which=which, linux=True)
    assert r["state"] == health.FAILED and "driver" in r["detail"]
    nouveau = [{"name": "NVIDIA GPU", "vendor": "NVIDIA", "driver": "nouveau"}]
    r = health.gpu(gpus=lambda: nouveau, run=run, which=which, linux=True)
    assert r["state"] == health.DEGRADED and "nouveau" in r["detail"]


def test_gpu_amd_intel_vm_and_none():
    amd = [{"name": "Radeon RX 7800", "vendor": "AMD", "driver": "amdgpu"}]
    assert health.gpu(gpus=lambda: amd, which=lambda n: None, linux=True)["state"] == health.WORKING
    intel = [{"name": "Intel UHD", "vendor": "Intel", "driver": "i915"}]
    assert health.gpu(gpus=lambda: intel, which=lambda n: None, linux=True)["state"] == health.DEGRADED
    unbound = [{"name": "Radeon", "vendor": "AMD", "driver": ""}]
    assert health.gpu(gpus=lambda: unbound, which=lambda n: None, linux=True)["state"] == health.FAILED
    vm = "00:02.0 VGA compatible controller: VMware SVGA II Adapter\n"
    r = health.gpu(gpus=lambda: [], run=lambda a, timeout: proc(0, vm), which=lambda n: "/x", linux=True)
    assert r["state"] == health.DEGRADED and "VMware" in r["detail"]
    assert health.gpu(gpus=lambda: [], which=lambda n: None, linux=True)["state"] == health.MISSING
    assert health.gpu(gpus=lambda: [], which=lambda n: None, linux=False)["state"] == health.NOT_TESTED


# --------------------------------------------------------------------------- storage
def test_storage_thresholds_and_dedup():
    usage = lambda free, total=500e9: SimpleNamespace(total=total, used=total - free, free=free)
    r = health.storage(disk_usage=lambda p: usage(200e9), paths=["/", "/home/u"])
    assert r["state"] == health.WORKING and r["detail"].count("GB free") == 1      # same filesystem once
    assert health.storage(disk_usage=lambda p: usage(6e9), paths=["/"])["state"] == health.DEGRADED
    assert health.storage(disk_usage=lambda p: usage(0.5e9), paths=["/"])["state"] == health.FAILED

    def broken(p):
        raise OSError("gone")
    assert health.storage(disk_usage=broken, paths=["/"])["state"] == health.FAILED


# --------------------------------------------------------------------------- run_all
def test_run_all_times_out_catches_errors_and_keeps_order():
    def slow(full):
        time.sleep(2)
        return health._result(health.WORKING, "late")

    def boom(full):
        raise RuntimeError("kaput")
    checks = {"network": slow, "gpu": boom, "storage": lambda f: health._result(health.WORKING, "ok")}
    t0 = time.monotonic()
    out = health.run_all(keys=["network", "gpu", "storage"], checks=checks, timeouts={"network": 0.3})
    assert time.monotonic() - t0 < 1.5
    assert [r["key"] for r in out] == ["network", "gpu", "storage"]
    assert out[0]["state"] == health.FAILED and "no answer within" in out[0]["detail"]
    assert out[1]["state"] == health.FAILED and "kaput" in out[1]["detail"]
    assert out[2]["state"] == health.WORKING and out[2]["label"] == "Storage"


def test_light_run_shows_last_full_result_of_heavy_checks(monkeypatch):
    monkeypatch.setattr(health, "_last_full", {})
    full = {"whisper": lambda f: health._result(health.WORKING if f else health.NOT_TESTED,
                                                "heard it" if f else "not tested yet")}
    health.run_all(full=True, keys=["whisper"], checks=full)
    light = health.run_all(full=False, keys=["whisper"], checks=full)[0]
    assert light["state"] == health.WORKING and light["detail"].startswith("heard it (tested ")
    # ...but a light check that finds it missing wins over the remembered pass
    gone = {"whisper": lambda f: health._result(health.MISSING, "deleted")}
    assert health.run_all(full=False, keys=["whisper"], checks=gone)[0]["state"] == health.MISSING


def test_every_subsystem_has_a_check_and_a_manifest():
    from core import deps
    keys = [k for k, _, _ in health.SUBSYSTEMS]
    assert keys == ["ollama", "kokoro", "whisper", "ai_gpu", "flatpak", "pacman", "network", "gpu", "storage"]
    assert set(keys) == set(deps.MANIFESTS)
    with pytest.raises(KeyError):
        health.check("nope")


def test_summary():
    rs = [{"state": health.WORKING}] * 2 + [{"state": health.FAILED}]
    assert health.summary(rs) == "2 working · 1 failed"


# --------------------------------------------------------------------------- default model
def test_default_model_rule():
    from core.config import OLLAMA_DEFAULT_MODEL, OLLAMA_SMALL_MODEL, choose_ollama_model
    assert OLLAMA_DEFAULT_MODEL == "llama3.1:8b" and OLLAMA_SMALL_MODEL == "llama3.2:3b"
    gib = 1024 ** 3
    assert choose_ollama_model(8 * gib, has_gpu=False) == OLLAMA_SMALL_MODEL
    assert choose_ollama_model(8 * gib, has_gpu=True) == OLLAMA_DEFAULT_MODEL
    assert choose_ollama_model(int(11.5 * gib), has_gpu=False) == OLLAMA_DEFAULT_MODEL   # a "12 GB" PC
    assert choose_ollama_model(32 * gib, has_gpu=False) == OLLAMA_DEFAULT_MODEL


def test_service_and_script_use_the_same_models_and_threshold():
    from core import config as cfg
    rootfs = ROOT / "packaging" / "linux" / "rootfs"
    unit = (rootfs / "usr/lib/systemd/system/saint-ollama-model.service").read_text(encoding="utf-8")
    conf = (rootfs / "etc/halo/ollama-model").read_text(encoding="utf-8")
    script = (rootfs / "usr/libexec/saintos/ollama-model").read_text(encoding="utf-8")
    assert "ExecStart=/usr/libexec/saintos/ollama-model auto" in unit
    assert f"HALO_OLLAMA_MODEL={cfg.OLLAMA_DEFAULT_MODEL}\n" in conf
    assert f"HALO_OLLAMA_SMALL_MODEL={cfg.OLLAMA_SMALL_MODEL}\n" in conf
    assert '-lt 12 ]' in script        # same 12 GB threshold as SMALL_MODEL_RAM_BYTES
    assert "llama3.2:3b" not in (ROOT / "core" / "evolve.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- model pull progress
class FakeResp:
    def __init__(self, lines, code=200):
        self.status_code, self.text, self._lines = code, "", [json.dumps(l).encode() for l in lines]

    def iter_lines(self):
        return iter(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_pull_model_stream_sums_layers(monkeypatch):
    from modules.ai.providers import OllamaProvider
    lines = [{"status": "pulling manifest"},
             {"status": "pulling a", "digest": "a", "total": 400, "completed": 100},
             {"status": "pulling b", "digest": "b", "total": 100, "completed": 0},
             {"status": "pulling a", "digest": "a", "total": 400, "completed": 400},
             {"status": "pulling b", "digest": "b", "total": 100, "completed": 100},
             {"status": "verifying sha256 digest"}, {"status": "success"}]
    p = OllamaProvider()
    monkeypatch.setattr(p, "_request", lambda *a, **k: FakeResp(lines))
    seen = []
    res = p.pull_model_stream("http://x", "m", seen.append)
    assert res["success"] is True
    assert [s["percent"] for s in seen if s["percent"] is not None][:3] == [25.0, 20.0, 80.0]
    assert seen[-1]["completed"] == seen[-1]["total"] == 500


def test_pull_model_stream_reports_ollama_error(monkeypatch):
    from modules.ai.providers import OllamaProvider
    p = OllamaProvider()
    monkeypatch.setattr(p, "_request", lambda *a, **k: FakeResp([{"error": "pull model manifest: file does not exist"}]))
    res = p.pull_model_stream("http://x", "nope:1b", lambda s: None)
    assert res["success"] is False and "does not exist" in res["error"]


def test_model_pull_state_and_notifications(monkeypatch):
    from core import model_pull
    monkeypatch.setattr(model_pull, "_state", dict(model_pull._state, running=False))
    said = []

    class Prov:
        def pull_model_stream(self, base, model, on_progress, cancel):
            on_progress({"status": "pulling", "completed": 50, "total": 100, "percent": 50.0})
            assert model_pull.state()["percent"] == 50.0 and model_pull.state()["running"]
            return {"success": True}
    assert model_pull.start("http://x", "llama3.1:8b", provider=Prov(), notify=lambda t, m: said.append(t),
                            wait=True)
    s = model_pull.state()
    assert s["done"] and not s["running"] and s["percent"] == 100.0
    assert said == ["Downloading SAINT's AI model", "SAINT's AI model is ready"]
    assert model_pull.describe(s) == "llama3.1:8b downloaded"

    class Bad:
        def pull_model_stream(self, *a):
            return {"success": False, "error": "no space left on device"}
    said.clear()
    model_pull.start("http://x", "llama3.1:8b", provider=Bad(), notify=lambda t, m: said.append(m), wait=True)
    assert model_pull.state()["error"] == "no space left on device" and "no space" in said[-1]


def test_model_pull_auto_start_only_on_halo_when_model_missing(monkeypatch):
    from core import model_pull, paths
    started = []
    monkeypatch.setattr(model_pull, "start", lambda b, m: started.append(m) or True)
    cfg = {"ai.provider": "ollama", "ai.model": "llama3.1:8b", "ai.base_url": "http://x"}.get
    missing = lambda b, m: health._result(health.DEGRADED, "not downloaded")
    monkeypatch.setattr(paths, "system_install", lambda: False)
    assert model_pull.auto_start(get_config=cfg, check=missing) is False
    monkeypatch.setattr(paths, "system_install", lambda: True)
    assert model_pull.auto_start(get_config=cfg, check=lambda b, m: health._result(health.WORKING, "")) is False
    assert model_pull.auto_start(get_config=cfg, check=lambda b, m: health._result(health.FAILED, "")) is False
    assert model_pull.auto_start(get_config=cfg, check=missing, live=lambda: True) is False   # RAM disk
    assert model_pull.auto_start(get_config=cfg, check=missing, live=lambda: False) is True
    assert started == ["llama3.1:8b"]
