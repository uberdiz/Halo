#!/usr/bin/env python3
"""Time Evolve's local backend on one small, checkable task per model, exactly as the Evolve app runs it.

    .venv/bin/python tools/dev/evolve_bench.py gpt-oss:20b devstral-small-2:24b      # base models (built at --ctx)
    .venv/bin/python tools/dev/evolve_bench.py --task "..." --expect "regex" --file ui/x.py evolve-coder

Each model gets a throwaway git worktree, the task, and SAINT's checks afterwards. Prints seconds, turns, how much
of the model sat on the GPU (ollama ps), and PASS/FAIL. Nothing is merged; the worktrees are removed.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from core import claude_agent, evolve, evolve_chat  # noqa: E402

TASK = ("The Evolve app's window title is \"Evolve — Claude Code on HalOS\". Change it to \"Evolve — HalOS\".")
FILE, EXPECT = "ui/evolve_app.py", r'setWindowTitle\("Evolve — HalOS"\)'


def build(base: str, ctx: int) -> str:
    """An Ollama model with a context window big enough for the agent; returns its name."""
    if base.startswith("evolve-"):
        return base
    name = "evolve-bench-" + base.replace(":", "-").replace("/", "-")
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False) as f:
        f.write(f"FROM {base}\nPARAMETER num_ctx {ctx}\nPARAMETER temperature 0.2\n")
    subprocess.run(["ollama", "create", name, "-f", f.name], check=True, capture_output=True)
    return name


def run(model: str, task: str, file: str, expect: str, timeout: int, show_diff: bool = False) -> dict:
    import re
    wt = Path(tempfile.mkdtemp(prefix="evolve-bench-")) / "wt"
    evolve._git(REPO, "worktree", "add", "-q", "--detach", str(wt), "HEAD")
    env = claude_agent.local_env()
    env.update(ANTHROPIC_MODEL=model, ANTHROPIC_DEFAULT_OPUS_MODEL=model, ANTHROPIC_DEFAULT_SONNET_MODEL=model)
    argv = [claude_agent.claude_path() or "claude", *evolve_chat.argv(True, "acceptEdits", str(wt), "")]
    prompt = task + "\n\n" + evolve_chat.context_for(task, wt)
    t0, turns, steps, gpu = time.time(), 0, [], ""
    proc = subprocess.Popen(argv, cwd=str(wt), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    proc.stdin.write(evolve_chat.user_line(prompt))
    proc.stdin.flush()
    import threading
    watchdog = threading.Timer(timeout, proc.kill)       # a model that never answers must not hang the bench
    watchdog.start()
    try:
        for raw in proc.stdout:
            if time.time() - t0 > timeout:
                break
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if ev.get("type") == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    if b.get("type") == "tool_use":
                        steps.append(claude_agent.describe_tool(b.get("name", ""), b.get("input") or {}))
                if not gpu:
                    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
                    gpu = next((" ".join(l.split()[4:-4]) or l for l in ps.splitlines() if l.startswith(model)), "")
            elif ev.get("type") == "result":
                turns = ev.get("num_turns", 0)
                break
    finally:
        watchdog.cancel()
        proc.stdin.close()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
    secs = time.time() - t0
    try:
        hit = bool(re.search(expect, (wt / file).read_text(encoding="utf-8")))
    except OSError:
        hit = False
    ok, checks = evolve_chat.verify(wt)
    extra = [f for f in evolve_chat.changed(wt) if f != file]
    if show_diff:
        evolve._git(wt, "add", "-A")
        print(evolve._git(wt, "diff", "--cached")[:6000], flush=True)
    evolve._git(REPO, "worktree", "remove", "--force", str(wt), check=False)
    return {"model": model, "secs": round(secs), "turns": turns, "steps": steps, "gpu": gpu,
            "pass": hit and ok and not extra, "edit": hit, "checks": checks, "other_files": extra,
            "stderr": proc.stderr.read().decode("utf-8", "replace")[-300:] if not hit else ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--task", default=TASK)
    ap.add_argument("--file", default=FILE)
    ap.add_argument("--expect", default=EXPECT)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--diff", action="store_true", help="print what the model changed")
    a = ap.parse_args()
    for base in a.models:
        r = run(build(base, a.ctx), a.task, a.file, a.expect, a.timeout, a.diff)
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {base:24} {r['secs']:4}s  {r['turns']} turns  {len(r['steps'])} steps  "
              f"[{r['gpu']}]  {r['checks']}" + (f"  other files: {r['other_files']}" if r["other_files"] else "")
              + (f"\n      {r['stderr']}" if r["stderr"] else ""), flush=True)
        for s in r["steps"]:
            print("      ·", s[:100])
        subprocess.run(["ollama", "stop", build(base, a.ctx)], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
