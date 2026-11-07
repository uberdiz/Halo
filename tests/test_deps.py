"""core/deps.py: declared per-subsystem dependencies, detect -> confirm -> install -> verify -> test."""

import subprocess

import pytest

from core import deps, health


def proc(code=0, out=""):
    return subprocess.CompletedProcess([], code, out, "")


def env(**kw):
    base = dict(which=lambda n: None, run=lambda a, timeout=8: proc(1), find_spec=lambda m: None, linux=True,
                has_nvidia=lambda: False, asset_ready=lambda n: False, model_present=lambda m: False,
                flathub=lambda: False, python="/opt/saint/bin/python", prefix_writable=False)
    base.update(kw)
    return deps.Env(**base)


ARCH = dict(which=lambda n: "/usr/bin/pacman" if n == "pacman" else None)


class FakePopen:
    calls = []

    def __init__(self, argv, **kw):
        FakePopen.calls.append(argv)
        self.stdout = iter(["ok\n"])
        self._code = 0

    def wait(self):
        return self._code


def test_manifests_are_well_formed():
    kinds = {"pacman", "pip", "flatpak-remote", "service", "asset", "ollama-model"}
    for key, m in deps.MANIFESTS.items():
        assert m["label"]
        for d in m["deps"]:
            assert d["kind"] in kinds and d["name"] and d.get("why"), (key, d)
            assert d.get("when", "") in ("", "linux", "pacman", "nvidia")


def test_when_conditions():
    e = env(**ARCH)
    assert [d["name"] for d in deps.detect("gpu", e)] == []                       # no NVIDIA card
    e = env(has_nvidia=lambda: True, **ARCH)
    assert [d["name"] for d in deps.detect("gpu", e)] == ["nvidia-open", "nvidia-utils"]
    win = env(linux=False)
    assert [d["kind"] for d in deps.detect("ollama", win)] == ["ollama-model"]     # no pacman/systemd on Windows
    assert deps.detect("flatpak", win) == []


def test_detect_uses_binary_module_asset_and_pacman_query():
    e = env(which=lambda n: "/usr/bin/" + n if n in ("pacman", "ollama") else None,
            run=lambda a, timeout=8: proc(0) if a[:2] == ["systemctl", "is-enabled"] else proc(1),
            model_present=lambda m: m == "llama3.1:8b")
    found = {d["name"]: d["present"] for d in deps.detect("ollama", e)}
    assert found["ollama"] and found["ollama.service"]
    k = deps.detect("kokoro", env(find_spec=lambda m: object() if m == "onnxruntime" else None,
                                  asset_ready=lambda n: n == "kokoro"))
    assert {d["name"]: d["present"] for d in k} == {"onnxruntime": True, "kokoro-onnx": False, "misaki[en]": False,
                                                     "sounddevice": False, "kokoro": True}
    e = env(run=lambda a, timeout=8: proc(0) if a == ["pacman", "-Q", "archlinux-keyring"] else proc(1), **ARCH)
    assert deps.detect("pacman", e) == [{"kind": "pacman", "name": "archlinux-keyring",
                                         "why": "verifies package signatures", "present": True}]


def test_plan_groups_admin_steps_through_pkexec():
    e = env(has_nvidia=lambda: True, **ARCH)
    acts = deps.plan("gpu", e)
    assert len(acts) == 1 and acts[0].needs_admin
    assert acts[0].argv == ["pkexec", "pacman", "-Syu", "--needed", "--noconfirm", "nvidia-open", "nvidia-utils"]
    acts = deps.plan("flatpak", e)
    assert acts[0].argv[:2] == ["pkexec", "pacman"] and acts[1].argv[:3] == ["flatpak", "remote-add", "--user"]
    assert not acts[1].needs_admin


def test_pip_needs_pkexec_only_when_the_venv_is_read_only():
    acts = deps.plan("whisper", env(prefix_writable=False))
    assert acts[0].argv[:4] == ["pkexec", "/opt/saint/bin/python", "-m", "pip"] and acts[0].needs_admin
    assert acts[1].fn is not None and acts[1].label.startswith("Download SAINT's whisper")
    acts = deps.plan("whisper", env(prefix_writable=True))
    assert acts[0].argv[0] == "/opt/saint/bin/python" and not acts[0].needs_admin


def test_unsafe_names_never_reach_a_command(monkeypatch):
    monkeypatch.setitem(deps.MANIFESTS, "evil", {"label": "x", "deps": [
        {"kind": "pacman", "name": "foo; rm -rf /", "why": "x"},
        {"kind": "pip", "name": "--index-url=http://evil", "why": "x"},
        {"kind": "service", "name": "a b.service", "why": "x"}]})
    assert deps.plan("evil", env(**ARCH)) == []


def test_install_asks_first_and_runs_nothing_when_declined():
    FakePopen.calls = []
    asked = []
    res = deps.install("gpu", confirm=lambda a: asked.append([x.label for x in a]) or False,
                       env=env(has_nvidia=lambda: True, **ARCH), popen=FakePopen,
                       verify=lambda k, f: pytest.fail("no verify when cancelled"), blockers=lambda: ([], []))
    assert res["status"] == "cancelled" and asked and FakePopen.calls == []


def test_install_blocked_while_pacman_is_busy():
    res = deps.install("gpu", confirm=lambda a: pytest.fail("don't ask when it can't run"),
                       env=env(has_nvidia=lambda: True, **ARCH),
                       blockers=lambda: (["Another app install or update is running"], []))
    assert res["status"] == "blocked" and "running" in res["errors"]["pacman"]


def test_install_runs_verifies_and_tests_heavy_subsystems(monkeypatch):
    from core import model_assets
    FakePopen.calls = []
    checks = []

    def verify(key, full):
        checks.append((key, full))
        return health._result(health.WORKING, "ok")
    fetched = []
    monkeypatch.setattr(model_assets, "ensure_whisper", lambda: fetched.append(1) or True)
    e = env(prefix_writable=True, asset_ready=lambda n: False)
    res = deps.install("whisper", confirm=lambda a: True, env=e, popen=FakePopen, verify=verify,
                       blockers=lambda: ([], []))
    assert FakePopen.calls and FakePopen.calls[0][1:4] == ["-m", "pip", "install"]
    assert fetched == [1] and res["errors"] == {}
    assert res["status"] == "ok" and checks == [("whisper", False), ("whisper", True)]
    assert res["steps"][0].startswith("Install Python packages faster-whisper")


def test_install_records_failures_and_reports_failed(monkeypatch):
    class Fail(FakePopen):
        def __init__(self, argv, **kw):
            super().__init__(argv, **kw)
            self.stdout = iter(["error: failed retrieving file: Could not resolve host\n"])
            self._code = 1
    res = deps.install("gpu", confirm=lambda a: True, env=env(has_nvidia=lambda: True, **ARCH), popen=Fail,
                       verify=lambda k, f: health._result(health.FAILED, "driver not loaded"),
                       blockers=lambda: ([], []))
    assert res["status"] == "failed"
    assert "network" in res["errors"]["nvidia-open"].lower() and res["test"] is None   # gpu isn't heavy


def test_in_process_step_failure_is_reported():
    e = env(model_present=lambda m: False, linux=False)
    acts = deps.plan("ollama", e)
    assert len(acts) == 1 and acts[0].fn is not None
    acts[0].fn = lambda: (_ for _ in ()).throw(RuntimeError("Ollama isn't answering"))
    import core.deps as d
    orig = d.plan
    try:
        d.plan = lambda key, env=None, missing=None: acts
        res = d.install("ollama", confirm=lambda a: True, env=e,
                        verify=lambda k, f: health._result(health.DEGRADED, "model missing"), test=False)
    finally:
        d.plan = orig
    assert res["status"] == "failed" and "isn't answering" in next(iter(res["errors"].values()))


def test_nothing_to_do_still_verifies():
    e = env(asset_ready=lambda n: True, find_spec=lambda m: object())
    res = deps.install("whisper", confirm=lambda a: pytest.fail("nothing to ask"), env=e,
                       verify=lambda k, f: health._result(health.WORKING, "ok"), test=False)
    assert res["status"] == "nothing to do" and res["verify"]["state"] == health.WORKING
