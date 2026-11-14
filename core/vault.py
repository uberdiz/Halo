"""
core/vault.py

SAINT's brain as an Obsidian vault the person can open, read and edit (Obsidian is preinstalled on HalOS):
~/Documents/SAINT Vault (SAINT_VAULT overrides it;
SAINT_VAULT_SKILLS=0 turns the skill download off). Plain markdown, so Claude Code, Obsidian and SAINT all use it.

    ensure()                 -> Path   the vault, seeded on first use (never overwrites a note the person changed),
                                       and the Obsidian agent skills installed in the background
    remember(fact, title=)   -> Path   a long-term memory fact as a note in Memory/ (chat and modules/memory call it)
    install_skills()         -> list   kepano/obsidian-skills (obsidian-markdown, obsidian-bases, json-canvas) into
                                       ~/.claude/skills, downloaded and checked; [] offline, tried again next time

Claude Code runs (Evolve, core/evolve.vault_args) get `--add-dir <vault>`, and the vault's CLAUDE.md / AGENTS.md
tell Claude how to use it.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable, Iterable, List, Optional

log = logging.getLogger("saint.vault")

GUIDE = """# SAINT Vault

This folder is SAINT's long-term memory on HalOS, kept as an Obsidian vault. You (Claude, or any agent SAINT runs)
may read every note here and add or edit notes.

- `Memory/`  one note per fact SAINT learned about the person (frontmatter: created, tags). Add facts here; update
  a note instead of writing a duplicate; never store passwords, keys or card numbers.
- `HalOS/`   what HalOS and SAINT can do, and this PC's hardware. Read these before suggesting changes to the system.
- Write Obsidian-flavoured markdown: [[wikilinks]] between related notes, YAML frontmatter, #tags. The
  obsidian-markdown, obsidian-bases and json-canvas skills (in ~/.claude/skills) describe the formats.
- Keep notes short and factual. Don't delete a note the person wrote; if something is wrong, correct it.
"""

ABOUT = """# What HalOS and SAINT can do

HalOS is an Arch Linux desktop (KDE Plasma 6, Wayland) built around SAINT, a voice and text desktop assistant.

- **SAINT** listens for its wake word, understands what you ask, and carries it out with deterministic actions
  (apps, windows, files, settings, media, Spotify, timers, search) - the AI picks the action, code runs it.
- **Memory**: facts you tell SAINT ("remember that ...") are kept in [[Memory]] notes in this vault.
- **Agent mode / Evolve**: with Claude Code signed in to your Claude account, SAINT can do multi-step tasks and
  change the desktop or its own source, always showing the change first, with undo and snapshots.
- **Local AI**: Ollama runs a local model sized to this PC (see [[This PC]]); nothing leaves the PC unless you
  pick a cloud model.
- **Apps**: Firefox, HalOS Files, Konsole, AIDE (Code), Spotify and Obsidian come with HalOS.
"""

SKILLS_REPO = "https://raw.githubusercontent.com/kepano/obsidian-skills/main/plugins/obsidian/skills/"
SKILL_FILES = {
    "obsidian-markdown": ["SKILL.md", "references/CALLOUTS.md", "references/EMBEDS.md", "references/PROPERTIES.md"],
    "obsidian-bases": ["SKILL.md", "references/FUNCTIONS_REFERENCE.md"],
    "json-canvas": ["SKILL.md", "references/EXAMPLES.md"],
}
MAX_SKILL_FILE = 256 * 1024
_skills_lock = threading.Lock()


def path() -> Path:
    return Path(os.environ.get("SAINT_VAULT") or Path.home() / "Documents" / "SAINT Vault")


def _hardware() -> str:
    try:
        from core import device_profile
        hw = device_profile.detect()
        gpu = f"{hw.gpu_name} ({hw.vram_gb:g} GB)" if hw.gpu_name else (hw.gpu_note or "none SAINT can use for AI")
        return (f"# This PC\n\n- CPU: {hw.cpu_name or 'unknown'} ({hw.cpu_threads} threads)\n- RAM: {hw.ram_gb:g} GB\n"
                f"- GPU: {gpu}\n- Free disk: {hw.disk_free_gb:g} GB\n\n_Written by SAINT on first run; edit freely._\n")
    except Exception:
        return "# This PC\n\nSAINT couldn't read the hardware yet.\n"


def _write_new(p: Path, text: str):
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def ensure(root: Optional[Path] = None, skills: bool = True) -> Path:
    """The vault, created and seeded if needed. Cheap after the first call (only checks that files exist)."""
    root = path() if root is None else Path(root)
    (root / "Memory").mkdir(parents=True, exist_ok=True)
    for name in ("CLAUDE.md", "AGENTS.md"):
        _write_new(root / name, GUIDE)
    _write_new(root / "HalOS" / "What HalOS and SAINT can do.md", ABOUT)
    if not (root / "HalOS" / "This PC.md").exists():
        _write_new(root / "HalOS" / "This PC.md", _hardware())
    if skills and os.environ.get("SAINT_VAULT_SKILLS", "1") != "0" and not skills_installed():
        threading.Thread(target=install_skills, name="vault-skills", daemon=True).start()
    return root


def claude_args() -> List[str]:
    """`--add-dir <vault>` for a Claude Code command line, so it can read and write SAINT's notes; [] if the vault
    can't be made (read-only home, ...): Claude Code still runs, just without it."""
    try:
        return ["--add-dir", str(ensure())]
    except Exception as e:
        log.warning("vault.unavailable: %s", e)
        return []


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", s)[:60].strip() or "Note"


def remember(fact: str, title: str = "", tags: Iterable[str] = ("memory",), root: Optional[Path] = None) -> Path:
    """Store one long-term fact as a markdown note in Memory/. Same title -> appended to that note, not duplicated.
    Returns the note's path."""
    fact = (fact or "").strip()
    if not fact:
        raise ValueError("nothing to remember")
    note = ensure(root, skills=False) / "Memory" / f"{_slug(title or fact)}.md"
    stamp = time.strftime("%Y-%m-%d %H:%M")
    if note.exists():
        with note.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"\n- {fact} ({stamp})\n")
    else:
        tag_list = ", ".join(t.strip().replace(" ", "-") for t in tags if t.strip())
        note.write_text(f"---\ncreated: {stamp}\ntags: [{tag_list}]\nsource: SAINT\n---\n\n- {fact}\n",
                        encoding="utf-8", newline="\n")
    return note


def skills_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def skills_installed(dest: Optional[Path] = None) -> bool:
    dest = skills_dir() if dest is None else dest
    return all((dest / name / "SKILL.md").is_file() for name in SKILL_FILES)


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SAINT"}), timeout=20) as r:
        return r.read(MAX_SKILL_FILE + 1)


def _valid(rel: str, data: bytes, name: str) -> bool:
    """A skill file is small UTF-8 text; SKILL.md starts with frontmatter naming this skill."""
    if len(data) > MAX_SKILL_FILE:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if rel == "SKILL.md":
        head = text.lstrip("﻿").split("\n---", 1)[0]
        return text.lstrip("﻿").startswith("---") and bool(
            re.search(rf"^name:\s*['\"]?{re.escape(name)}\b", head, re.M))
    return True


def install_skills(dest: Optional[Path] = None, fetch: Callable[[str], bytes] = _fetch) -> List[str]:
    """Download the Obsidian skills into ``dest`` (~/.claude/skills). A skill is written only when all its files
    downloaded and passed the check; one already there is left alone. Returns the skills installed now."""
    dest = skills_dir() if dest is None else Path(dest)
    done = []
    with _skills_lock:
        for name, files in SKILL_FILES.items():
            if (dest / name / "SKILL.md").is_file():
                continue
            try:
                got = {rel: fetch(SKILLS_REPO + f"{name}/{rel}") for rel in files}
            except Exception as e:                     # offline, GitHub down: try again on the next ensure()
                log.info("vault.skills_offline: %s: %s", name, e)
                continue
            if not all(_valid(rel, data, name) for rel, data in got.items()):
                log.warning("vault.skill_rejected: %s", name)
                continue
            for rel, data in sorted(got.items(), key=lambda kv: kv[0] == "SKILL.md"):   # SKILL.md last
                out = dest / name / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
            done.append(name)
    return done
