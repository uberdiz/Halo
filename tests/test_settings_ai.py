"""The device profile and first-boot setup, GPU use in the health check, the Claude provider and key, and the one
settings window with its HalOS and SAINT groups. No GPU, network or subprocess is really used."""

import json
import os
import subprocess
import types
from pathlib import Path

import pytest

from core import device_profile as dp
from core import evolve, health, provision
from core.config import Config, config
from modules.ai.providers import AnthropicProvider, get_provider
from ui import saintos_center as sc

ROOT = Path(__file__).resolve().parent.parent
DISK = 500


# --------------------------------------------------------------------------- tiers
@pytest.mark.parametrize("gpu, vram, ram, tier, model, whisper, device, compute", [
    ("", 0, 4, "cpu-1b", "llama3.2:1b", "tiny.en", "cpu", "int8"),
    ("", 0, 8, "cpu-3b", "llama3.2:3b", "base.en", "cpu", "int8"),
    ("", 0, 11.5, "cpu-8b", "llama3.1:8b", "base.en", "cpu", "int8"),
    ("RTX 3050", 4, 16, "gpu-4", "llama3.2:3b", "base.en", "cuda", "int8_float16"),
    ("RTX 5060 Ti", 7.996, 48, "gpu-8", "llama3.1:8b", "small.en", "cuda", "float16"),
    ("RTX 4070", 12, 32, "gpu-12", "llama3.1:8b", "medium.en", "cuda", "float16"),
    ("RTX 5060 Ti", 15.99, 48, "gpu-16", "qwen2.5:14b", "large-v3-turbo", "cuda", "float16"),
    ("RTX 4090", 24, 64, "gpu-24", "qwen2.5:32b", "large-v3-turbo", "cuda", "float16"),
])
def test_tiers(gpu, vram, ram, tier, model, whisper, device, compute):
    p = dp.choose(dp.Hardware(gpu_name=gpu, vram_gb=vram, ram_gb=ram, cpu_threads=16, disk_free_gb=DISK))
    assert (p.tier, p.ollama_model, p.whisper_model, p.whisper_device, p.whisper_compute) == (
        tier, model, whisper, device, compute)
    assert p.use_gpu == bool(gpu) and p.tts_provider == "kokoro" and p.tts_device == "cpu"


def test_same_12_gb_line_as_the_default_model():
    from core.config import choose_ollama_model
    gib = 1024 ** 3
    for ram in (8, 11.5, 12, 32):
        got = dp.choose(dp.Hardware(ram_gb=ram, cpu_threads=8, disk_free_gb=DISK)).ollama_model
        assert got == choose_ollama_model(int(ram * gib), has_gpu=False)


def test_small_card_and_few_threads_use_the_cpu_tier():
    p = dp.choose(dp.Hardware(gpu_name="GT 1030", vram_gb=2, ram_gb=16, cpu_threads=2, disk_free_gb=DISK))
    assert not p.use_gpu and p.whisper_model == "tiny.en" and "GT 1030" in p.notes[0]


def test_disk_decides_last():
    # 60 GB free on a 24 GB card: 20 GB model still fits. 25 GB free: 12 for the stack + 8 reserved leaves 5.
    big = dict(gpu_name="RTX 4090", vram_gb=24, ram_gb=64, cpu_threads=16)
    assert dp.choose(dp.Hardware(disk_free_gb=60, **big)).ollama_model == "qwen2.5:32b"
    tight = dp.choose(dp.Hardware(disk_free_gb=25, **big))
    assert tight.use_gpu and tight.ollama_model == "llama3.2:3b" and any("Smaller" in n for n in tight.notes)
    no_stack = dp.choose(dp.Hardware(disk_free_gb=15, **big))
    assert not no_stack.use_gpu and any("GPU libraries" in n for n in no_stack.notes)
    nothing = dp.choose(dp.Hardware(disk_free_gb=8.2, ram_gb=64, cpu_threads=16))
    assert nothing.ollama_model == "" and any("no language model" in n for n in nothing.notes)


def test_detect_reads_the_biggest_card_and_never_raises():
    def run(argv, timeout=10):
        return types.SimpleNamespace(returncode=0, stdout="NVIDIA GeForce GT 710, 2048\nNVIDIA GeForce RTX 5060 Ti, 8188\n")

    def read(path):
        if path == "/proc/meminfo":
            return "MemTotal:       49283072 kB\n"
        if path == "/proc/cpuinfo":
            return "model name : AMD Ryzen 9 5900XT\n"
        raise OSError(path)
    hw = dp.detect(run=run, read=read, disk_usage=lambda _p: types.SimpleNamespace(free=900e9), cpu_count=lambda: 32)
    assert hw.gpu_name == "NVIDIA GeForce RTX 5060 Ti" and round(hw.vram_gb) == 8 and round(hw.ram_gb) == 47
    assert hw.cpu_name == "AMD Ryzen 9 5900XT" and hw.cpu_threads == 32 and hw.disk_free_gb == 900

    def broken(argv, timeout=10):
        raise FileNotFoundError("nvidia-smi")
    gone = dp.detect(run=broken, read=lambda p: "nouveau" if p == "/run/halo/gpu" else (_ for _ in ()).throw(OSError()),
                     disk_usage=lambda _p: types.SimpleNamespace(free=1e9))
    assert gone.gpu_name == "" and "nouveau" in gone.gpu_note


# --------------------------------------------------------------------------- config
def _store(values):
    data = dict(values)
    return data, data.get, lambda k, v, persist=True: data.__setitem__(k, v)


DEFAULTS = {"ai.model": "llama3.1:8b", "voice.stt_model": "base.en", "voice.stt_device": "cuda",
            "voice.stt_compute_type": "float16", "voice.tts_backend": "kokoro", "voice.tts_device": "cuda"}
PROFILE = dp.Profile("gpu-16", "qwen2.5:14b", "large-v3-turbo", "cuda", "float16", True).to_dict()


def test_config_gets_the_profile_only_where_the_user_changed_nothing():
    data, get, set_ = _store({**DEFAULTS, "voice.stt_model": "tiny.en"})     # the user's own choice
    changed = dp.apply_to_config(PROFILE, get, set_, DEFAULTS.get)
    assert data["ai.model"] == "qwen2.5:14b" and data["voice.stt_model"] == "tiny.en" and data["voice.tts_device"] == "cpu"
    assert "voice.stt_model" not in changed
    # A later profile may replace what the last one wrote, not what the user changes afterwards.
    data["ai.model"] = "my-model"
    dp.apply_to_config({**PROFILE, "ollama_model": "llama3.1:8b", "whisper_device": "cpu"}, get, set_, DEFAULTS.get)
    assert data["ai.model"] == "my-model" and data["voice.stt_device"] == "cpu"


# --------------------------------------------------------------------------- first-boot setup
class Runner:
    """pacman, pip and systemctl as subprocess.run; pip "installs" the libraries into --target."""

    def __init__(self, fail=None):
        self.calls, self.fail = [], fail or {}

    def __call__(self, argv, **_kw):
        self.calls.append(argv)
        key = next((k for k in self.fail if k in " ".join(argv)), None)
        if key:
            return types.SimpleNamespace(returncode=1, stdout="", stderr=self.fail[key])
        if argv[:2] == ["pacman", "-Q"]:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="not found")
        if "pip" in argv:
            target = Path(argv[argv.index("--target") + 1])
            for rel in ("nvidia/cublas/lib/libcublas.so.12", "nvidia/cudnn/lib/libcudnn.so.9"):
                (target / rel).parent.mkdir(parents=True, exist_ok=True)
                (target / rel).write_text("x")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")


def fake_fetch(model, cache):
    folder = Path(cache) / ("models--" + dp.WHISPER_REPOS[model].replace("/", "--"))
    (folder / "refs").mkdir(parents=True)
    (folder / "refs" / "main").write_text("abc")
    (folder / "snapshots" / "abc").mkdir(parents=True)
    for name in ("model.bin", "config.json"):
        (folder / "snapshots" / "abc" / name).write_text("x")


NVIDIA = dp.Hardware(gpu_name="RTX 5060 Ti", vram_gb=8, ram_gb=48, cpu_threads=24, disk_free_gb=DISK)
PLAIN = dp.Hardware(ram_gb=16, cpu_threads=8, disk_free_gb=DISK)


def test_setup_waits_for_a_network_but_knows_the_tier(tmp_path):
    run = Runner()
    assert provision.run(NVIDIA, run, online=lambda: False, fetch=fake_fetch, root=tmp_path) == provision.RETRY
    assert run.calls == []
    assert provision.read_json(tmp_path / "device-profile.json")["tier"] == "gpu-8"
    assert "HALO_PROFILE_MODEL=llama3.1:8b" in (tmp_path / "device-profile.env").read_text()


def test_nvidia_setup_installs_cuda_writes_the_library_path_and_downloads_whisper(tmp_path):
    run = Runner()
    assert provision.run(NVIDIA, run, online=lambda: True, fetch=fake_fetch, root=tmp_path) == 0
    joined = [" ".join(c) for c in run.calls]
    assert "pacman -S --needed --noconfirm ollama-cuda" in joined
    assert not any("-Syu" in c for c in joined)
    assert any("nvidia-cublas-cu12==" in c and "--target" in c for c in joined)
    assert "systemctl restart ollama.service" in joined
    env = (tmp_path / "gpu" / "env").read_text().replace("\\", "/")
    assert "nvidia/cublas/lib" in env and "nvidia/cudnn/lib" in env and "LD_LIBRARY_PATH" in env
    assert provision.whisper_present("small.en", tmp_path)
    st = provision.status(tmp_path)
    assert st["state"]["stage"] == "ready" and st["state"]["gpu"]["status"] == "ready"
    assert "gpu-8" in provision.describe(st)
    # Run again (the service retrying): nothing is installed twice.
    again = Runner()
    assert provision.run(NVIDIA, again, online=lambda: True, fetch=fake_fetch, root=tmp_path) == 0
    assert again.calls == []


def test_other_machines_skip_all_of_it(tmp_path):
    run = Runner()
    assert provision.run(PLAIN, run, online=lambda: True, fetch=fake_fetch, root=tmp_path) == 0
    assert run.calls == [] and not (tmp_path / "gpu").exists() and provision.whisper_present("base.en", tmp_path)


def test_stale_package_database_upgrades_and_asks_for_a_restart(tmp_path):
    run = Runner(fail={"pacman -S --needed": "error: failed retrieving file"})
    assert provision.run(NVIDIA, run, online=lambda: True, fetch=fake_fetch, root=tmp_path) == 0
    assert any("-Syu" in c for c in run.calls)
    assert provision.status(tmp_path)["state"]["gpu"]["restart_needed"] is True


def test_network_trouble_retries_and_a_real_failure_falls_back_to_cpu_with_the_reason(tmp_path):
    busy = Runner(fail={"pacman -S": "error: unable to lock database"})
    assert provision.run(NVIDIA, busy, online=lambda: True, fetch=fake_fetch, root=tmp_path) == provision.RETRY

    broken = Runner(fail={"pacman -S": "error: conflicting files"})
    root = tmp_path / "b"
    assert provision.run(NVIDIA, broken, online=lambda: True, fetch=fake_fetch, root=root) == 0
    st = provision.status(root)
    assert st["state"]["gpu"]["status"] == "failed" and "conflicting files" in st["state"]["gpu"]["why"]
    assert st["profile"]["whisper_device"] == "cpu" and st["profile"]["whisper_compute"] == "int8"
    assert any("conflicting files" in n for n in st["profile"]["notes"])
    # It stays on the CPU instead of looping, until `device-setup --force`.
    later = Runner()
    assert provision.run(NVIDIA, later, online=lambda: True, fetch=fake_fetch, root=root) == 0 and later.calls == []
    forced = Runner()
    assert provision.run(NVIDIA, forced, online=lambda: True, fetch=fake_fetch, root=root, force=True) == 0
    assert forced.calls and provision.status(root)["state"]["gpu"]["status"] == "ready"


def test_a_failed_whisper_download_retries(tmp_path):
    def no_net(model, cache):
        raise OSError("connection reset")
    assert provision.run(PLAIN, Runner(), online=lambda: True, fetch=no_net, root=tmp_path) == provision.RETRY
    assert provision.status(tmp_path)["state"]["stage"] == "waiting to retry"


def test_whisper_source_prefers_the_first_boot_download(tmp_path, monkeypatch):
    from core import model_assets
    assert model_assets.whisper_source("small.en") == "small.en"          # not downloaded: by name
    fake_fetch("small.en", tmp_path / "whisper")
    monkeypatch.setattr(provision, "STATE_DIR", tmp_path)
    assert Path(model_assets.whisper_source("small.en")).name == "abc" and model_assets.whisper_ready("small.en")


def test_service_runs_setup_first_and_never_live():
    fs = ROOT / "packaging/linux/rootfs"
    unit = (fs / "usr/lib/systemd/system/saint-ollama-model.service").read_text(encoding="utf-8")
    assert unit.index("ExecStartPre=/usr/libexec/saintos/device-setup") < unit.index("ExecStart=/usr/libexec/saintos/ollama-model")
    assert "ConditionKernelCommandLine=!archisobasedir" in unit and "Restart=on-failure" in unit
    assert "/run/archiso" in (fs / "usr/libexec/saintos/device-setup").read_text(encoding="utf-8")
    assert "/var/lib/saint/gpu/env" in (fs / "usr/bin/saint").read_text(encoding="utf-8")
    pkg = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert "device-setup" in pkg and "/var/lib/saint" in pkg
    packages = (ROOT / "packaging/arch/profile/packages.x86_64").read_text(encoding="utf-8").splitlines()
    assert "ollama" in packages and "ollama-cuda" not in packages and "cuda" not in packages
    mode = subprocess.run(["git", "ls-files", "-s", "packaging/linux/rootfs/usr/libexec/saintos/device-setup"], cwd=ROOT,
                          capture_output=True, text=True).stdout
    assert mode.startswith("100755")


# --------------------------------------------------------------------------- health: really on the GPU?
def test_gpu_health_without_nvidia_and_before_a_full_check():
    assert health.ai_gpu(nvidia=lambda: "")["state"] == health.NOT_TESTED
    assert health.ai_gpu(nvidia=lambda: "RTX")["state"] == health.NOT_TESTED


def _on(detail="on"):
    return {"on_gpu": True, "detail": detail}


def test_gpu_health_says_which_engine_is_on_the_cpu_and_why(monkeypatch):
    monkeypatch.setattr(health, "_cfg", lambda k, d="": {"ai.provider": "ollama", "voice.stt_device": "cuda"}.get(k, d))
    kokoro = lambda: {"on_gpu": False, "expected_cpu": True, "detail": "on the CPU by design"}
    good = health.ai_gpu(True, lambda: "RTX", _on, _on, kokoro)
    assert good["state"] == health.WORKING and "by design" in good["detail"]
    bad = health.ai_gpu(True, lambda: "RTX", _on, lambda: {"on_gpu": False, "detail": "libcublas.so.12 missing"}, kokoro)
    assert bad["state"] == health.DEGRADED and "Whisper not on the GPU" in bad["detail"] and "libcublas" in bad["detail"]


def test_gpu_ollama_reads_video_memory_from_a_loaded_model():
    post = lambda url, body, timeout: {"response": "ok"}
    on = health.gpu_ollama("http://x", "m", post, lambda u: {"models": [{"name": "m", "size": 100, "size_vram": 100}]})
    assert on["on_gpu"] and "100%" in on["detail"]
    off = health.gpu_ollama("http://x", "m", post, lambda u: {"models": [{"name": "m", "size": 100, "size_vram": 0}]})
    assert not off["on_gpu"] and "ollama-cuda" in off["detail"]


def test_gpu_whisper_and_kokoro_use_what_the_engine_answers():
    def proc(out="", err="", code=0):
        return lambda argv, timeout=0: types.SimpleNamespace(returncode=code, stdout=out, stderr=err)
    assert health.gpu_whisper("m", "float16", proc('{"device": "cuda"}'))["on_gpu"]
    failed = health.gpu_whisper("m", "float16", proc(err="RuntimeError: Library libcublas.so.12 is not found", code=1))
    assert not failed["on_gpu"] and "libcublas" in failed["detail"]
    assert not health.gpu_kokoro("m", proc('{"providers": ["CPUExecutionProvider"]}'))["on_gpu"]
    assert health.gpu_kokoro("m", proc('{"providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]}'))["on_gpu"]


# --------------------------------------------------------------------------- Claude
class SSE:
    status_code, text = 200, ""

    def __init__(self, events):
        self.lines = [b"event: x"] + [b"data: " + json.dumps(e).encode() for e in events]

    def iter_lines(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capture(monkeypatch, response):
    import modules.ai.providers as prov
    sent = {}

    def post(url, headers=None, json=None, timeout=None, stream=False):
        sent.update(url=url, headers=headers, body=json)
        return response
    monkeypatch.setattr(prov.requests, "post", post)
    return sent


def _saved_key(monkeypatch, key="sk-ant-test"):
    real = config.get
    monkeypatch.setattr(config, "get", lambda k, d=None: key if k == "ai.anthropic_api_key" else real(k, d))


def test_claude_streams_text_with_the_current_api(monkeypatch):
    _saved_key(monkeypatch)
    sent = _capture(monkeypatch, SSE([
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hel"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "lo"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
        {"type": "message_stop"}]))
    tokens = []
    out = get_provider("anthropic").stream_send(
        [{"role": "system", "content": "Be brief."}, {"role": "system", "content": "It is noon."},
         {"role": "user", "content": "hi"}], "claude-sonnet-5-5", "sk-openai-other", "", 0.7, 30, tokens.append, None)
    assert out == "Hello" and tokens == ["Hel", "lo"]
    body, headers = sent["body"], sent["headers"]
    assert sent["url"].endswith("/v1/messages") and headers["x-api-key"] == "sk-ant-test"     # never the OpenAI key
    assert body["system"] == "Be brief.\n\nIt is noon." and body["messages"] == [{"role": "user", "content": "hi"}]
    assert "temperature" not in body and body["stream"] is True and body["fallbacks"] == "default"
    assert headers["anthropic-beta"] == "server-side-fallback-2026-07-01"


def test_claude_without_a_key_says_where_to_add_one(monkeypatch):
    _saved_key(monkeypatch, "")
    from modules.ai.providers import ProviderError
    with pytest.raises(ProviderError, match="Settings > AI"):
        get_provider("anthropic").send([{"role": "user", "content": "hi"}], "m", "", "", 0.5, 5)


def test_claude_tool_turn_replays_thinking_and_returns_results_in_one_message(monkeypatch):
    _saved_key(monkeypatch)
    _capture(monkeypatch, SSE([
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hm"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig"}},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "t1", "name": "a", "input": {}}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"x"'}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": ': 1}'}},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "t2", "name": "b", "input": {}}},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}}]))
    schema = {"type": "function", "function": {"name": "a", "description": "d", "parameters": {"type": "object"}}}
    turn = AnthropicProvider().stream_turn([{"role": "user", "content": "go"}], "claude-sonnet-5-5", "", 30,
                                           lambda t: None, tools=[schema])
    assert [c["id"] for c in turn["calls"]] == ["t1", "t2"] and turn["calls"][0]["function"]["arguments"] == {"x": 1}
    assert turn["blocks"][0] == {"type": "thinking", "thinking": "hm", "signature": "sig"}
    system, msgs = AnthropicProvider.convert([
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "", "tool_calls": turn["calls"], "anthropic_blocks": turn["blocks"]},
        {"role": "tool", "content": "r1", "tool_name": "a", "tool_call_id": "t1"},
        {"role": "tool", "content": "r2", "tool_name": "b", "tool_call_id": "t2"}])
    assert msgs[1]["content"][0]["signature"] == "sig" and len(msgs) == 3
    assert [b["tool_use_id"] for b in msgs[2]["content"]] == ["t1", "t2"]
    assert AnthropicProvider.tool_schema(schema)["input_schema"] == {"type": "object"}


def test_cut_off_tool_call_doesnt_run_and_refusal_is_an_error(monkeypatch):
    from modules.ai.providers import ProviderError
    _saved_key(monkeypatch)
    _capture(monkeypatch, SSE([
        {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "t", "name": "a", "input": {}}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"x'}},
        {"type": "message_delta", "delta": {"stop_reason": "max_tokens"}}]))
    assert AnthropicProvider().stream_turn([{"role": "user", "content": "go"}], "m", "", 30, lambda t: None)["calls"] == []
    _capture(monkeypatch, SSE([{"type": "message_delta", "delta": {"stop_reason": "refusal"}}]))
    with pytest.raises(ProviderError, match="declined"):
        AnthropicProvider().stream_send([{"role": "user", "content": "x"}], "m", "", "", 0.5, 5, lambda t: None, None)


def test_key_test_costs_nothing_and_never_repeats_the_key(monkeypatch):
    import modules.ai.providers as prov
    seen = {}

    def get(url, headers=None, timeout=None):
        seen.update(url=url, key=headers["x-api-key"])
        return types.SimpleNamespace(status_code=401, text="", json=lambda: {})
    monkeypatch.setattr(prov.requests, "get", get)
    res = AnthropicProvider().test_key("sk-ant-secret")
    assert seen == {"url": prov.ANTHROPIC_URL + "/models", "key": "sk-ant-secret"}
    assert res["connected"] is False and "sk-ant-secret" not in json.dumps(res)


def test_module_uses_claudes_own_model_setting():
    from modules.ai.module import AIModule
    assert AIModule._resolve_model(None, "anthropic", "", "llama3.1:8b")[0] == config.get("ai.anthropic_model")


def test_key_goes_to_the_secret_store_only(tmp_path):
    import keyring
    from core.paths import keyring_service
    path = tmp_path / "config.json"
    c = Config(path)
    assert c.set_secret("ai.anthropic_api_key", "sk-ant-new") and c.get("ai.anthropic_api_key") == "sk-ant-new"
    c.save()
    assert "sk-ant-new" not in path.read_text(encoding="utf-8")
    assert keyring.get_password(keyring_service(), "ai.anthropic_api_key") == "sk-ant-new"
    assert c.set_secret("ai.anthropic_api_key", "") and c.get("ai.anthropic_api_key", "") == ""


def test_no_secret_store_refuses_instead_of_writing_the_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    c = Config(path)
    monkeypatch.setattr(c, "_secret_write", lambda k, v: False)
    assert c.set_secret("ai.anthropic_api_key", "sk-ant-new") is False
    c.save()
    assert "sk-ant-new" not in path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- Evolve with the saved key
def test_saved_key_only_reaches_claude_code_when_not_signed_in(tmp_path):
    env = evolve.claude_env(env={"PATH": "x"}, home=tmp_path, key="sk-ant-k")
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-k" and "ANTHROPIC_API_KEY" not in os.environ
    assert "ANTHROPIC_API_KEY" not in evolve.claude_env(env={"PATH": "x"}, home=tmp_path, key="")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    assert "ANTHROPIC_API_KEY" not in evolve.claude_env(env={"PATH": "x"}, home=tmp_path, key="sk-ant-k")


def test_claude_status_accepts_the_saved_key_and_the_fix_mentions_it(tmp_path):
    def run(argv, **_):
        if "--version" in argv:
            return types.SimpleNamespace(returncode=0, stdout="2.1\n", stderr="")
        return types.SimpleNamespace(returncode=1, stdout="not logged in", stderr="")
    which = lambda _n: "/usr/bin/claude"
    assert evolve.claude_status(which, run, tmp_path, {}, key="sk-ant-k").ok
    missing = evolve.claude_status(which, run, tmp_path, {}, key="")
    assert not missing.ok and "API key" in missing.fix and "claude auth login" in missing.fix


# --------------------------------------------------------------------------- the one settings window
@pytest.fixture
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _extra(title, group=None):
    mod = types.SimpleNamespace(TITLE=title, ICON="power")
    if group:
        mod.GROUP = group
    return mod


def test_rail_rows_have_two_groups_and_extra_pages_join_halos(monkeypatch):
    monkeypatch.setattr(sc, "is_halo", lambda: True)
    rows = sc.rail_rows([_extra("Drives & OS"), _extra("Tweaks", "SAINT")])
    names = [n for n, _ in rows]
    assert [n for n, icon in rows if not icon] == ["HalOS", "SAINT"]
    assert names.index("HalOS") < names.index("Welcome") < names.index("Drives & OS") < names.index("Updates") < names.index("SAINT")
    assert names.index("SAINT") < names.index("AI") and names[-1] == "Tweaks"
    assert sc.group_of("Recovery", rows) == sc.HALOS and sc.group_of("Voice", rows) == sc.SAINT
    assert len(names) == len(set(names))                                   # one place for each page
    windows = [n for n, _ in sc.rail_rows([], os_pages=False)]
    assert "HalOS" not in windows and "Recovery" not in windows and "Service" not in windows and "AI" in windows


def test_every_row_builds_and_shows_its_page(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = sc.build_window("Voice")
    assert win._stack.count() == win._nav.count() == len(win._page_names)
    assert win._page_names[win._nav.currentRow()] == "Voice" and win._settings.isVisibleTo(win)
    for name in win._page_names:
        if win._nav.item(win._page_names.index(name)).flags():
            assert win._open(name)
            app.processEvents()
            assert win._page_names[win._stack.currentIndex()] == name
            assert win._settings.isVisibleTo(win) == (name in win._settings.category_pages)
    # Duplicate controls are gone: one Save bar, and the AI page has the Claude box.
    assert sum(b.text() == "Save settings" for b in win.findChildren(QPushButton)) == 1
    assert {"Save key", "Remove", "Test a reply", "Download model"} <= {b.text() for b in win.findChildren(QPushButton)}
    win.close()


def test_a_heading_is_skipped_and_groups_open_their_first_page(app, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = sc.build_window("Updates")
    win._open_group(sc.HALOS)
    assert win._page_names[win._nav.currentRow()] == "Updates"             # already in the group: stays
    win._open_group(sc.SAINT)
    assert win._page_names[win._nav.currentRow()] == "General"
    win._nav.setCurrentRow(win._page_names.index(sc.SAINT))
    assert win._page_names[win._nav.currentRow()] == "General"             # the heading passes to its first page
    assert win._open("Desktop & devices") and win._page_names[win._nav.currentRow()] == "Plasma settings"
    win.close()


def test_welcome_can_be_dismissed_but_opens_when_asked_for(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = sc.build_window("Welcome")
    row = win._page_names.index("Welcome")
    assert not win._nav.item(row).isHidden()
    next(b for b in win.findChildren(QPushButton) if b.text().startswith("Done,")).click()
    assert win._nav.item(row).isHidden() and win._page_names[win._nav.currentRow()] != "Welcome"
    assert sc.welcome_done_mark().exists()
    win.close()
    later = sc.build_window("")
    assert later._nav.item(row).isHidden()
    assert later._open("Welcome") and not later._nav.item(row).isHidden()  # saintos-control --welcome still works
    later.close()


def test_search_finds_settings_across_both_groups(app, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = sc.build_window("General")
    names = win._page_names
    visible = lambda: [names[r] for r in range(len(names)) if not win._nav.item(r).isHidden()]
    win._rail.search.setText("barge")                                      # a label inside Voice
    assert visible() == ["SAINT", "Voice"] and names[win._nav.currentRow()] == "Voice"
    win._rail.search.setText("firmware")                                   # a button inside Recovery
    assert "Recovery" in visible() and "SAINT" not in visible()
    win._rail.search.clear()
    assert "AI" in visible() and "Updates" in visible()
    win.close()


def test_claude_key_controls_mask_save_test_remove(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QLineEdit
    from ui.settings_ui import SettingsUI
    s = SettingsUI()
    assert s.claude_key.echoMode() == QLineEdit.Password
    monkeypatch.setattr(s, "_claude_test", lambda: None)
    s.claude_key.setText("sk-ant-paste")
    s._claude_save()
    assert s.claude_key.text() == "" and config.get("ai.anthropic_api_key") == "sk-ant-paste"
    assert "saved" in s.claude_key.placeholderText()
    s._claude_remove()
    assert not config.get("ai.anthropic_api_key", "") and s.claude_status.text() == "No key saved."
    # Only the provider's own fields show.
    s.provider_combo.setCurrentIndex(s.provider_combo.findData("anthropic"))
    assert not s._ai_form.isRowVisible(s.base_url_line) and not s._ai_form.isRowVisible(s.openai_key_line)
    s.provider_combo.setCurrentIndex(s.provider_combo.findData("openai"))
    assert s._ai_form.isRowVisible(s.base_url_line) and s._ai_form.isRowVisible(s.openai_key_line)
    s.load()
    s.close()


def test_names_people_read_say_halos():
    text = (ROOT / "ui/saintos_center.py").read_text(encoding="utf-8")
    assert "Halo itself" not in text and "Halo updates" not in text and "Halo repository" not in text
    settings = (ROOT / "ui/settings_ui.py").read_text(encoding="utf-8")
    assert '"Halo & overlay"' in settings                                  # the glow keeps its name
