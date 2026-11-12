"""
core/claude_agent.py

SAINT's agent mode, driven by Claude Code with the person's own Claude subscription (no API key): a task runs as
`claude -p <task> --output-format stream-json`, in the background, never taking focus. Its live progress becomes
the same plan events as any SAINT plan (plan.started / plan.step / plan.done), so the plan panel and the Agent page
show every step as it happens.

    start(task, cwd)          -> AgentRun (running in a thread); several can run at once
    follow_up(run_id, text)   -> AgentRun continuing the same Claude session (--resume: no context sent twice)
    approve(run_id)           -> AgentRun carrying out a plan that was made with trust "ask"
    stop(run_id)
    runs()                    -> the recent runs, newest first (also saved, as short summaries, in agent_runs.jsonl)

Trust (core/actions/trust.py, category "agent") decides how much Claude Code may do on its own:
    ask        --permission-mode plan        Claude only plans; the Agent page shows the plan with Approve
    ask_risky  --permission-mode dontAsk     reading, searching and editing files in the project run; anything else
               + a safe tool list            (shell commands, the web) is refused and reported, not asked about
    trusted    --permission-mode auto        Claude Code's own safety checks decide
Nothing ever runs with bypassPermissions.

Token thrift: a follow-up resumes the same session instead of re-sending history; each run is saved as a
one-paragraph summary (not the transcript), which is all SAINT sends back as context later.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.events import EventType, event_bus

log = logging.getLogger("saint.claude_agent")

SAFE_TOOLS = ["Read", "Glob", "Grep", "Edit", "MultiEdit", "Write", "NotebookEdit", "TodoWrite"]
MODES = {"ask": "plan", "ask_risky": "dontAsk", "trusted": "auto"}
CONTEXT = ("You are running as SAINT's agent on HalOS (Arch Linux, KDE Plasma 6). The person is not watching a "
           "terminal: keep a short todo list (TodoWrite) so they can follow along, prefer small verifiable steps, "
           "and end with a two or three sentence summary of what changed and anything they must do.")


@dataclass
class Step:
    title: str
    status: str = "pending"            # pending | running | done | failed | skipped
    message: str = ""


@dataclass
class AgentRun:
    id: str
    task: str
    cwd: str
    mode: str
    session_id: str = ""
    status: str = "starting"           # starting | running | planned | done | failed | stopped
    steps: List[Step] = field(default_factory=list)
    result: str = ""
    error: str = ""
    cost_usd: float = 0.0
    turns: int = 0
    started: float = field(default_factory=time.time)
    finished: float = 0.0
    parent: str = ""                   # the run this one follows up

    def summary(self) -> Dict:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


# --------------------------------------------------------------------------- your subscription, never API credits
# Any of these in Claude Code's environment makes it bill an API account instead of using your Claude sign-in.
API_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX", "ANTHROPIC_BEDROCK_BASE_URL", "ANTHROPIC_VERTEX_BASE_URL")
SIGN_IN_FIX = ("Sign in once: open a terminal, run `claude`, and choose your Claude account (Pro or Max) when it "
               "asks how to sign in. SAINT then uses your subscription; it never uses an API key.")


def subscription_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """The environment Claude Code runs with: everything that would switch it to API billing removed, so it can
    only use your signed-in Claude account (config agent.allow_api_key turns this off, for people who want that)."""
    env = dict(os.environ if env is None else env)
    try:
        from core.config import config
        if config.get("agent.allow_api_key", False):
            return env
    except Exception:
        pass
    for var in API_VARS:
        env.pop(var, None)
    return env


def signed_in(home: Optional[Path] = None, run: Callable = subprocess.run, exe: str = "claude") -> bool:
    """Is Claude Code signed in to a Claude account? Its sign-in file, else `claude auth status` (with no API key in
    the environment, so a key can't make it look signed in)."""
    home = Path.home() if home is None else Path(home)
    if (home / ".claude" / ".credentials.json").is_file():
        return True
    try:
        r = run([exe, "auth", "status"], capture_output=True, text=True, timeout=20, env=subscription_env())
    except (OSError, subprocess.SubprocessError):
        return False
    text = ((r.stdout or "") + (r.stderr or "")).lower()
    return r.returncode == 0 and "not logged in" not in text and "not signed in" not in text and "api key" not in text


# --------------------------------------------------------------------------- the command line
def claude_path(which: Callable[[str], Optional[str]] = shutil.which) -> str:
    return which("claude") or ""


def build_argv(task: str, mode: str, resume: str = "", model: str = "", exe: str = "claude") -> List[str]:
    if mode not in MODES.values():
        raise ValueError(f"unknown permission mode {mode!r}")
    argv = [exe, "-p", task, "--output-format", "stream-json", "--verbose", "--permission-mode", mode,
            "--append-system-prompt", CONTEXT]
    if mode == "dontAsk":
        argv += ["--allowedTools", ",".join(SAFE_TOOLS)]
    if resume:
        argv += ["--resume", resume]
    if model:
        argv += ["--model", model]
    return argv


def mode_for_trust(level: str) -> str:
    return MODES.get(level, MODES["ask_risky"])


# --------------------------------------------------------------------------- reading Claude Code's stream
def describe_tool(name: str, args: Dict) -> str:
    """A tool call in words, for the step list."""
    a = args or {}
    path = a.get("file_path") or a.get("notebook_path") or a.get("path") or ""
    short = Path(str(path)).name if path else ""
    if name == "Bash":
        cmd = str(a.get("description") or a.get("command") or "").strip().splitlines()[0][:90] if (a.get("description") or a.get("command")) else ""
        return f"Run: {cmd}" if not a.get("description") else str(a["description"])[:90]
    if name in ("Edit", "MultiEdit", "NotebookEdit"):
        return f"Edit {short}"
    if name == "Write":
        return f"Write {short}"
    if name == "Read":
        return f"Read {short}"
    if name in ("Grep", "Glob"):
        return f"Search for {str(a.get('pattern', ''))[:60]}"
    if name in ("WebFetch", "WebSearch"):
        return f"Look up {str(a.get('query') or a.get('url') or '')[:70]}"
    if name in ("Task", "Agent"):
        return f"Helper: {str(a.get('description', ''))[:70]}"
    return name


class StreamReader:
    """Folds Claude Code's stream-json lines into an AgentRun. Todo lists (TodoWrite) become the step list; without
    one, each tool call is a step."""

    def __init__(self, run: AgentRun):
        self.run = run
        self.todos = False
        self.pending: Dict[str, int] = {}          # tool_use id -> step index

    def feed(self, line: str) -> bool:
        """Apply one line; True when the step list or status changed."""
        try:
            ev = json.loads(line)
        except ValueError:
            return False
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            self.run.session_id = ev.get("session_id", self.run.session_id)
            self.run.status = "running"
            return True
        if kind == "assistant":
            changed = False
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") != "tool_use":
                    continue
                name, args = block.get("name", ""), block.get("input") or {}
                if name == "TodoWrite":
                    self._todos(args.get("todos") or [])
                    changed = True
                elif name == "ExitPlanMode":
                    self.run.result = str(args.get("plan", ""))
                    changed = True
                elif not self.todos:
                    self.run.steps.append(Step(describe_tool(name, args), "running"))
                    self.pending[block.get("id", "")] = len(self.run.steps) - 1
                    changed = True
            return changed
        if kind == "user":
            changed = False
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_result" and block.get("tool_use_id") in self.pending:
                    step = self.run.steps[self.pending.pop(block["tool_use_id"])]
                    step.status = "failed" if block.get("is_error") else "done"
                    if block.get("is_error"):
                        text = block.get("content")
                        step.message = (text if isinstance(text, str) else json.dumps(text))[:200]
                    changed = True
            return changed
        if kind == "result":
            self.run.session_id = ev.get("session_id", self.run.session_id)
            self.run.cost_usd = float(ev.get("total_cost_usd") or 0)
            self.run.turns = int(ev.get("num_turns") or 0)
            ok = ev.get("subtype") == "success" and not ev.get("is_error")
            text = str(ev.get("result") or "")
            if self.run.mode == "plan" and ok:
                self.run.status = "planned"
                self.run.result = self.run.result or text
            else:
                self.run.status = "done" if ok else "failed"
                self.run.result = text if ok else self.run.result
                if not ok:
                    self.run.error = text or str(ev.get("subtype", "error")).replace("_", " ")
            for s in self.run.steps:
                if s.status in ("running", "pending") and self.run.status == "done" and not self.todos:
                    s.status = "done"
            return True
        return False

    def _todos(self, todos: List[Dict]):
        self.todos = True
        word = {"completed": "done", "in_progress": "running", "pending": "pending"}
        self.run.steps = [Step(str(t.get("content") or t.get("activeForm") or "Step"), word.get(t.get("status"), "pending"))
                          for t in todos]


# --------------------------------------------------------------------------- running
_runs: Dict[str, AgentRun] = {}
_procs: Dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def _store() -> Path:
    from core.paths import data_path
    return data_path("agent_runs.jsonl")


def _emit(run: AgentRun, kind: str):
    steps = [{"index": i, "action": "agent", "title": s.title, "status": s.status, "message": s.message}
             for i, s in enumerate(run.steps)]
    if kind == "start":
        event_bus.emit_event(EventType.PLAN_STARTED, {"plan": run.id, "title": run.task[:80], "source": "agent",
                                                      "steps": steps or [{"index": 0, "title": "Starting Claude Code",
                                                                          "status": "running"}], "status": "running"})
    elif kind == "steps":
        for s in steps:
            event_bus.emit_event(EventType.PLAN_STEP, dict(s, plan=run.id, total=len(steps)))
    else:
        event_bus.emit_event(EventType.PLAN_DONE, {"plan": run.id, "title": run.task[:80], "ok": run.status in ("done", "planned"),
                                                   "steps": steps, "message": run.error or run.result[:300]})


def _save(run: AgentRun):
    """One short line per finished run: the task, the outcome in a paragraph, the session to resume. Never the
    transcript, so what SAINT sends back as context later stays small."""
    row = {"id": run.id, "task": run.task, "status": run.status, "summary": (run.result or run.error)[:600],
           "session_id": run.session_id, "cwd": run.cwd, "cost_usd": run.cost_usd, "turns": run.turns,
           "steps": len(run.steps), "started": run.started, "finished": run.finished, "parent": run.parent}
    try:
        path = _store()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        log.exception("agent.save_failed")


def _go(run: AgentRun, argv: List[str], popen: Callable):
    reader = StreamReader(run)
    try:
        proc = popen(argv, cwd=run.cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                     errors="replace", stdin=subprocess.DEVNULL, env=subscription_env(),
                     **({"creationflags": 0x08000000} if os.name == "nt" else {}))      # no console window
    except OSError as e:
        run.status, run.error = "failed", f"Claude Code couldn't start: {e}"
        run.finished = time.time()
        _emit(run, "done")
        return
    with _lock:
        _procs[run.id] = proc
    for line in proc.stdout:
        if reader.feed(line):
            _emit(run, "steps")
    proc.wait()
    err = proc.stderr.read() if proc.stderr else ""
    with _lock:
        _procs.pop(run.id, None)
    if run.status in ("starting", "running"):
        if run.status != "stopped":
            run.status = "failed"
            run.error = run.error or _explain(err, proc.returncode)
    run.finished = time.time()
    _emit(run, "done")
    _save(run)


def _explain(stderr: str, code: int) -> str:
    low = (stderr or "").lower()
    if "not logged in" in low or "login" in low or "authenticate" in low or "api key" in low:
        return "Claude Code isn't signed in. " + SIGN_IN_FIX
    if "usage limit" in low or "rate limit" in low or "429" in low:
        return "Your Claude usage limit is reached for now. It resets after a few hours."
    if "enotfound" in low or "network" in low or "econnrefused" in low:
        return "Claude Code couldn't reach the internet."
    return (stderr or "").strip().splitlines()[-1][:200] if stderr.strip() else f"Claude Code stopped (code {code})."


def start(task: str, cwd: Optional[str] = None, trust_level: Optional[str] = None, resume: str = "",
          parent: str = "", popen: Callable = subprocess.Popen, which: Callable = shutil.which,
          wait: bool = False) -> AgentRun:
    task = (task or "").strip()
    if trust_level is None:
        from core.actions import trust
        trust_level = trust.get_level("agent")
    mode = mode_for_trust(trust_level)
    cwd = cwd or str(Path.home())
    run = AgentRun(uuid.uuid4().hex[:10], task, cwd, mode, session_id=resume, parent=parent)
    exe = claude_path(which)
    with _lock:
        _runs[run.id] = run
    if not task:
        run.status, run.error = "failed", "There's no task to give Claude Code."
    elif not exe:
        run.status, run.error = "failed", ("Claude Code isn't installed. Install it from Settings > AI agents "
                                           "(it uses your Claude subscription, no API key).")
    elif not signed_in(exe=exe):
        run.status, run.error = "failed", "Claude Code isn't signed in to your Claude account yet. " + SIGN_IN_FIX
    if run.status == "failed":
        run.finished = time.time()
        _emit(run, "done")
        return run
    from core.config import config
    argv = build_argv(task, mode, resume, config.get("agent.claude_model", ""), exe)
    _emit(run, "start")
    if wait:
        _go(run, argv, popen)
    else:
        threading.Thread(target=_go, args=(run, argv, popen), daemon=True, name=f"claude-{run.id}").start()
    return run


def follow_up(run_id: str, text: str, **kw) -> AgentRun:
    prev = _runs.get(run_id)
    if prev is None or not prev.session_id:
        raise KeyError("That task can't be continued (it never started a Claude session).")
    return start(text, prev.cwd, resume=prev.session_id, parent=run_id, **kw)


def approve(run_id: str, **kw) -> AgentRun:
    """Carry out the plan an "ask" run made, in the same session, with files allowed."""
    prev = _runs.get(run_id)
    if prev is None or prev.status != "planned":
        raise KeyError("There's no plan waiting for approval.")
    return start("Go ahead with the plan.", prev.cwd, trust_level="ask_risky", resume=prev.session_id, parent=run_id, **kw)


def stop(run_id: str) -> bool:
    with _lock:
        proc = _procs.get(run_id)
        run = _runs.get(run_id)
    if proc is None or run is None:
        return False
    run.status, run.error = "stopped", "Stopped."
    proc.terminate()
    return True


def runs(limit: int = 30) -> List[AgentRun]:
    with _lock:
        return sorted(_runs.values(), key=lambda r: -r.started)[:limit]


def recent_summaries(limit: int = 5) -> List[Dict]:
    """The last finished runs as short summaries, for SAINT to mention without re-reading transcripts."""
    try:
        rows = [json.loads(l) for l in _store().read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []
    return rows[-limit:][::-1]
