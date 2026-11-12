"""
core/migration_journal.py

The undo journal for "bring everything". Every change the migration makes goes through a Journal method, which does
the change and appends one JSON line saying how to reverse it. ``undo()`` walks the lines backwards.

Two rules live here so that no caller can forget them:
  * nothing is ever created, changed, moved or removed under a protected root (the old OS's partition);
  * undo only removes what the migration made and that is still as it left it (a file the user changed since stays).
"""

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from core.paths import data_path

JOURNAL_NAME = "migration_journal.jsonl"


class SourceIsReadOnly(PermissionError):
    pass


def _inside(path, root) -> bool:
    try:
        a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
        return a == b or a.startswith(b.rstrip("\\/") + os.sep)
    except (OSError, ValueError):
        return False


class Journal:
    def __init__(self, path: Optional[Path] = None, protect: Iterable = (), run_id: str = ""):
        self.path = Path(path) if path else Path(data_path(JOURNAL_NAME))
        self.protect = [str(p) for p in protect if p]
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ recording
    def guard(self, *paths) -> None:
        """Raises when any path is on the old OS. Called before every change."""
        for p in paths:
            for root in self.protect:
                if _inside(p, root):
                    raise SourceIsReadOnly(f"{p} is on the old system, which is never changed.")

    def _add(self, op: str, **fields) -> Dict:
        entry = {"run": self.run_id, "ts": time.time(), "op": op, **fields}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def mkdir(self, path) -> None:
        """Creates the missing folders one by one, so undo removes exactly those (and only if empty)."""
        self.guard(path)
        missing, cur = [], Path(path)
        while not cur.exists() and cur != cur.parent:
            missing.append(cur)
            cur = cur.parent
        for p in reversed(missing):
            p.mkdir()
            self._add("mkdir", path=str(p))

    def symlink(self, target, link, symlink: Callable = os.symlink, directory: bool = True) -> None:
        self.guard(link)
        self.mkdir(Path(link).parent)
        symlink(str(target), str(link), target_is_directory=directory)
        self._add("symlink", path=str(link), target=str(target))

    def rmdir_empty(self, path) -> None:
        """Takes an empty folder out of the way (for a link with the same name). Undo puts it back."""
        self.guard(path)
        os.rmdir(path)
        self._add("rmdir", path=str(path))

    def copy_file(self, src, dest) -> None:
        """src may be on the old OS (reading is fine); dest never is. An existing dest is never overwritten."""
        self.guard(dest)
        if os.path.lexists(dest):
            raise FileExistsError(f"{dest} is already there.")
        self.mkdir(Path(dest).parent)
        shutil.copy2(src, dest, follow_symlinks=False)
        st = os.lstat(dest)
        self._add("copy", path=str(dest), source=str(src), size=st.st_size, mtime=st.st_mtime)

    def write_text(self, path, text: str, mode: Optional[int] = None) -> None:
        """Writes a config file. The previous version is kept beside the journal and comes back on undo."""
        self.guard(path)
        path = Path(path)
        self.mkdir(path.parent)
        backup = ""
        if path.exists():
            store = self.path.parent / "migration_backups"
            store.mkdir(parents=True, exist_ok=True)
            backup = str(store / f"{uuid.uuid4().hex}-{path.name}")
            shutil.copy2(path, backup)
        tmp = path.with_name(path.name + ".halos-tmp")
        tmp.write_text(text, encoding="utf-8")
        if mode is not None:
            try:
                os.chmod(tmp, mode)
            except OSError:
                pass
        os.replace(tmp, path)
        st = os.lstat(path)
        self._add("write", path=str(path), backup=backup, size=st.st_size, mtime=st.st_mtime)

    def move(self, src, dest) -> None:
        """A move inside the new home (merging duplicates). Neither end may be on the old OS."""
        self.guard(src, dest)
        if os.path.lexists(dest):
            raise FileExistsError(f"{dest} is already there.")
        self.mkdir(Path(dest).parent)
        shutil.move(str(src), str(dest))
        self._add("move", path=str(dest), source=str(src))

    def command(self, argv: List[str], undo_argv: Optional[List[str]] = None, note: str = "",
                run: Callable = subprocess.run, stdin: Optional[str] = None, timeout: int = 300) -> bool:
        """Runs one argument list (never a shell string). Recorded only if it worked."""
        res = run(argv, capture_output=True, text=True, timeout=timeout, **({"input": stdin} if stdin is not None else {}))
        ok = getattr(res, "returncode", 1) == 0
        if ok:
            self._add("command", argv=argv, undo=undo_argv or [], note=note)
        return ok

    def note(self, what: str, **fields) -> None:
        """Something that needs no undo (a skip and its reason, a step finishing) but belongs in the report."""
        self._add("note", note=what, **fields)

    # ------------------------------------------------------------------ reading and undoing
    def entries(self, run_id: Optional[str] = None) -> List[Dict]:
        out = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if run_id is None or e.get("run") == run_id:
                        out.append(e)
        except OSError:
            pass
        return out

    def runs(self) -> List[Dict]:
        """One row per migration run that can still be undone, newest first."""
        seen: Dict[str, Dict] = {}
        undone = set()
        for e in self.entries():
            if e["op"] == "undone":
                undone.add(e["run"])
                continue
            r = seen.setdefault(e["run"], {"run": e["run"], "started": e["ts"], "changes": 0})
            r["changes"] += e["op"] != "note"
        return sorted((r for k, r in seen.items() if k not in undone and r["changes"]), key=lambda r: -r["started"])

    def undo(self, run_id: Optional[str] = None, run: Callable = subprocess.run) -> Dict:
        """Reverses one run (default: this one). {"undone": n, "kept": [(path, why)]}."""
        run_id = run_id or self.run_id
        if any(e["op"] == "undone" for e in self.entries(run_id)):
            return {"undone": 0, "kept": [], "note": "That run was already undone."}
        undone, kept = 0, []
        for e in reversed(self.entries(run_id)):
            op, path = e["op"], e.get("path", "")
            try:
                if path:
                    self.guard(path)
                if op == "symlink":
                    if os.path.islink(path) and os.readlink(path) == e["target"]:
                        os.unlink(path)
                    elif os.path.isjunction(path):
                        os.rmdir(path)
                    elif os.path.lexists(path):
                        kept.append((path, "it isn't the link the migration made any more"))
                        continue
                elif op == "mkdir":
                    if os.path.isdir(path):
                        if any(os.scandir(path)):
                            kept.append((path, "it has files in it now"))
                            continue
                        os.rmdir(path)
                elif op == "rmdir":
                    if not os.path.lexists(path):
                        os.mkdir(path)
                elif op in ("copy", "write"):
                    if os.path.lexists(path):
                        st = os.lstat(path)
                        if st.st_size != e["size"] or abs(st.st_mtime - e["mtime"]) > 2:
                            kept.append((path, "you changed it after the migration"))
                            continue
                        os.unlink(path)
                    if e.get("backup") and os.path.exists(e["backup"]):
                        shutil.move(e["backup"], path)
                elif op == "move":
                    if os.path.lexists(path) and not os.path.lexists(e["source"]):
                        self.guard(e["source"])
                        Path(e["source"]).parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(path, e["source"])
                    else:
                        kept.append((path, "it moved again, or something took its old place"))
                        continue
                elif op == "command":
                    if not e.get("undo"):
                        kept.append((" ".join(e["argv"][:3]), "this step has no automatic undo"))
                        continue
                    if getattr(run(e["undo"], capture_output=True, text=True, timeout=300), "returncode", 1) != 0:
                        kept.append((" ".join(e["undo"][:3]), "the undo command was refused"))
                        continue
                else:
                    continue
                undone += 1
            except SourceIsReadOnly as err:
                kept.append((path, str(err)))
            except OSError as err:
                kept.append((path, err.strerror or str(err)))
        self._add("undone", run=run_id, count=undone)
        return {"undone": undone, "kept": kept}
