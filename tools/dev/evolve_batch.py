#!/usr/bin/env python3
"""Run open Fix notes through Evolve's source-change pipeline on the local models, one isolated worktree each.

    .venv/bin/python tools/dev/evolve_batch.py --list               # open notes, numbered
    .venv/bin/python tools/dev/evolve_batch.py 231030 001505        # notes whose file name contains these
    .venv/bin/python tools/dev/evolve_batch.py --claude 231030      # same, on Claude instead

Per note: worktree + branch evolve/<id> -> plan -> apply -> tests (core/evolve.py). Nothing is merged: review a
branch with `git diff master evolve/<id>`, keep it with `git merge evolve/<id>`, or drop it with
`git worktree remove ... && git branch -D evolve/<id>`. Results are appended to SAINT Vault/Evolve/Local runs.md.
No snapshot (no password prompt): the worktree is the protection; nothing outside it is touched.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import evolve, fix_notes, vault  # noqa: E402
from core.config import config  # noqa: E402



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("match", nargs="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--claude", action="store_true", help="use Claude (subscription) instead of local models")
    ap.add_argument("--notify", action="store_true", help="a desktop notification per finished note")
    a = ap.parse_args()
    notes = fix_notes.open_notes()
    if a.list or not a.match:
        for n in notes:
            print(f"{n.path.stem[:15]}  {n.text.strip().splitlines()[0][:90]}")
        return 0
    picked = [n for n in notes if any(m in n.path.name for m in a.match)]
    if not picked:
        print("No open note matches.", file=sys.stderr)
        return 1
    config.set("evolve.backend", "claude" if a.claude else "local", persist=False)
    repo = evolve.default_repo() or Path(__file__).resolve().parents[2]
    ix = evolve.build_index(repo)
    log = vault.ensure() / "Evolve" / "Local runs.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    for n in picked:
        t0 = time.time()
        request = (n.text.strip() + (f"\n(Where: {n.where})" if n.where else ""))[:2000]
        ch = evolve.start_source_change(repo, request)
        ch.note(f"note {n.path.stem}")                    # Evolve › Local runs › Keep marks this note fixed
        print(f"\n=== {n.path.stem}\n    branch {ch.branch}")
        ch.meta.mkdir(parents=True, exist_ok=True)
        live = open(ch.meta / "live.log", "a", encoding="utf-8", buffering=1)   # Evolve › Local runs tails this
        say = lambda l: live.write(l.rstrip("\n") + "\n")
        try:
            say("── planning (read-only) ──")
            evolve.plan_source_change(ch, ix, on_line=say)
            evolve.approve(ch)
            say("── applying the plan ──")
            evolve.apply_source_change(ch, ix, snap=lambda *_: {"kind": None, "reason": "worktree only"},
                                       on_line=say)
            say("── testing ──")
            res = evolve.test_source_change(ch)
            verdict = "tests passed" if res["passed"] else "tests FAILED"
        except Exception as e:                        # one note failing mustn't stop the batch
            verdict = f"failed: {str(e)[:200]}"
            ch.note(verdict)
        say(f"── {verdict} ──")
        live.close()
        mins = (time.time() - t0) / 60
        files = ", ".join(evolve.changed_files(ch)) if ch.status in ("applied", "tested", "failed") else ""
        print(f"    {verdict} in {mins:.1f} min; files: {files or '-'}")
        if a.notify:
            import subprocess
            subprocess.run(["notify-send", "--app-name=Evolve", "--icon=saint", f"Evolve tried a note: {verdict}",
                            n.text.strip().splitlines()[0][:90] + "\nKeep or Drop it in Evolve › Local runs."], check=False)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} [[{n.path.stem}]] on "
                    f"{'Claude' if a.claude else 'local'}: **{verdict}** ({mins:.1f} min), branch `{ch.branch}`"
                    f"{', files: ' + files if files else ''}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
