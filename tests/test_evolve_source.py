"""core/evolve.py, OS Expansion Agent: repository index, skill registry, Claude Code detection, and a source
change in an isolated git worktree through plan -> approve -> snapshot -> apply -> test -> keep/rollback.
Claude Code, pkexec/snapper and pytest are stood in for; git is real."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core import evolve

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def _g(repo, *args):
    env_args = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", *env_args, "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "core").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "modules" / "spotify").mkdir(parents=True)
    (r / "core" / "volume.py").write_text('"""Volume control for SAINT."""\n\ndef set_volume(v):\n    return v\n\n'
                                          'class Mixer:\n    def mute(self):\n        pass\n', encoding="utf-8")
    (r / "tests" / "test_volume.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (r / "modules" / "spotify" / "module.py").write_text('"""Spotify playback."""\n', encoding="utf-8")
    (r / "README.md").write_text("# Halo\n\n## Install\n", encoding="utf-8")
    (r / "big.bin").write_bytes(b"\0" * 10)
    _g(r, "init", "-q")
    _g(r, "add", "-A")
    _g(r, "commit", "-q", "-m", "init")
    return r


class Run:
    """Records privileged/test commands; snapper prints numbers; pytest returns ``test_rc``."""

    def __init__(self, test_rc=0, fs="btrfs"):
        self.calls, self.n, self.test_rc, self.fs = [], 10, test_rc, fs

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        out, rc = "", 0
        if argv[:1] == ["findmnt"]:
            out = self.fs + "\n"
        elif "--print-number" in argv:
            self.n += 1
            out = f"{self.n}\n"
        elif "pytest" in argv:
            rc, out = self.test_rc, ("1 passed" if self.test_rc == 0 else "1 failed")
        return type("R", (), {"returncode": rc, "stdout": out, "stderr": ""})()


def fake_claude(edit=True, rc=0, text="ok"):
    calls = []

    def claude(prompt, cwd, tools, mode, on_line):
        calls.append({"prompt": prompt, "cwd": Path(cwd), "tools": tools, "mode": mode})
        if mode == "plan":
            return rc, "1. Edit core/volume.py: add get_volume.\n2. Test in tests/test_volume.py."
        if edit:
            p = Path(cwd) / "core" / "volume.py"
            p.write_text(p.read_text(encoding="utf-8") + "\ndef get_volume():\n    return 1\n", encoding="utf-8")
        return rc, text
    claude.calls = calls
    return claude


def test_index_summaries_symbols_and_hash_cache(repo, tmp_path):
    cache = tmp_path / "ix"
    ix = evolve.build_index(repo, cache_dir=cache)
    e = ix.files["core/volume.py"]
    assert e["summary"] == "Volume control for SAINT."
    assert {"set_volume", "Mixer", "Mixer.mute"} <= set(e["symbols"])
    assert ix.files["README.md"]["summary"] == "Halo" and "big.bin" not in ix.files
    assert ix.computed == len(ix.files) and ix.reused == 0
    assert ix.search("change the volume when muted")[0] == "core/volume.py"
    assert "core/volume.py: Volume control for SAINT." in ix.context("volume")

    (repo / "core" / "volume.py").write_text('"""Louder."""\n', encoding="utf-8")
    ix2 = evolve.build_index(repo, cache_dir=cache)
    assert ix2.computed == 1 and ix2.reused == len(ix2.files) - 1      # only the changed file was re-read
    assert ix2.files["core/volume.py"]["summary"] == "Louder."


def test_skill_registry_is_cached_until_something_changes(repo, tmp_path):
    ix = evolve.build_index(repo, cache_dir=tmp_path / "ix")
    skills = tmp_path / "skills.json"
    skills.write_text(json.dumps([{"phrase": "open my music", "steps": ["a", "b"]}]), encoding="utf-8")
    ext = tmp_path / "ext"
    (ext / "gpu-temp").mkdir(parents=True)
    cache = tmp_path / "reg.json"
    reg = evolve.skill_registry(ix, skills_file=skills, ext_dir=ext, cache=cache)
    kinds = {(e["kind"], e["name"]) for e in reg}
    assert {("module", "spotify"), ("learned", "open my music"), ("extension", "gpu-temp")} <= kinds
    data = json.loads(cache.read_text(encoding="utf-8"))
    data["entries"] = [{"kind": "module", "name": "from-cache"}]
    cache.write_text(json.dumps(data), encoding="utf-8")
    assert evolve.skill_registry(ix, skills_file=skills, ext_dir=ext, cache=cache)[0]["name"] == "from-cache"
    (ext / "another").mkdir()
    assert any(e["name"] == "another" for e in evolve.skill_registry(ix, skills_file=skills, ext_dir=ext, cache=cache))


def test_claude_status_says_how_to_fix(tmp_path):
    def ok_run(argv, **kw):
        rc = 1 if argv[1:] == ["auth", "status"] else 0
        return type("R", (), {"returncode": rc, "stdout": "2.1.0 (Claude Code)\n", "stderr": ""})()

    missing = evolve.claude_status(which=lambda n: None)
    assert not missing.ok and "@anthropic-ai/claude-code" in missing.fix
    signed_out = evolve.claude_status(which=lambda n: "/usr/bin/claude", run=ok_run, home=tmp_path, env={})
    assert not signed_out.ok and "claude auth login" in signed_out.fix and "2.1.0" in signed_out.message
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    assert evolve.claude_status(which=lambda n: "/usr/bin/claude", run=ok_run, home=tmp_path, env={}).ok
    assert evolve.claude_status(which=lambda n: "/usr/bin/claude", run=ok_run, home=tmp_path / "x",
                                env={"ANTHROPIC_API_KEY": "k"}).ok


def test_claude_argv_is_non_interactive_and_scoped():
    argv = evolve.claude_argv("do it", evolve.CLAUDE_APPLY_TOOLS, "acceptEdits")
    assert argv[:2] == ["claude", "-p"] and argv[-1] == "do it"
    assert argv[argv.index("--allowedTools") + 1] == evolve.CLAUDE_APPLY_TOOLS
    assert "WebFetch" in argv[argv.index("--disallowedTools") + 1]
    assert "Bash(git push:*)" in evolve.CLAUDE_DENY_TOOLS and "Bash(" not in evolve.CLAUDE_PLAN_TOOLS


def test_snapshot_kinds():
    assert evolve.snapshot("x", run=Run(fs="ext4"))["kind"] is None
    assert evolve.snapshot("x", run=Run(), which=lambda n: "/usr/bin/snapper") == {"kind": "snapper", "number": 11}
    run = Run()
    s = evolve.snapshot("x", run=run, which=lambda n: None)
    assert s["kind"] == "btrfs" and run.calls[-1][:5] == ["pkexec", "btrfs", "subvolume", "snapshot", "-r"]


def test_full_flow_keep(repo, tmp_path):
    root = tmp_path / "evolve"
    ix = evolve.build_index(repo, cache_dir=tmp_path / "ix")
    ch = evolve.start_source_change(repo, "add a get volume function", root=root)
    assert Path(ch.worktree).is_dir() and ch.branch.startswith("evolve/")
    claude, run = fake_claude(), Run()
    snap = lambda d, r: evolve.snapshot(d, run=r, which=lambda n: "/usr/bin/snapper")

    with pytest.raises(RuntimeError):                                   # nothing applies before approval
        evolve.apply_source_change(ch, claude=claude, run=run, snap=snap)
    plan = evolve.plan_source_change(ch, ix=ix, claude=claude)
    assert "get_volume" in plan and ch.status == "planned"
    assert claude.calls[0]["mode"] == "plan" and claude.calls[0]["tools"] == evolve.CLAUDE_PLAN_TOOLS
    assert claude.calls[0]["cwd"] == Path(ch.worktree) and "core/volume.py" in claude.calls[0]["prompt"]

    evolve.approve(ch)
    d = evolve.apply_source_change(ch, ix=ix, claude=claude, run=run, snap=snap)
    assert "get_volume" in d and ch.status == "applied"
    assert ch.snapshot == {"kind": "snapper", "number": 11} and ch.post_snapshot["number"] == 12
    assert "get_volume" not in (repo / "core" / "volume.py").read_text(encoding="utf-8")   # checkout untouched

    t = evolve.test_source_change(ch, run=run, python="py")
    assert t["passed"] and t["targets"] == ["tests/test_volume.py"] and ch.status == "tested"
    assert ["py", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_volume.py"] in run.calls

    msg = evolve.keep(ch)
    assert "Kept" in msg and "get_volume" in (repo / "core" / "volume.py").read_text(encoding="utf-8")
    assert not Path(ch.worktree).exists()
    assert evolve.source_history(root)[0]["status"] == "kept"
    assert evolve.SourceChange.load(ch.meta / "change.json").status == "kept"


def test_failed_tests_roll_back(repo, tmp_path):
    root = tmp_path / "evolve"
    ch = evolve.start_source_change(repo, "add a get volume function", root=root)
    claude, run = fake_claude(), Run(test_rc=1)
    snap = lambda d, r: evolve.snapshot(d, run=r, which=lambda n: "/usr/bin/snapper")
    evolve.plan_source_change(ch, claude=claude)
    evolve.approve(ch)
    evolve.apply_source_change(ch, claude=claude, run=run, snap=snap)
    assert not evolve.test_source_change(ch, run=run)["passed"] and ch.status == "failed"
    with pytest.raises(RuntimeError):
        evolve.keep(ch)
    done = evolve.rollback(ch, run=run)
    assert run.calls[-1] == ["pkexec", "snapper", "-c", "root", "undochange", "11..12"]
    assert "system files restored from the snapshot" in done and ch.status == "rolled back"
    assert not Path(ch.worktree).exists()
    branches = subprocess.run(["git", "-C", str(repo), "branch"], capture_output=True, text=True).stdout
    assert "evolve/" not in branches


def test_not_signed_in_and_no_change_are_reported(repo, tmp_path):
    ch = evolve.start_source_change(repo, "x y z", root=tmp_path / "e")
    with pytest.raises(RuntimeError, match="isn't signed in"):
        evolve.plan_source_change(ch, claude=lambda *a: (1, "Invalid API key · Please run /login"))
    ch.status = "approved"
    with pytest.raises(RuntimeError, match="without changing anything"):
        evolve.apply_source_change(ch, claude=fake_claude(edit=False), run=Run(fs="ext4"))
    assert ch.status == "failed" and ch.snapshot["kind"] is None
    evolve.rollback(ch, run=Run())


def test_tests_for_maps_modules_to_tests(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_evolve.py").write_text("", encoding="utf-8")
    assert evolve.tests_for(["core/evolve.py", "tests/test_new.py", "README.md"], tmp_path) == \
        ["tests/test_evolve.py", "tests/test_new.py"]
