"""
core/evolve_chat.py

What the Evolve app's chat does without a model, and what it hands the model so it needs fewer turns:

    quick(text, cwd, last)     "commit", "status", "diff", "undo", "deploy": run directly, no model at all
    argv(...)                  Claude Code's command line. Local models get --bare (3 tools, ~1k tokens of prompt
                               instead of ~13k) and a short rule list; Claude keeps its full toolset
    context_for(request, cwd)  the few relevant files (evolve.build_index) and the lessons from earlier runs
    verify(cwd)                compile the changed Python files and run their tests (so the model doesn't have to)
    parse_reply(text)          QUESTION: / ROOT: / TEST: lines the agent ends with -> buttons, a root prompt, a checklist
    log_run / lesson / code_map / set_status      the vault notes (Evolve/Runs, Lessons, Code map) and status.json,
                               which SAINT reads to answer "how is Evolve doing?"
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core import evolve

STATUS = evolve.ROOT / "status.json"

# Read-only shell the agent may run unasked (everything else in Bash is refused in -p mode, not asked about).
SAFE_BASH = ["git status", "git diff", "git log", "git show", "grep", "rg", "ls", "cat", "head", "tail", "wc", "find",
             "sed -n", "python3 -m py_compile", "python -m py_compile", ".venv/bin/python -m py_compile"]
PROTOCOL = (" If you cannot continue without the user's decision (or something must be installed or approved), stop "
            "and end your reply with a line `QUESTION: <the question>` followed by 2-4 lines `- <option>`. If a "
            "command needs root, never use sudo: end your reply with `ROOT: <the exact command>` and stop; the user "
            "approves it and you get its output. When done, end with two or three sentences on what changed, then "
            "one `TEST: <something the user should try by hand>` line per thing to check.")
LOCAL_RULES = ("You are Evolve, a coding agent on HalOS (Arch Linux, KDE Plasma 6, Wayland), working in {cwd}; use "
               "absolute paths inside it. You have Bash (read-only commands: rg, grep, ls, cat, sed -n, git "
               "status/diff), Read and Edit. Work in few steps: 1) find the code with `rg -n` before reading; Read "
               "only the part you need (offset/limit). 2) Make the smallest change that does what was asked, "
               "reusing existing helpers. 3) Stop. Do not write documentation or new .md files, do not add extras "
               "that were not asked for, do not run git add/commit (the user says `commit`), and do not run tests: "
               "when you stop, SAINT compiles the changed files and runs their tests and tells you what failed. "
               "Edits take effect after SAINT restarts; say which part to restart.")
ROOT_NEVER = re.compile(r"rm\s+-[a-z]*r[a-z]*f?\s+/(\s|$|\*)|mkfs|\bdd\b.*of=/dev/|>\s*/dev/(sd|nvme)|:\(\)\s*\{")


# ------------------------------------------------------------------ no model: git and deploy
@dataclass
class Quick:
    title: str
    text: str
    ok: bool = True


_QUICK = [
    ("commit", r"(git )?commit( (the |my |all |these )?changes| it| this| that| everything)?"),
    ("status", r"(git )?(status|diff)|what( has|'s)? changed|show (me )?(the )?(changes|diff)"),
    ("undo", r"undo( that| it| the changes?| the last change)?|discard (the )?changes"),
    ("deploy", r"deploy( it| this)?|make it live"),
]


def quick_kind(text: str) -> str:
    t = " ".join((text or "").lower().split()).rstrip(".!?")
    return next((k for k, pat in _QUICK if re.fullmatch(pat, t)), "")


def changed(cwd: Path) -> List[str]:
    return [l[3:].split(" -> ")[-1].strip('"') for l in
            evolve._git(cwd, "status", "--porcelain", "--untracked-files=all").splitlines() if l.strip()]


def quick(text: str, cwd, last_request: str = "", run=subprocess.run) -> Optional[Quick]:
    """A request that is just a git/deploy command, done here. None: it needs the model."""
    kind = quick_kind(text)
    cwd = Path(cwd)
    if not kind or not (cwd / ".git").exists():
        return None
    try:
        files = changed(cwd)
        if kind == "status":
            return Quick("What changed", evolve._git(cwd, "status", "--short") + "\n" + evolve._git(cwd, "diff", "--stat")
                         if files else "Nothing has changed since the last commit.")
        if not files:
            return Quick(kind.capitalize(), "There are no changes to " + kind + ".")
        if kind == "commit":
            subject = (" ".join(last_request.split()) or f"Evolve: {len(files)} file(s) changed")[:72]
            evolve._git(cwd, "add", "-A")
            evolve._git(cwd, "commit", "-q", "-m", subject + "\n\n" + "\n".join(files[:50]))
            return Quick("Committed", f"{subject}\n{len(files)} file(s): " + ", ".join(files[:12])
                         + (" …" if len(files) > 12 else ""))
        if kind == "undo":
            name = "evolve undo " + time.strftime("%Y-%m-%d %H:%M:%S")
            evolve._git(cwd, "stash", "push", "-u", "-q", "-m", name)
            return Quick("Undone", f"{len(files)} file(s) set aside as stash “{name}”. Bring them back with: git stash pop")
        script = cwd / "deploy.sh"
        if not script.is_file():
            return Quick("Deploy", "This folder has no deploy.sh.", False)
        res = run(["bash", str(script)], cwd=str(cwd), capture_output=True, text=True, timeout=300,
                  stdin=subprocess.DEVNULL)
        out = ((res.stdout or "") + (res.stderr or "")).strip()[-1500:]
        if res.returncode != 0 and "sudo" in out:        # no terminal here for sudo's password prompt
            out += f"\n\ndeploy.sh needs your password. Run it in Konsole:  cd {cwd} && ./deploy.sh"
        return Quick("Deployed" if res.returncode == 0 else "Deploy failed", out, res.returncode == 0)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        return Quick(kind.capitalize() + " failed", str(e)[:600], False)


# ------------------------------------------------------------------ the command line
def argv(local: bool, mode: str, cwd: str, system: str, model: str = "", resume: str = "",
         add_dirs: Tuple[str, ...] = ()) -> List[str]:
    """Arguments after `claude`. The prompt goes in on stdin as stream-json lines and stdin stays open, so a
    message typed while the agent works becomes its next turn in the same process (no restart, nothing re-sent)."""
    out = ["-p", "--output-format", "stream-json", "--input-format", "stream-json", "--verbose",
           "--permission-mode", mode, "--allowedTools", ",".join(f"Bash({c}:*)" for c in SAFE_BASH)]
    if local:
        # --bare: no hooks, plugins, skills listing, MCP or CLAUDE.md discovery; Bash, Read and Edit only.
        out += ["--bare", "--system-prompt", LOCAL_RULES.format(cwd=cwd) + PROTOCOL + system]
    else:
        out += ["--append-system-prompt", system + PROTOCOL]
    dirs = [d for d in add_dirs if d and d != cwd]
    if dirs:
        out += ["--add-dir", *dirs]
    if model:
        out += ["--model", model]
    if resume:
        out += ["--resume", resume]
    return out


def user_line(text: str) -> bytes:
    """One user message for --input-format stream-json."""
    return (json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}})
            + "\n").encode("utf-8")


def context_for(request: str, cwd, n: int = 8) -> str:
    """Appended to the request: where to look, and what earlier runs learned. Deterministic, cached by content."""
    parts = []
    cwd = Path(cwd)
    if (cwd / ".git").exists():
        try:
            ctx = evolve.build_index(cwd).context(request, n)
            if ctx:
                parts.append("Files most likely relevant (path: summary [symbols]); check with rg before trusting:\n" + ctx)
        except (RuntimeError, OSError):
            pass
    learned = lessons()
    if learned:
        parts.append("Lessons from earlier runs here (follow them):\n" + learned)
    return "\n\n".join(parts)


# ------------------------------------------------------------------ after a run: checks, without a model
def verify(cwd, run=subprocess.run, timeout: int = 300) -> Tuple[bool, str]:
    """Compile every changed .py file and run the tests that cover them. (ok, what ran and what failed)."""
    cwd = Path(cwd)
    if not (cwd / ".git").exists():
        return True, ""
    files = [f for f in changed(cwd) if (cwd / f).is_file()]
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return True, f"{len(files)} file(s) changed, no Python to check." if files else "Nothing changed."
    python = str(cwd / ".venv" / "bin" / "python") if (cwd / ".venv" / "bin" / "python").is_file() else sys.executable
    said = []
    tests = evolve.tests_for(py, cwd)
    for name, n, cmd in (("compile", len(py), [python, "-c", _COMPILE, *py]),      # no .pyc left in the checkout
                         ("tests", len(tests), [python, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests])):
        if not n:
            said.append("no tests cover these files")
            continue
        try:
            res = run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"{name} didn't finish: {e}"
        if res.returncode != 0:
            return False, f"{name} failed:\n" + ((res.stdout or "") + (res.stderr or "")).strip()[-1500:]
        said.append(f"{name} ok ({n} file(s))")
    return True, "; ".join(said)


_COMPILE = "import sys\nfor f in sys.argv[1:]:\n    compile(open(f, encoding='utf-8').read(), f, 'exec')"


@dataclass
class Reply:
    question: str = ""
    options: List[str] = field(default_factory=list)
    root: str = ""
    tests: List[str] = field(default_factory=list)


def parse_reply(text: str) -> Reply:
    r = Reply()
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        s = line.strip().strip("*`").strip()
        if s.startswith("QUESTION:"):
            r.question = s[9:].strip()
            r.options = [l.strip()[1:].strip().strip("*`") for l in lines[i + 1:i + 6] if l.strip().startswith(("-", "•"))][:4]
        elif s.startswith("ROOT:"):
            r.root = s[5:].strip().strip("`")
        elif s.startswith("TEST:"):
            r.tests.append(s[5:].strip())
    return r


def parse_preflight(raw: str) -> Optional[Dict]:
    """The small model's JSON brief -> {"scope", "summary", "questions": [{"q", "options"}], "needs"}; None if unusable."""
    try:
        d = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, AttributeError):
        return None
    if not isinstance(d, dict):
        return None
    qs = [{"q": str(q.get("q", "")).strip()[:300], "options": [str(o)[:120] for o in (q.get("options") or [])][:4]}
          for q in (d.get("questions") or []) if isinstance(q, dict) and str(q.get("q", "")).strip()][:4]
    scope = str(d.get("scope", "")).lower()
    return {"scope": scope if scope in ("small", "medium", "large") else "", "summary": str(d.get("summary", ""))[:300],
            "questions": qs, "needs": [str(n)[:200] for n in (d.get("needs") or []) if str(n).strip()][:6]}


def root_refused(command: str) -> str:
    """Why Evolve won't run this as root even when approved; "" when it may be offered to the user."""
    if not command.strip():
        return "empty command"
    return "it could destroy the system (disk or / wipe)" if ROOT_NEVER.search(command) else ""


# ------------------------------------------------------------------ the vault: runs, lessons, code map
def _vault() -> Path:
    from core import vault
    d = vault.ensure(skills=False) / "Evolve"
    d.mkdir(parents=True, exist_ok=True)
    return d


def lessons(limit: int = 15) -> str:
    try:
        lines = [l for l in (_vault() / "Lessons.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    except OSError:
        return ""
    return "\n".join(lines[-limit:])


def lesson(text: str) -> bool:
    """Remember one lesson for later runs (once). True when it was new."""
    text = " ".join((text or "").split())[:300]
    p = _vault() / "Lessons.md"
    old = p.read_text(encoding="utf-8") if p.exists() else ("---\ntags: [evolve, lessons]\n---\n# Evolve lessons\n\n"
                                                              "One line per thing a run got wrong or you corrected. "
                                                              "Evolve gives the newest ones to every run; edit freely.\n\n")
    if not text or text.lower() in old.lower():
        return False
    p.write_text(old.rstrip("\n") + f"\n- {text} ({time.strftime('%Y-%m-%d')})\n", encoding="utf-8")
    return True


def log_run(request: str, cwd, ok: bool, checks: str, secs: float, model: str, answer: str = "",
            notes: Tuple[str, ...] = (), turns=None) -> Path:
    """One note per run in Evolve/Runs: what was asked, what changed, the checks, what to test by hand."""
    files = changed(Path(cwd)) if (Path(cwd) / ".git").exists() else []
    tests = parse_reply(answer).tests
    title = re.sub(r"[^\w\s-]", "", request.splitlines()[0] if request else "run").strip()[:50] or "run"
    p = _vault() / "Runs" / f"{time.strftime('%Y-%m-%d %H%M')} {title}.md"
    p.parent.mkdir(exist_ok=True)
    body = (f"---\ncreated: {time.strftime('%Y-%m-%d %H:%M')}\nresult: {'ok' if ok else 'failed'}\nmodel: {model}\n"
            f"seconds: {secs:.0f}\nturns: {turns if turns is not None else ''}\ntags: [evolve, run]\n---\n\n"
            f"## Request\n\n{request.strip()}\n\n## Changed\n\n"
            + ("\n".join(f"- `{f}`" for f in files) or "- nothing") + f"\n\n## Checks\n\n{checks or 'none'}\n\n"
            "## What to test\n\n" + ("\n".join(f"- [ ] {t}" for t in tests) or "- [ ] (the agent listed nothing)") + "\n"
            + ("\n## From notes\n\n" + "\n".join(f"- [[{n}]]" for n in notes) + "\n" if notes else "")
            + (f"\n## Agent's summary\n\n{answer.strip()[-1500:]}\n" if answer.strip() else ""))
    p.write_text(body, encoding="utf-8")
    return p


def code_map(repo, max_files: int = 600) -> Path:
    """Evolve/Code map.md: every indexed file with its one-line summary, by folder (from evolve.build_index, no
    model). Agents grep this note instead of exploring; rewritten only when the index changed."""
    ix = evolve.build_index(Path(repo))
    by_dir: Dict[str, List[str]] = {}
    for path in sorted(ix.files)[:max_files]:
        e = ix.files[path]
        if e.get("summary"):
            by_dir.setdefault(str(Path(path).parent), []).append(f"- `{path}`: {e['summary'][:120]}")
    text = ("---\ntags: [evolve, code-map]\n---\n# Code map\n\nWhere things live in the SAINT/HalOS source "
            f"(`{repo}`). Generated by Evolve from the code; don't edit by hand. See also [[Lessons]].\n"
            + "".join(f"\n## {d}\n\n" + "\n".join(lines) + "\n" for d, lines in by_dir.items()))
    p = _vault() / "Code map.md"
    if not p.exists() or p.read_text(encoding="utf-8") != text:
        p.write_text(text, encoding="utf-8")
    return p


def set_status(**kw) -> Dict:
    """Merge into status.json (running, phase, request, started, result, to_test, run_note): SAINT reads it."""
    try:
        cur = json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    cur.update(kw, updated=time.time())
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps(cur), encoding="utf-8")
    except OSError:
        pass
    return cur


def status_text(now: Optional[float] = None) -> str:
    """What SAINT says for "how is Evolve doing?"."""
    try:
        s = json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Evolve hasn't run anything yet."
    req = " ".join(str(s.get("request", "")).split())[:120]
    if s.get("running"):
        mins = ((now or time.time()) - float(s.get("started") or time.time())) / 60
        return f"Evolve is working on “{req}”: {s.get('phase') or 'thinking'} ({mins:.0f} min so far)."
    out = f"Evolve finished “{req}”: {s.get('result') or 'done'}."
    tests = s.get("to_test") or []
    return out + (" To test: " + "; ".join(tests[:5]) + "." if tests else "")


if __name__ == "__main__":                       # self-check: python -m core.evolve_chat
    import os
    import tempfile
    assert quick_kind("Commit changes.") == "commit" and quick_kind("git status") == "status"
    assert quick_kind("undo that") == "undo" and quick_kind("commit the fix for the avatar and add tests") == ""
    d = Path(tempfile.mkdtemp())
    assert quick("commit", d) is None                                   # not a repository: the model's job
    evolve._git(d, "init", "-q")
    (d / "a.py").write_text("x = 1\n")
    q = quick("commit changes", d, "add a thing")
    assert q.ok and q.title == "Committed" and "add a thing" in evolve._git(d, "log", "--format=%s"), q
    assert "no changes" in quick("commit", d).text
    (d / "a.py").write_text("x = (\n")
    ok, why = verify(d)
    assert not ok and "compile failed" in why and not (d / "__pycache__").exists(), why
    assert quick("undo", d).title == "Undone" and verify(d)[0]
    r = parse_reply("Done.\nQUESTION: Which key?\n- Meta+S\n- Meta+H\nROOT: `pacman -S foo`\nTEST: press Meta+S")
    assert (r.question, r.options, r.root, r.tests) == ("Which key?", ["Meta+S", "Meta+H"], "pacman -S foo", ["press Meta+S"])
    b = parse_preflight('noise {"scope": "Small", "questions": [{"q": "Which key?", "options": ["a", "b"]}, {"q": ""}], "needs": ["x"]} tail')
    assert b["scope"] == "small" and len(b["questions"]) == 1 and b["needs"] == ["x"] and parse_preflight("nope") is None
    assert root_refused("rm -rf / ") and not root_refused("pacman -S --needed htop")
    a = argv(True, "acceptEdits", "/x", "", model="m", resume="s")
    assert "--bare" in a and a[-4:] == ["--model", "m", "--resume", "s"] and "--bare" not in argv(False, "plan", "/x", "")
    os.environ["SAINT_VAULT"] = str(d / "vault")
    assert lesson("Global shortcuts are kglobalaccel .desktop files") and not lesson("global shortcuts are kglobalaccel .desktop files")
    assert "kglobalaccel" in lessons() and "kglobalaccel" in context_for("x", d)
    p = log_run("add a thing", d, True, "compile ok", 12, "m", "ok\nTEST: open it")
    assert "- [ ] open it" in p.read_text() and "a.py" in code_map(d).read_text()
    print("ok")
