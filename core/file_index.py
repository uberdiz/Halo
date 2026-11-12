"""
core/file_index.py

HalOS Files' search: a local index of file and folder names (SQLite FTS5, in the app data folder) plus an intent
layer that reads what you mean, without any model call:

    "the app for claude"          -> installed apps whose name, keywords or description mention Claude
    "photos from last week"       -> images changed in the last 7 days
    "big videos"                  -> videos, largest first
    "tax pdf 2025"                -> files whose names match every word (prefixes count), PDFs only

    idx = FileIndex()                 one per process; the index file persists between runs
    idx.update(roots)                 incremental: only folders whose modification time changed are re-read
    idx.search("budget xls")          -> [Hit], best first, in a few milliseconds
    understand("photos from today")   -> Query(words, kinds, since, sort, apps): the parsed request (pure)

Hidden folders and build/cache folders are skipped. Nothing outside the given roots is read.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

KINDS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".svg", ".raw", ".dng"},
    "video": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv"},
    "audio": {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"},
    "document": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".pages", ".tex", ".epub"},
    "spreadsheet": {".xls", ".xlsx", ".ods", ".csv", ".numbers"},
    "presentation": {".ppt", ".pptx", ".odp", ".key"},
    "archive": {".zip", ".7z", ".rar", ".tar", ".gz", ".xz", ".zst", ".iso"},
    "code": {".py", ".js", ".ts", ".tsx", ".c", ".cpp", ".h", ".rs", ".go", ".java", ".cs", ".sh", ".lua", ".json", ".yaml", ".yml", ".toml"},
}
KIND_WORDS = {"photo": "image", "photos": "image", "picture": "image", "pictures": "image", "pic": "image",
              "pics": "image", "image": "image", "images": "image", "screenshot": "image", "screenshots": "image",
              "video": "video", "videos": "video", "movie": "video", "movies": "video", "clip": "video", "clips": "video",
              "song": "audio", "songs": "audio", "music": "audio", "audio": "audio", "recording": "audio",
              "document": "document", "documents": "document", "doc": "document", "docs": "document",
              "pdf": "document", "pdfs": "document", "essay": "document", "letter": "document",
              "spreadsheet": "spreadsheet", "spreadsheets": "spreadsheet", "excel": "spreadsheet", "sheet": "spreadsheet",
              "presentation": "presentation", "slides": "presentation", "powerpoint": "presentation", "deck": "presentation",
              "zip": "archive", "archive": "archive", "archives": "archive", "code": "code", "script": "code"}
EXT_WORDS = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "png": ".png", "jpg": ".jpg", "mp4": ".mp4",
             "mp3": ".mp3", "csv": ".csv", "zip": ".zip", "iso": ".iso", "txt": ".txt", "py": ".py"}
FILLER = {"the", "a", "an", "my", "me", "find", "show", "open", "where", "is", "are", "that", "which", "with", "of",
          "in", "on", "file", "files", "folder", "thing", "one", "i", "made", "saved", "called", "named", "about",
          "for", "some", "all", "from", "to", "please", "search"}
APP_WORDS = {"app", "apps", "application", "program", "programs", "tool", "editor", "game", "games"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".cache", "cache", "Cache", ".venv", "venv", "site-packages",
             "dist-packages", ".npm", ".cargo", "target", "build", "dist", ".gradle", "AppData", ".local", ".wine",
             "Trash", ".Trash", "$Recycle.Bin", "System Volume Information"}
_WORD = re.compile(r"[a-z0-9]+")


def words_of(text: str) -> List[str]:
    """Lower-case word pieces, splitting camelCase and digits ("TaxReturn2025.pdf" -> tax return 2025 pdf)."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    text = re.sub(r"([A-Za-z])(\d)|(\d)([A-Za-z])", lambda m: " ".join(g for g in m.groups() if g), text)
    return _WORD.findall(text.lower())


@dataclass
class Query:
    words: List[str] = field(default_factory=list)
    kinds: List[str] = field(default_factory=list)
    exts: List[str] = field(default_factory=list)
    since: float = 0.0
    sort: str = "best"                 # best | newest | biggest
    apps: bool = False                 # "the app for ...": look among installed apps


def understand(text: str, now: Optional[float] = None) -> Query:
    now = now or time.time()
    t = (text or "").lower()
    q = Query()
    day = 86400
    for phrase, seconds in (("today", day), ("yesterday", 2 * day), ("this week", 7 * day), ("last week", 14 * day),
                            ("this month", 31 * day), ("last month", 62 * day), ("recent", 7 * day),
                            ("this year", 366 * day)):
        if phrase in t:
            q.since = now - seconds
            t = t.replace(phrase, " ")
    for word in words_of(t):
        if word in APP_WORDS:
            q.apps = True
        elif word in KIND_WORDS and KIND_WORDS[word] not in q.kinds:
            q.kinds.append(KIND_WORDS[word])
            if word in EXT_WORDS:
                q.exts.append(EXT_WORDS[word])
        elif word in EXT_WORDS:
            q.exts.append(EXT_WORDS[word])
        elif word in ("big", "biggest", "large", "largest", "huge"):
            q.sort = "biggest"
        elif word in ("new", "newest", "latest", "last", "recently"):
            q.sort = "newest"
        elif word not in FILLER:
            q.words.append(word)
    if q.since and q.sort == "best":
        q.sort = "newest"
    return q


@dataclass
class Hit:
    kind: str                          # app | folder | file
    title: str
    path: str
    detail: str = ""
    size: int = 0
    mtime: float = 0.0


# --------------------------------------------------------------------------- installed apps
def desktop_entries(dirs: Optional[Iterable[str]] = None) -> List[Dict]:
    """Installed apps from .desktop files (Linux) or Start Menu shortcuts (Windows)."""
    if dirs is None:
        dirs = ["/usr/share/applications", "/var/lib/flatpak/exports/share/applications",
                str(Path.home() / ".local/share/applications"),
                str(Path.home() / ".local/share/flatpak/exports/share/applications")]
        if os.name == "nt":
            dirs = [os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
                    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")]
    apps = []
    for d in dirs:
        for root, _dirs, files in os.walk(d):
            for f in files:
                path = os.path.join(root, f)
                if f.endswith(".desktop"):
                    entry = _read_desktop(path)
                    if entry:
                        apps.append(entry)
                elif f.endswith(".lnk"):
                    apps.append({"name": f[:-4], "generic": "", "keywords": "", "comment": "", "path": path})
    return apps


def _read_desktop(path: str) -> Optional[Dict]:
    fields = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            section = ""
            for line in fh:
                line = line.strip()
                if line.startswith("["):
                    section = line
                elif section == "[Desktop Entry]" and "=" in line:
                    k, v = line.split("=", 1)
                    fields.setdefault(k.strip(), v.strip())
    except OSError:
        return None
    if fields.get("NoDisplay", "").lower() == "true" or fields.get("Type", "Application") != "Application":
        return None
    if not fields.get("Name"):
        return None
    return {"name": fields["Name"], "generic": fields.get("GenericName", ""), "keywords": fields.get("Keywords", ""),
            "comment": fields.get("Comment", ""), "path": path}


def match_apps(q: Query, apps: List[Dict], limit: int = 5) -> List[Hit]:
    if not q.words:
        return []
    scored = []
    for a in apps:
        name, rest = set(words_of(a["name"])), set(words_of(" ".join((a["generic"], a["keywords"], a["comment"]))))
        score = 0
        for w in q.words:
            if w in name:
                score += 3
            elif any(n.startswith(w) for n in name):
                score += 2
            elif w in rest or any(r.startswith(w) for r in rest if len(w) >= 3):
                score += 1
            else:
                score -= 2
        if score > 0:
            scored.append((-score, a["name"].lower(), a))
    scored.sort(key=lambda s: s[:2])
    return [Hit("app", a["name"], a["path"], a["generic"] or a["comment"]) for _s, _n, a in scored[:limit]]


# --------------------------------------------------------------------------- the index
class FileIndex:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            from core.paths import data_path
            path = data_path("files", "index.sqlite")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, path TEXT UNIQUE, name TEXT, folder TEXT,
                ext TEXT, kind TEXT, is_dir INTEGER, size INTEGER, mtime REAL);
            CREATE TABLE IF NOT EXISTS dirs(path TEXT PRIMARY KEY, mtime REAL);
            CREATE VIRTUAL TABLE IF NOT EXISTS names USING fts5(words, content='files', content_rowid='id',
                tokenize='unicode61');
            CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                INSERT INTO names(rowid, words) VALUES (new.id, new.name || ' ' || new.folder); END;
            CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                INSERT INTO names(names, rowid, words) VALUES ('delete', old.id, old.name || ' ' || old.folder); END;
            CREATE INDEX IF NOT EXISTS files_folder ON files(folder);
        """)
        self._apps: Optional[List[Dict]] = None

    @staticmethod
    def _kind(ext: str, is_dir: bool) -> str:
        if is_dir:
            return "folder"
        return next((k for k, exts in KINDS.items() if ext in exts), "other")

    def update(self, roots: Iterable[str], progress: Optional[Callable[[int], None]] = None) -> int:
        """Bring the index up to date; returns how many folders were re-read. Folders whose mtime didn't change are
        skipped (a folder's mtime changes when anything is added, removed or renamed in it)."""
        changed = 0
        seen_dirs = set()
        stack = [str(Path(r)) for r in roots if os.path.isdir(r)]
        with self._lock:
            known = dict(self.db.execute("SELECT path, mtime FROM dirs"))
            while stack:
                d = stack.pop()
                seen_dirs.add(d)
                try:
                    st = os.stat(d)
                    entries = list(os.scandir(d))
                except OSError:
                    continue
                subdirs = [e.path for e in entries if e.is_dir(follow_symlinks=False)
                           and not e.name.startswith(".") and e.name not in SKIP_DIRS]
                stack.extend(subdirs)
                if known.get(d) == st.st_mtime:
                    continue
                changed += 1
                self.db.execute("DELETE FROM files WHERE folder = ?", (d,))
                rows = []
                for e in entries:
                    if e.name.startswith(".") or e.is_symlink():
                        continue
                    try:
                        es = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    is_dir = e.is_dir(follow_symlinks=False)
                    if is_dir and e.name in SKIP_DIRS:
                        continue
                    ext = "" if is_dir else os.path.splitext(e.name)[1].lower()
                    rows.append((e.path, " ".join(words_of(e.name)) + " " + e.name.lower(), d, ext,
                                 self._kind(ext, is_dir), int(is_dir), 0 if is_dir else es.st_size, es.st_mtime))
                self.db.executemany("INSERT OR REPLACE INTO files(path, name, folder, ext, kind, is_dir, size, mtime) "
                                    "VALUES (?,?,?,?,?,?,?,?)", rows)
                self.db.execute("INSERT OR REPLACE INTO dirs(path, mtime) VALUES (?, ?)", (d, st.st_mtime))
                if progress:
                    progress(changed)
            gone = [p for p in known if p not in seen_dirs and any(p.startswith(str(Path(r))) for r in roots)]
            for p in gone:
                self.db.execute("DELETE FROM files WHERE folder = ?", (p,))
                self.db.execute("DELETE FROM dirs WHERE path = ?", (p,))
            self.db.commit()
        return changed

    def count(self) -> int:
        return self.db.execute("SELECT count(*) FROM files").fetchone()[0]

    def search(self, text: str, limit: int = 40, apps: Optional[List[Dict]] = None, now: Optional[float] = None) -> List[Hit]:
        q = understand(text, now)
        hits: List[Hit] = []
        if q.apps or (q.words and not (q.kinds or q.exts or q.since)):
            if apps is None:
                if self._apps is None:
                    self._apps = desktop_entries()
                apps = self._apps
            hits += match_apps(q, apps, limit=5 if q.apps else 3)
            if q.apps:
                return hits
        sql = ["SELECT path, name, ext, kind, is_dir, size, mtime FROM files"]
        args: List = []
        where = []
        if q.words:
            sql = ["SELECT f.path, f.name, f.ext, f.kind, f.is_dir, f.size, f.mtime FROM names "
                   "JOIN files f ON f.id = names.rowid"]
            where.append("names MATCH ?")
            args.append(" AND ".join(f'"{w}"*' for w in q.words))
        if q.kinds:
            where.append(f"kind IN ({','.join('?' * len(q.kinds))})")
            args += q.kinds
        if q.exts:
            where.append(f"ext IN ({','.join('?' * len(q.exts))})")
            args += q.exts
        if q.since:
            where.append("mtime >= ?")
            args.append(q.since)
        if not where:
            return hits
        sql.append("WHERE " + " AND ".join(where))
        order = {"newest": "mtime DESC", "biggest": "size DESC"}.get(q.sort, "bm25(names), mtime DESC" if q.words else "mtime DESC")
        sql.append(f"ORDER BY {order} LIMIT ?")
        args.append(int(limit))
        with self._lock:
            rows = self.db.execute(" ".join(sql), args).fetchall()
        for path, _name, ext, kind, is_dir, size, mtime in rows:
            title = os.path.basename(path)
            hits.append(Hit("folder" if is_dir else "file", title, path, os.path.dirname(path), size, mtime))
        return hits
