"""
core/migrate_ai.py

The AI part of "bring everything" from a Windows profile (the old disk mounted read-only, or a Windows exporter's
folder): SAINT's history and memory of you, Claude Code's history, settings and skills, and the Claude app's MCP
servers. Copies only; nothing on the source is ever changed. Every write goes through the undo journal
(core/migration_journal.py) and nothing that already exists on HalOS is overwritten.

    import_saint(profile, journal)    SAINT's history merged by time (no duplicates); its config and memory copied
                                      only when this HalOS SAINT has none yet
    import_claude(profile, journal)   ~/.claude (projects and sessions, history, settings, CLAUDE.md, skills,
                                      agents, commands) and the Claude app's claude_desktop_config.json

Sign-in tokens are never copied (.credentials.json and the like): sign in to Claude once on HalOS.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core.migration_journal import Journal

CLAUDE_KEEP = ("projects", "history.jsonl", "settings.json", "CLAUDE.md", "skills", "agents", "commands", "plugins",
               "todos", "file-history")
SECRETS = (".credentials.json", "credentials.json", "auth.json", ".env")


def _ci(parent: Path, *parts: str) -> Optional[Path]:
    """A path under ``parent``, matching each part case-insensitively (NTFS mounted on Linux keeps case)."""
    cur = parent
    for part in parts:
        try:
            cur = next(Path(e.path) for e in os.scandir(cur) if e.name.lower() == part.lower())
        except (StopIteration, OSError):
            return None
    return cur


def _copy_tree(src: Path, dest: Path, journal: Journal, skip: Iterable[str] = SECRETS) -> Dict[str, int]:
    """Copy files that aren't there yet; returns {"copied", "kept"} (kept = already on HalOS, left alone)."""
    out = {"copied": 0, "kept": 0}
    skip = {s.lower() for s in skip}
    files = [src] if src.is_file() else [Path(r) / f for r, _d, fs in os.walk(src) for f in fs]
    for f in files:
        if f.name.lower() in skip or f.is_symlink():
            continue
        target = dest if src.is_file() else dest / f.relative_to(src)
        if os.path.lexists(target):
            out["kept"] += 1
            continue
        journal.copy_file(f, target)
        out["copied"] += 1
    return out


def merge_history(windows_lines: List[str], halos_lines: List[str]) -> List[str]:
    """Both SAINT histories in time order, each request once (same time and words = the same request)."""
    seen, merged = set(), []
    for line in halos_lines + windows_lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        key = (round(float(rec.get("ts", 0)), 1), rec.get("user", ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(rec)
    merged.sort(key=lambda r: r.get("ts", 0))
    return [json.dumps(r, ensure_ascii=False) for r in merged]


def import_saint(profile: Path, journal: Journal, data_dir: Optional[Path] = None) -> Dict:
    """SAINT on Windows keeps its data in %LOCALAPPDATA%\\SAINT."""
    if data_dir is None:
        from core.paths import data_dir as _dd
        data_dir = _dd()
    src = _ci(profile, "AppData", "Local", "SAINT")
    if src is None:
        return {"found": False, "note": "SAINT wasn't used on that Windows."}
    out: Dict = {"found": True, "history_added": 0, "copied": 0}
    old = _ci(src, "history.jsonl")
    if old is not None:
        mine = data_dir / "history.jsonl"
        theirs = old.read_text(encoding="utf-8", errors="replace").splitlines()
        current = mine.read_text(encoding="utf-8").splitlines() if mine.exists() else []
        merged = merge_history(theirs, current)
        out["history_added"] = len(merged) - len([l for l in current if l.strip()])
        journal.write_text(mine, "\n".join(merged) + "\n")
    for name in ("memory", "config.json", "learning"):
        part = _ci(src, name)
        if part is not None and not (data_dir / name).exists():
            out["copied"] += _copy_tree(part, data_dir / name, journal)["copied"]
    return out


def import_claude(profile: Path, journal: Journal, home: Optional[Path] = None) -> Dict:
    home = Path(home or Path.home())
    out: Dict = {"found": False, "copied": 0, "kept": 0, "parts": []}
    claude = _ci(profile, ".claude")
    if claude is not None:
        out["found"] = True
        for name in CLAUDE_KEEP:
            part = _ci(claude, name)
            if part is None:
                continue
            r = _copy_tree(part, home / ".claude" / name, journal)
            out["copied"] += r["copied"]
            out["kept"] += r["kept"]
            out["parts"].append(name)
    desktop = _ci(profile, "AppData", "Roaming", "Claude", "claude_desktop_config.json")
    if desktop is not None:
        out["found"] = True
        r = _copy_tree(desktop, home / ".config/Claude/claude_desktop_config.json", journal)
        out["copied"] += r["copied"]
        out["kept"] += r["kept"]
        out["parts"].append("Claude app MCP servers")
    out["note"] = ("Sign in to Claude once on HalOS: sign-in tokens aren't copied." if out["found"]
                   else "Claude wasn't used on that Windows.")
    return out
