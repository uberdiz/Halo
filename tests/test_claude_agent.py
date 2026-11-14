"""SAINT's agent mode on Claude Code: the right command line for each trust level (never bypassPermissions), live
steps from Claude Code's stream, follow-ups resuming the same session, plan approval, and the Agent page.
Claude Code is faked: no usage is spent."""
import io
import json
import os

import pytest

from core import claude_agent as ca

SID = "5f0c2c1e-0000-4000-8000-000000000001"


def ev(**kw):
    return json.dumps(kw) + "\n"


def tool(id_, name, args):
    return ev(type="assistant", message={"content": [{"type": "tool_use", "id": id_, "name": name, "input": args}]})


def result_of(id_, error=False, text="ok"):
    return ev(type="user", message={"content": [{"type": "tool_result", "tool_use_id": id_, "is_error": error,
                                                 "content": text}]})


DONE = ev(type="result", subtype="success", is_error=False, result="Fixed the test: the date parser now handles UTC.",
          session_id=SID, total_cost_usd=0.04, num_turns=6)
STREAM = [ev(type="system", subtype="init", session_id=SID, tools=["Read", "Edit", "Bash"]),
          tool("t1", "TodoWrite", {"todos": [{"content": "Find the failing test", "status": "in_progress"},
                                             {"content": "Fix the parser", "status": "pending"}]}),
          tool("t2", "Read", {"file_path": "/home/me/app/parser.py"}), result_of("t2"),
          tool("t3", "TodoWrite", {"todos": [{"content": "Find the failing test", "status": "completed"},
                                             {"content": "Fix the parser", "status": "completed"}]}),
          DONE]


class FakeProc:
    def __init__(self, lines, code=0, err=""):
        self.stdout = iter(lines)
        self.stderr = io.StringIO(err)
        self.returncode = code
        self.terminated = False

    def wait(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


def fake_popen(lines, code=0, err="", seen=None):
    def popen(argv, **kw):
        if seen is not None:
            seen.append((argv, kw))
        return FakeProc(lines, code, err)
    return popen


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "_store", lambda: tmp_path / "agent_runs.jsonl")
    monkeypatch.setattr(ca, "signed_in", lambda *a, **k: True)
    ca._runs.clear()
    yield


@pytest.mark.parametrize("level, mode", [("ask", "plan"), ("ask_risky", "dontAsk"), ("trusted", "auto")])
def test_trust_levels_map_to_permission_modes_and_never_bypass(level, mode):
    argv = ca.build_argv("do it", ca.mode_for_trust(level))
    assert argv[:3] == ["claude", "-p", "do it"] and argv[argv.index("--permission-mode") + 1] == mode
    assert "bypassPermissions" not in argv and "--dangerously-skip-permissions" not in argv
    assert ("--allowedTools" in argv) == (mode == "dontAsk")
    if mode == "dontAsk":
        assert "Bash" not in argv[argv.index("--allowedTools") + 1]
    with pytest.raises(ValueError):
        ca.build_argv("x", "bypassPermissions")


def test_a_run_turns_the_stream_into_live_steps_and_a_summary():
    seen = []
    run = ca.start("fix the failing test", "/home/me/app", trust_level="ask_risky", which=lambda c: "/usr/bin/claude",
                   popen=fake_popen(STREAM, seen=seen), wait=True)
    assert run.status == "done" and run.session_id == SID and run.turns == 6
    assert [(s.title, s.status) for s in run.steps] == [("Find the failing test", "done"), ("Fix the parser", "done")]
    assert "UTC" in run.result
    argv, kw = seen[0]
    assert kw["cwd"] == "/home/me/app" and kw["stdin"] is not None              # nothing waits on a terminal
    saved = [json.loads(l) for l in ca._store().read_text(encoding="utf-8").splitlines()]
    assert saved[0]["summary"].startswith("Fixed the test") and "transcript" not in saved[0]


def test_without_a_todo_list_each_tool_call_is_a_step_and_failures_say_why():
    lines = [ev(type="system", subtype="init", session_id=SID),
             tool("a", "Bash", {"command": "npm test", "description": "Run the tests"}), result_of("a", True, "3 failing"),
             tool("b", "Edit", {"file_path": "/p/src/date.ts"}), result_of("b"),
             ev(type="result", subtype="error_max_turns", is_error=True, result="", session_id=SID)]
    run = ca.start("fix it", "/p", trust_level="trusted", which=lambda c: "claude", popen=fake_popen(lines), wait=True)
    assert [(s.title, s.status) for s in run.steps] == [("Run the tests", "failed"), ("Edit date.ts", "done")]
    assert run.steps[0].message == "3 failing" and run.status == "failed" and "max turns" in run.error


def test_follow_up_resumes_the_same_session():
    first = ca.start("fix it", "/p", trust_level="ask_risky", which=lambda c: "claude", popen=fake_popen(STREAM), wait=True)
    seen = []
    second = ca.follow_up(first.id, "now add a test for it", which=lambda c: "claude", popen=fake_popen(STREAM, seen=seen),
                          wait=True, trust_level="ask_risky")
    argv = seen[0][0]
    assert argv[argv.index("--resume") + 1] == SID and second.parent == first.id and second.cwd == "/p"


def test_ask_trust_plans_first_and_approval_carries_it_out():
    plan_stream = [ev(type="system", subtype="init", session_id=SID),
                   tool("p", "ExitPlanMode", {"plan": "1. Read parser.py\n2. Fix the UTC branch"}),
                   ev(type="result", subtype="success", is_error=False, result="", session_id=SID)]
    planned = ca.start("fix it", "/p", trust_level="ask", which=lambda c: "claude", popen=fake_popen(plan_stream), wait=True)
    assert planned.status == "planned" and "Fix the UTC branch" in planned.result
    seen = []
    done = ca.approve(planned.id, which=lambda c: "claude", popen=fake_popen(STREAM, seen=seen), wait=True)
    argv = seen[0][0]
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk" and argv[argv.index("--resume") + 1] == SID
    assert done.status == "done"
    with pytest.raises(KeyError):
        ca.approve(done.id)


def test_missing_claude_and_sign_in_problems_are_explained():
    run = ca.start("anything", "/p", trust_level="ask_risky", which=lambda c: None, wait=True)
    assert run.status == "failed" and "Settings > AI agents" in run.error
    lines = [ev(type="system", subtype="init", session_id=SID)]
    out = ca.start("x", "/p", trust_level="ask_risky", which=lambda c: "claude",
                   popen=fake_popen(lines, 1, "Error: Not logged in. Please run /login"), wait=True)
    assert out.status == "failed" and "sign in" in out.error


def test_runs_show_on_the_plan_panel_through_plan_events():
    from core.events import EventType, event_bus
    got = []
    handler = lambda e: got.append(e.type) if e.type.startswith("plan.") else None
    event_bus.subscribe(handler)
    try:
        ca.start("fix it", "/p", trust_level="ask_risky", which=lambda c: "claude", popen=fake_popen(STREAM), wait=True)
    finally:
        event_bus.unsubscribe(handler)
    assert got[0] == EventType.PLAN_STARTED and got[-1] == EventType.PLAN_DONE and EventType.PLAN_STEP in got


def test_agent_page_starts_shows_and_follows_up(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.pages.agent import AgentPage
    real_start = ca.start
    monkeypatch.setattr(ca, "start", lambda task, cwd=None, **kw: real_start(
        task, cwd or "/p", trust_level="ask_risky", which=lambda c: "claude", popen=fake_popen(STREAM), wait=True,
        **{k: v for k, v in kw.items() if k in ("resume", "parent")}))
    page = AgentPage()
    assert "No tasks yet" in page.title.text()
    page.task.setText("fix the failing test")
    page.go()
    assert page.list.count() == 1 and page.title.text() == "fix the failing test"
    assert page.badge.text() == "Done" and "UTC" in page.result.toPlainText()
    assert page.more.isEnabled() and not page.stop_btn.isEnabled() and page.approve_btn.isHidden()
    page.more.setText("now add a test")
    page.follow()
    assert page.list.count() == 2


@pytest.mark.parametrize("text, task", [("ask claude to fix the failing tests in my app", "fix the failing tests in my app"),
                                        ("SAINT, have the agent clean up my Downloads folder", "clean up my Downloads folder"),
                                        ("agent: write a README for AIDE", "write a README for AIDE")])
def test_saint_hands_bigger_jobs_to_the_agent(text, task, monkeypatch):
    from modules.agent import os_intents
    started = []
    monkeypatch.setattr(ca, "start", lambda t, *a, **k: started.append(t) or ca.AgentRun("r1", t, "/", "dontAsk"))
    intent = os_intents.parse_os(text)
    assert intent is not None and intent.name == "os.agent"
    reply = intent.run()
    assert started == [task] and "background" in reply.text


def test_claude_code_never_gets_an_api_key(monkeypatch):
    """A key anywhere in the environment would make Claude Code bill API credits instead of the subscription."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-be-used")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("PATH_MARKER", "kept")
    seen = []
    ca.start("fix it", "/p", trust_level="ask_risky", which=lambda c: "claude", popen=fake_popen(STREAM, seen=seen), wait=True)
    env = seen[0][1]["env"]
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_BASE_URL" not in env and env["PATH_MARKER"] == "kept"


def test_not_signed_in_says_how_to_sign_in(monkeypatch, tmp_path):
    monkeypatch.setattr(ca, "signed_in", lambda *a, **k: False)
    run = ca.start("fix it", "/p", trust_level="ask_risky", which=lambda c: "claude", wait=True)
    assert run.status == "failed" and "run `claude`" in run.error and "never uses an API key" in run.error


def test_signed_in_check_reads_the_sign_in_file_and_ignores_keys(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    seen = []

    def run(argv, **kw):
        seen.append(kw.get("env", {}))
        return type("R", (), {"returncode": 1, "stdout": "Not logged in", "stderr": ""})()
    real = ca.__dict__["subscription_env"]
    assert real({"ANTHROPIC_API_KEY": "k", "HOME": "h"}) == {"HOME": "h"}
    import importlib
    fresh = importlib.reload(ca)
    assert fresh.signed_in(home=home, run=run) is False and "ANTHROPIC_API_KEY" not in seen[0]
    (home / ".claude/.credentials.json").write_text("{}")
    assert fresh.signed_in(home=home, run=run) is True


def test_status_is_the_one_installed_and_signed_in_check(tmp_path, monkeypatch):
    import importlib
    monkeypatch.undo()                      # the autouse fixture stubs signed_in
    importlib.reload(ca)

    def run_out(argv, **kw):
        return type("R", (), {"returncode": 1, "stdout": "Not logged in", "stderr": ""})()
    assert ca.status(which=lambda n: None, home=tmp_path) == ca.ClaudeStatus(False, False, "")
    st = ca.status(which=lambda n: "/usr/bin/claude", run=run_out, home=tmp_path)
    assert st.installed and not st.signed_in
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    assert ca.status(which=lambda n: "/usr/bin/claude", run=run_out, home=tmp_path).signed_in


def test_open_login_runs_the_sign_in_in_konsole_then_checks_again(monkeypatch):
    from core import claude_agent as ca
    seen = []
    states = iter([ca.ClaudeStatus(True, False, "/usr/bin/claude"), ca.ClaudeStatus(True, True, "/usr/bin/claude")])
    monkeypatch.setattr(ca, "status", lambda which=None: next(states))
    after = ca.open_login(run=lambda argv, **kw: seen.append(argv))
    assert after.signed_in and seen[0][:2] == ["konsole", "-e"] and "claude auth login" in seen[0][-1]
    assert "npm install -g @anthropic-ai/claude-code" in ca.login_command(installed=False)[-1]
