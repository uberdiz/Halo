"""core/model_pull: refuse duplicate / too-big pulls, and verify a pulled model (listed, real inference, CUDA/CPU)."""
import os

import pytest

from core import device_profile as dp, model_pull as mp

BIG = dp.Hardware(gpu_name="RTX 5060 Ti", vram_gb=16, ram_gb=48, cpu_threads=16, disk_free_gb=500)
SMALL = dp.Hardware(ram_gb=8, cpu_threads=4, disk_free_gb=500)


class Prov:
    def __init__(self, names):
        self.names = names
        self.pulled = []

    def list_models(self, base_url, timeout=3, force_refresh=False):
        return [{"name": n} for n in self.names]

    def pull_model_stream(self, base_url, model, progress, cancel):
        self.pulled.append(model)
        self.names.append(model)
        return {"success": True}


def test_refuses_installed_and_too_big():
    assert "already installed" in mp.precheck("llama3.2:1b", {"llama3.2:1b"}, hw=BIG)
    msg = mp.precheck("qwen2.5:32b", set(), hw=SMALL)
    assert "too big" in msg and "Try Llama 3.2 3B (llama3.2:3b" in msg
    assert mp.precheck("qwen2.5:32b", set(), hw=BIG) == ""
    assert mp.precheck("some/custom:model", set(), hw=SMALL) == ""        # not in the catalog: allowed


def test_start_refuses_duplicate_and_verifies(monkeypatch):
    said = []
    p = Prov(["llama3.2:1b"])
    assert not mp.start("http://x", "llama3.2:1b", provider=p, hw=BIG) and "already installed" in mp.refusal()

    def http(base, path, body=None, timeout=5):
        return {"response": "OK"} if path == "/api/generate" else {
            "models": [{"name": "llama3.2:3b", "size_vram": 2_000_000_000}]}
    monkeypatch.setattr(mp, "_http", http)
    monkeypatch.setattr(mp.verify, "__defaults__", (None, http, []))
    assert mp.start("http://x", "llama3.2:3b", provider=p, hw=BIG, wait=True, notify=lambda t, m: said.append(m))
    s = mp.state()
    assert s["verify"]["device"] == "CUDA" and s["status"] == "verified"
    assert "running on CUDA" in mp.describe(s) and "running on CUDA" in said[-1]


def test_verify_cpu_and_failures():
    p = Prov(["m:1"])
    ok = lambda b, path, body=None, timeout=5: {"response": "OK"} if body else {"models": [{"name": "m:1", "size_vram": 0}]}
    assert mp.verify("http://x", "m:1", provider=p, http=ok, gpu_procs=[])["device"] == "CPU"
    gpu = [{"name": "ollama.exe", "memory_mb": 3000.0}]
    assert mp.verify("http://x", "m:1", provider=p, http=ok, gpu_procs=gpu)["device"] == "CUDA"
    assert not mp.verify("http://x", "other:1", provider=p, http=ok, gpu_procs=[])["listed"]

    def boom(*a, **k):
        raise OSError("connection refused")
    v = mp.verify("http://x", "m:1", provider=p, http=boom, gpu_procs=[])
    assert not v["inference"] and "didn't answer" in v["message"]


@pytest.mark.skipif(not os.environ.get("SAINT_LIVE_OLLAMA"), reason="set SAINT_LIVE_OLLAMA=model to run on real Ollama")
def test_live_ollama():
    v = mp.verify("http://localhost:11434", os.environ["SAINT_LIVE_OLLAMA"])
    assert v["listed"] and v["inference"] and v["device"] in ("CUDA", "CPU")
