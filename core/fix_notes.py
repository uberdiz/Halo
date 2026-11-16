"""
core/fix_notes.py

"Note to fix" (Halo): right-click anything in a SAINT window (or press Meta+N anywhere, or right-click a file in
Dolphin) and write what's wrong. Each note is a markdown file in the SAINT Vault under Fix/, with what was clicked
and a screenshot, so Obsidian shows them too. Evolve's "Fix my notes" hands the open ones to Claude Code.

    add(text, where="", details="", screenshot=None) -> Path
    open_notes() -> [Note]          newest first
    mark(note, status)              "open" | "done" | "dropped"
    similar(text) -> [Note]         open notes about the same thing (so you add to one instead of repeating it)
    append(note, text)              add to an existing note
    section(text) -> str            Evolve, Avatar, Shortcuts, ... (by keyword; the Notes tab and the index group by it)
    write_index() -> Path           SAINT Vault/Evolve/Fix index.md: every note by section and state, rebuilt on change
    prompt(notes) -> str            the task Claude Code gets
"""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def folder() -> Path:
    from core import vault
    d = vault.path() / "Fix"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Note:
    path: Path
    text: str
    where: str
    details: str
    status: str
    created: str
    screenshot: str


# First match wins; the words are matched as whole words in the note's text and "where".
SECTIONS = [("Evolve", "evolve agent claude prompt note notes vault obsidian llm model skills"),
            ("Avatar", "avatar outfit outfits vrm vroid walking climb"),
            ("Shortcuts", "shortcut shortcuts hotkey meta win"),
            ("Media", "spotify miniplayer player music lyrics youtube video"),
            ("Devices", "lights camera microphone bluetooth headphones"),
            ("Desktop", "window windows taskbar alt-tab boot desktop files explorer installer calamares fullscreen "
                        "screen screenshot widget notifications"),
            ("SAINT", "saint voice listening wake usage history")]
_WORD = re.compile(r"[a-z0-9+-]{3,}")
_COMMON = {"the", "and", "that", "this", "with", "should", "make", "when", "also", "like", "its", "isnt", "doesnt",
           "for", "from", "just", "have", "being", "able", "can", "you", "not", "but", "more", "what", "into", "sure"}


def _words(text: str) -> set:
    return set(_WORD.findall((text or "").lower())) - _COMMON


def section(text: str) -> str:
    words = _words(text)
    return next((name for name, keys in SECTIONS if words & set(keys.split())), "Other")


def similar(text: str, items: Optional[List["Note"]] = None, n: int = 3, least: float = 0.3) -> List["Note"]:
    """Open notes that share enough words with ``text`` (overlap over the smaller word set), best first."""
    mine = _words(text)
    if len(mine) < 2:
        return []
    scored = []
    for note in (open_notes() if items is None else items):
        theirs = _words(note.text)
        score = len(mine & theirs) / max(1, min(len(mine), len(theirs)))
        if score >= least and len(mine & theirs) >= 2:
            scored.append((-score, note.path.name, note))
    return [note for _, _, note in sorted(scored)[:n]]


def append(note: "Note", text: str):
    """Add to a note instead of writing the same thing again (the addition goes above "What was clicked")."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Write what to add.")
    raw = note.path.read_text(encoding="utf-8")
    head, sep, tail = raw.partition("\n## What was clicked")
    if not sep:
        head, sep, tail = raw.partition("\n![[")
    extra = f"\n**Added {time.strftime('%Y-%m-%d %H:%M')}:** {text}\n"
    note.path.write_text(head.rstrip("\n") + "\n" + extra + sep + tail, encoding="utf-8")
    note.text += "\n" + text


def write_index(root: Optional[Path] = None, out: Optional[Path] = None) -> Path:
    """Every note by section and state, as one vault note with links. Only written when it changed."""
    items = notes(None, root)
    by: dict = {}
    for n in items:
        by.setdefault(section(n.text + " " + n.where), []).append(n)
    mark_of = {"open": " ", "done": "x", "dropped": "-"}
    text = ("---\ntags: [fix, index]\n---\n# Fix index\n\nEvery [[Fix]] note by area. Rebuilt by SAINT whenever a note "
            f"changes; don't edit by hand. {sum(n.status == 'open' for n in items)} open of {len(items)}.\n")
    for name in [s for s, _ in SECTIONS] + ["Other"]:
        if name in by:
            text += f"\n## {name}\n\n" + "\n".join(
                f"- [{mark_of.get(n.status, ' ')}] [[{n.path.stem}|{' '.join(n.text.split())[:90]}]]" for n in by[name]) + "\n"
    out = out or (root or folder()).parent / "Evolve" / "Fix index.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8")
    return out


def _slug(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]) or "note"


def add(text: str, where: str = "", details: str = "", screenshot: Optional[str] = None,
        root: Optional[Path] = None) -> Path:
    text = (text or "").strip()
    if not text:
        raise ValueError("Write what should be fixed.")
    d = root or folder()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    p = d / f"{stamp}-{_slug(text)}.md"
    shot = ""
    if screenshot and Path(screenshot).is_file():
        (d / "shots").mkdir(exist_ok=True)
        dest = d / "shots" / f"{stamp}.png"
        shutil.move(screenshot, dest)
        shot = f"shots/{dest.name}"
    one = lambda s: " ".join(str(s).split()).replace('"', "'")[:300]
    body = (f'---\nstatus: open\ncreated: {time.strftime("%Y-%m-%d %H:%M")}\nwhere: "{one(where)}"\n'
            f'screenshot: "{shot}"\ntags: [fix]\n---\n\n{text}\n')
    if details.strip():
        body += f"\n## What was clicked\n\n```\n{details.strip()[:2000]}\n```\n"
    if shot:
        body += f"\n![[{shot}]]\n"
    p.write_text(body, encoding="utf-8")
    write_index(d)
    return p


def _parse(p: Path) -> Note:
    raw = p.read_text(encoding="utf-8", errors="replace")
    meta, body = {}, raw
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if m:
        for line in m[1].splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
        body = m[2]
    text = body.split("\n## ")[0].split("\n![[")[0].strip()
    det = re.search(r"## What was clicked\s+```\n(.*?)\n```", body, re.S)
    return Note(p, text, meta.get("where", ""), det[1] if det else "", meta.get("status", "open"),
                meta.get("created", ""), meta.get("screenshot", ""))


def notes(status: Optional[str] = "open", root: Optional[Path] = None) -> List[Note]:
    d = root or folder()
    out = [_parse(p) for p in sorted(d.glob("*.md"), reverse=True)]
    return [n for n in out if status is None or n.status == status]


def open_notes(root: Optional[Path] = None) -> List[Note]:
    return notes("open", root)


def mark(note: Note, status: str):
    raw = note.path.read_text(encoding="utf-8")
    note.path.write_text(re.sub(r"^status: \w+", f"status: {status}", raw, count=1, flags=re.M), encoding="utf-8")
    note.status = status
    write_index(note.path.parent)


def prompt(items: List[Note]) -> str:
    lines = ["Fix these problems the user noted while using HalOS/SAINT, in the SAINT source (this folder). For each "
             "note: find the cause in the code, fix it at the root, keep the change small. Screenshots are attached "
             "as file paths: read them. Don't edit the note files (they are marked done when the change is kept).", ""]
    for i, n in enumerate(items, 1):
        lines.append(f"{i}. {n.text}")
        if n.where:
            lines.append(f"   Where: {n.where}")
        if n.details:
            lines.append("   Clicked: " + " | ".join(n.details.splitlines())[:400])
        if n.screenshot:
            lines.append(f"   Screenshot: {n.path.parent / n.screenshot}")
        lines.append(f"   Note file: {n.path}")
    lines.append("\nEnd with which notes you fixed, which you couldn't, and whether SAINT needs a restart.")
    return "\n".join(lines)


if __name__ == "__main__":                       # self-check: python -m core.fix_notes
    import tempfile
    d = Path(tempfile.mkdtemp()) / "Fix"                # the index goes next to it, in <tmp>/Evolve
    d.mkdir()
    p = add("Button is cut off", where="Store › Install", details="QPushButton 'Install'", root=d)
    [n] = open_notes(d)
    assert n.text == "Button is cut off" and n.where == "Store › Install" and "QPushButton" in n.details, n
    assert "Button is cut off" in prompt([n])
    mark(n, "done")
    assert open_notes(d) == [] and notes(None, d)[0].status == "done"
    q = add("The avatar walks too fast along the taskbar", root=d)
    [n] = open_notes(d)
    assert section(n.text) == "Avatar" and section("add a shortcut like meta+s") == "Shortcuts"
    assert similar("avatar walking is too fast", [n]) == [n] and similar("the installer shows the wrong disk", [n]) == []
    append(n, "and awkward")
    assert "and awkward" in open_notes(d)[0].text
    ix = write_index(d).read_text()
    assert "## Avatar" in ix and "- [x] [[" in ix and f"[[{q.stem}|" in ix, ix
    print("ok", p.name)
