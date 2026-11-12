"""Agents matched to the hardware: what's recommended on small, mid-range and big PCs, models reused from Windows,
and the settings page."""
import os

import pytest

from core import agent_catalog as ac
from core.device_profile import Hardware

SMALL = Hardware(ram_gb=4, cpu_threads=4, disk_free_gb=60)
MID = Hardware(gpu_name="RTX 3060 Ti", vram_gb=8, ram_gb=16, cpu_threads=12, disk_free_gb=300)
BIG = Hardware(gpu_name="RTX 4090", vram_gb=24, ram_gb=64, cpu_threads=32, disk_free_gb=900)


def _by_id(ratings):
    return {r.id: r for r in ratings}


def test_catalog_is_well_formed():
    entries = ac.load()
    assert entries[0]["id"] == "claude-code" and entries[0]["kind"] == "cloud"
    for e in entries:
        assert e["install"].split(":", 1)[0] in ("ollama", "featured")
        if e["kind"] == "local":
            assert all(k in e for k in ("size_gb", "params_b", "min_ram_gb", "min_vram_gb"))


def test_claude_code_is_always_recommended_and_first():
    for hw in (SMALL, MID, BIG):
        ratings = ac.rate(hw)
        assert ratings[0].id == "claude-code" and ratings[0].status == ac.RECOMMENDED


def test_a_4_gb_laptop_gets_the_small_model_and_is_told_why_the_rest_wont_run():
    r = _by_id(ac.rate(SMALL))
    assert r["llama3.2:1b"].status == ac.RECOMMENDED
    assert r["llama3.1:8b"].status == ac.TOO_HEAVY and "12 GB of RAM" in r["llama3.1:8b"].reason
    assert r["qwen2.5:32b"].status == ac.TOO_HEAVY


def test_an_8_gb_gpu_runs_8b_models_on_the_gpu_and_not_the_32b():
    r = _by_id(ac.rate(MID))
    assert r["llama3.1:8b"].status == ac.RECOMMENDED and "RTX 3060 Ti" in r["llama3.1:8b"].reason
    assert r["qwen2.5-coder:7b"].status == ac.WILL_RUN
    assert r["qwen2.5:32b"].status == ac.TOO_HEAVY
    assert r["llama3.1:8b"].tokens_per_s > r["llama3.2:1b"].tokens_per_s / 10       # a rough but sane estimate


def test_a_24_gb_gpu_is_recommended_the_biggest_model():
    r = _by_id(ac.rate(BIG))
    assert r["qwen2.5:32b"].status == ac.RECOMMENDED and r["qwen2.5:32b"].tokens_per_s >= 10


def test_too_little_disk_is_a_reason_of_its_own():
    full = Hardware(gpu_name="RTX 4090", vram_gb=24, ram_gb=64, cpu_threads=32, disk_free_gb=20)
    r = _by_id(ac.rate(full))
    assert r["qwen2.5:32b"].status == ac.TOO_HEAVY and "disk" in r["qwen2.5:32b"].reason


def test_installed_things_are_marked():
    have = ac.installed_ids(which=lambda c: "/usr/bin/claude" if c == "claude" else None, models=["llama3.1:8b"])
    assert have == {"claude-code", "llama3.1:8b"}
    r = _by_id(ac.rate(MID, installed=have))
    assert r["claude-code"].installed and r["llama3.1:8b"].installed and not r["qwen2.5:14b"].installed


def test_models_downloaded_on_windows_are_found_and_copied_never_overwritten(tmp_path):
    store = tmp_path / "mnt/windows/Users/me/.ollama/models"
    (store / "manifests/registry.ollama.ai/library/llama3.1").mkdir(parents=True)
    (store / "manifests/registry.ollama.ai/library/llama3.1/8b").write_text("{}")
    (store / "manifests/registry.ollama.ai/someone/tool").mkdir(parents=True)
    (store / "manifests/registry.ollama.ai/someone/tool/latest").write_text("{}")
    (store / "blobs").mkdir()
    (store / "blobs/sha256-abc").write_bytes(b"x" * 1000)
    found = ac.windows_model_stores(globs=[str(tmp_path / "mnt/*/Users/*/.ollama/models")])
    assert found and found[0]["models"] == ["llama3.1:8b", "someone/tool:latest"]
    steps = ac.reuse_steps(found[0]["path"], dest="/var/lib/ollama")
    assert steps[0].argv[:4] == ["pkexec", "cp", "-rn", "--"]                 # -n: an existing file is never replaced
    assert steps[1].argv[-2:] == ["ollama:ollama", "/var/lib/ollama"]


def test_ollama_models_dir_reads_the_service():
    run = lambda argv, **kw: type("R", (), {"stdout": "HOME=/var/lib/ollama OLLAMA_MODELS=/srv/models\n"})()
    assert ac.ollama_models_dir(run) == "/srv/models"
    none = lambda argv, **kw: type("R", (), {"stdout": ""})()
    assert ac.ollama_models_dir(none) == "/var/lib/ollama/.ollama/models"


def test_install_starts_the_right_thing(monkeypatch):
    from core import model_pull
    started = []
    monkeypatch.setattr(model_pull, "start", lambda url, model, **kw: started.append(model) or True)
    res = ac.install("llama3.2:3b")
    assert res["ok"] and started == ["llama3.2:3b"] and "2.0 GB" in res["message"]
    assert not ac.install("nonsense")["ok"]


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_settings_page_lists_ratings_and_offers_reuse(qapp, monkeypatch):
    from ui.settings_pages import agents
    monkeypatch.setattr(agents, "run_async", lambda fn, done, failed: done(fn()))
    store = {"path": "/mnt/w/Users/me/.ollama/models", "models": ["llama3.1:8b"], "size_gb": 4.9}
    page = agents.AgentsPage(detect=lambda: MID, installed=lambda: {"claude-code"}, stores=lambda: [store])
    assert "16 GB of RAM" in page.summary.text() and "RTX 3060 Ti" in page.summary.text()
    first = page.rows[0]
    assert first.rating.id == "claude-code" and first.button.text() == "Installed" and not first.button.isEnabled()
    heavy = next(r for r in page.rows if r.rating.id == "qwen2.5:32b")
    assert not heavy.button.isEnabled() and heavy.badge.text() == "Too heavy for this PC"
    assert not page.reuse.isHidden()


def test_memory_the_os_keeps_back_does_not_push_a_pc_below_its_size():
    r = _by_id(ac.rate(Hardware(ram_gb=47.9, cpu_threads=32, disk_free_gb=400)))
    assert r["qwen2.5:32b"].status != ac.TOO_HEAVY and "CPU" in r["qwen2.5:32b"].reason
