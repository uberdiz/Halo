"""
core/evolve_idle.py

Evolve works on one small open Fix note while the PC is idle (config evolve.idle_work, on by default; Settings can
turn it off). SAINT's app calls tick() every few minutes; when everything below holds it starts
tools/dev/evolve_batch.py for one note: an isolated git worktree on the local models, nothing merged. You get a
notification when it's done and decide in Evolve › Local runs (Keep or Drop).

    pick(notes, tried)       the shortest open note not tried yet that doesn't need you first (no model)
    should_run(...)          idle long enough, no game, nothing else running in Evolve, not more than one per GAP
    tick(idle_s)             start the batch when should_run; returns the note's stem or ""
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from core import evolve

STATE = evolve.ROOT / "idle.json"
IDLE_S = 300.0                  # nothing typed or moved for this long
GAP_S = 2 * 3600.0              # at most one background job per two hours
MAX_CHARS = 400                 # longer notes are bigger jobs: yours to start
NEEDS_YOU = ("Devices",)        # sections that need answers from you first (lights, camera, ...)


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def pick(notes: List, tried: List[str]) -> Optional[object]:
    from core import fix_notes
    ok = [n for n in notes if n.path.stem not in tried and len(n.text) <= MAX_CHARS
          and fix_notes.section(n.text + " " + n.where) not in NEEDS_YOU]
    return min(ok, key=lambda n: len(n.text)) if ok else None


def should_run(idle_s: float, last_run: float, gaming: bool, evolve_busy: bool, enabled: bool, now: float) -> bool:
    return enabled and not gaming and not evolve_busy and idle_s >= IDLE_S and now - last_run >= GAP_S


def tick(idle_s: float, popen=subprocess.Popen, now: Optional[float] = None) -> str:
    now = time.time() if now is None else now
    st = _state()
    try:
        from core import claude_agent, evolve_chat, fix_notes
        from core.config import config
        from core.game_mode import game_mode
        enabled = bool(config.get("evolve.idle_work", True))
        gaming = bool(getattr(game_mode, "active", False) or getattr(game_mode, "running", False))
        busy = bool(json.loads(evolve_chat.STATUS.read_text(encoding="utf-8")).get("running")) \
            if evolve_chat.STATUS.exists() else False
        if not should_run(idle_s, float(st.get("last", 0)), gaming, busy, enabled, now):
            return ""
        repo = evolve.default_repo()
        note = pick(fix_notes.open_notes(), st.get("tried", []))
        if repo is None or note is None or claude_agent.local_status():
            return ""
    except Exception:                       # a missing vault or config must never disturb SAINT
        return ""
    st = {"last": now, "tried": [*st.get("tried", []), note.path.stem][-200:]}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st), encoding="utf-8")
    python = repo / ".venv" / "bin" / "python"
    popen([str(python) if python.is_file() else sys.executable, "tools/dev/evolve_batch.py", "--notify", note.path.stem],
          cwd=str(repo), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
          start_new_session=True)
    return note.path.stem


if __name__ == "__main__":                       # self-check: python -m core.evolve_idle
    from types import SimpleNamespace as N
    notes = [N(path=Path("a.md"), text="x" * 50, where=""), N(path=Path("b.md"), text="add a shortcut", where=""),
             N(path=Path("c.md"), text="lights", where=""), N(path=Path("d.md"), text="y" * 900, where="")]
    assert pick(notes, []).path.stem == "b" and pick(notes, ["b"]).path.stem == "a" and pick(notes, ["a", "b"]) is None
    assert should_run(600, 0, False, False, True, 10 ** 9)
    assert not should_run(60, 0, False, False, True, 10 ** 9) and not should_run(600, 0, True, False, True, 10 ** 9)
    assert not should_run(600, 10 ** 9 - 60, False, False, True, 10 ** 9) and not should_run(600, 0, False, True, True, 10 ** 9)
    print("ok")
