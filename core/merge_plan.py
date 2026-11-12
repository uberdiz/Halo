"""
core/merge_plan.py

When the old Windows folders and the new HalOS ones are brought together, some files exist on both sides. This
finds them, deterministically (size, then content hash; no model), and proposes what to do; nothing moves until
you approve the proposal, and then only through the undo journal (core/migration_journal.py):

    same       identical content on both sides  -> keep one: the HalOS copy moves to "Duplicates" (never deleted)
    conflict   same name, different content     -> keep both: the Windows copy comes over as "name (Windows).ext"
    only_old   only on Windows                  -> nothing to merge (linking or copying handles it)

    plan = propose(windows_documents, halos_documents)    # -> Proposal
    apply(plan, journal, approved=plan.items)             # only the items you ticked
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core.migration_journal import Journal

CHUNK = 1 << 20


@dataclass
class Item:
    kind: str                  # same | conflict
    rel: str                   # path relative to both folders
    old: str
    new: str
    size: int
    action: str                # what apply() will do, in words


@dataclass
class Proposal:
    items: List[Item] = field(default_factory=list)
    bytes_same: int = 0
    scanned: int = 0

    def summary(self) -> str:
        same = sum(i.kind == "same" for i in self.items)
        conflict = len(self.items) - same
        return (f"{same} files are on both sides already ({self.bytes_same / 1e9:.1f} GB could be freed); "
                f"{conflict} have the same name but different content and would both be kept.")


def digest(path: Path, quick: bool = False) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if quick:
            h.update(f.read(64 * 1024))
            size = os.fstat(f.fileno()).st_size
            if size > 128 * 1024:
                f.seek(-64 * 1024, os.SEEK_END)
                h.update(f.read())
        else:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                h.update(chunk)
    return h.hexdigest()


def _files(root: Path) -> Dict[str, Path]:
    out = {}
    for dirpath, dirnames, files in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in files:
            p = Path(dirpath) / f
            if not p.is_symlink() and not f.startswith("."):
                out[p.relative_to(root).as_posix().lower()] = p
    return out


def propose(old_root, new_root) -> Proposal:
    old_root, new_root = Path(old_root), Path(new_root)
    old, new = _files(old_root), _files(new_root)
    plan = Proposal(scanned=len(old) + len(new))
    for key in sorted(old.keys() & new.keys()):
        a, b = old[key], new[key]
        sa, sb = a.stat().st_size, b.stat().st_size
        same = sa == sb and digest(a, quick=True) == digest(b, quick=True) and digest(a) == digest(b)
        rel = a.relative_to(old_root).as_posix()
        if same:
            plan.items.append(Item("same", rel, str(a), str(b), sb, "Keep one: the HalOS copy moves to Duplicates"))
            plan.bytes_same += sb
        else:
            plan.items.append(Item("conflict", rel, str(a), str(b), sa,
                                   "Keep both: the Windows one comes over with \"(Windows)\" in its name"))
    return plan


def apply(plan: Proposal, journal: Journal, approved: Iterable[Item], duplicates: Optional[Path] = None) -> Dict[str, int]:
    """Carry out only the approved items, through the journal (undoable; the Windows side is never written)."""
    done = {"same": 0, "conflict": 0}
    for item in approved:
        if item not in plan.items:
            continue
        new = Path(item.new)
        if item.kind == "same":
            dup_root = duplicates or new.parents[len(Path(item.rel).parts) - 1].parent / "Duplicates"
            journal.move(new, dup_root / item.rel)
        else:
            stem, ext = os.path.splitext(new.name)
            journal.copy_file(item.old, new.with_name(f"{stem} (Windows){ext}"))
        done[item.kind] += 1
    return done
