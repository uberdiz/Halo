"""HalOS Files' search: a fast local index and plain-words intent ("the app for claude", "photos from last week")."""
import os
import time

import pytest

from core import file_index as fi

NOW = 1_800_000_000.0
APPS = [{"name": "Claude Code", "generic": "AI coding agent", "keywords": "anthropic;ai;terminal;", "comment": "", "path": "/a/claude.desktop"},
        {"name": "AIDE", "generic": "Code", "keywords": "code;editor;ide;vscode;claude;ai;", "comment": "Write code with Claude Code", "path": "/a/aide.desktop"},
        {"name": "Firefox", "generic": "Web Browser", "keywords": "internet;www;", "comment": "", "path": "/a/firefox.desktop"},
        {"name": "Steam", "generic": "Games", "keywords": "games;valve;", "comment": "", "path": "/a/steam.desktop"}]


def test_understanding_plain_words():
    q = fi.understand("photos from last week", now=NOW)
    assert q.kinds == ["image"] and q.since == NOW - 14 * 86400 and q.sort == "newest" and q.words == []
    q = fi.understand("the app for claude")
    assert q.apps and q.words == ["claude"]
    q = fi.understand("big videos")
    assert q.kinds == ["video"] and q.sort == "biggest"
    q = fi.understand("tax return pdf 2025")
    assert q.words == ["tax", "return", "2025"] and q.exts == [".pdf"] and q.kinds == ["document"]
    assert fi.words_of("TaxReturn2025_final.PDF") == ["tax", "return", "2025", "final", "pdf"]


def test_the_app_for_claude_finds_claude_code_and_aide():
    hits = fi.match_apps(fi.understand("the app for claude"), APPS)
    assert [h.title for h in hits] == ["Claude Code", "AIDE"] and all(h.kind == "app" for h in hits)
    assert fi.match_apps(fi.understand("the web browser"), APPS)[0].title == "Firefox"


def _tree(root):
    files = {"Documents/Taxes/TaxReturn2025.pdf": 50_000, "Documents/Taxes/notes.txt": 100,
             "Documents/Budget 2025.xlsx": 9_000, "Pictures/beach.jpg": 2_000_000, "Pictures/old/cat.png": 300_000,
             "Videos/holiday.mp4": 900_000_000, "Videos/clip.mov": 10_000_000, ".hidden/secret.pdf": 1,
             "code/node_modules/lib/index.js": 1}
    for rel, size in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            f.truncate(size)
    old = root / "Pictures/old/cat.png"
    os.utime(old, (NOW - 400 * 86400, NOW - 400 * 86400))
    os.utime(root / "Pictures/beach.jpg", (NOW - 86400, NOW - 86400))
    return root


@pytest.fixture
def index(tmp_path):
    root = _tree(tmp_path / "home")
    idx = fi.FileIndex(tmp_path / "index.sqlite")
    idx.update([str(root)])
    return idx, root


def test_index_skips_hidden_and_build_folders(index):
    idx, _root = index
    paths = [r[0] for r in idx.db.execute("SELECT path FROM files")]
    assert not any(".hidden" in p or "node_modules" in p for p in paths)


def test_searches(index):
    idx, root = index
    titles = lambda text: [h.title for h in idx.search(text, apps=[], now=NOW)]
    assert titles("tax return") == ["TaxReturn2025.pdf"]
    assert titles("taxes") == ["Taxes", "TaxReturn2025.pdf", "notes.txt"] or titles("taxes")[0] == "Taxes"
    assert titles("budget xlsx") == ["Budget 2025.xlsx"]
    assert titles("photos from this week") == ["beach.jpg"]
    assert titles("big videos") == ["holiday.mp4", "clip.mov"]
    assert titles("2025") [0] in ("TaxReturn2025.pdf", "Budget 2025.xlsx")


def test_updates_are_incremental_and_see_renames(index):
    idx, root = index
    assert idx.update([str(root)]) == 0                         # nothing changed: nothing re-read
    (root / "Documents/Taxes/notes.txt").rename(root / "Documents/Taxes/receipts.txt")
    assert idx.update([str(root)]) == 1
    assert [h.title for h in idx.search("receipts", apps=[])] == ["receipts.txt"]
    assert idx.search("notes", apps=[]) == []


def test_search_is_fast_on_a_big_home(tmp_path):
    root = tmp_path / "big"
    for d in range(200):
        folder = root / f"project{d}"
        folder.mkdir(parents=True)
        for i in range(100):
            (folder / f"file{i}_report_{d}.txt").write_bytes(b"")
    idx = fi.FileIndex(tmp_path / "big.sqlite")
    idx.update([str(root)])
    assert idx.count() >= 20_000
    start = time.perf_counter()
    for _ in range(20):
        hits = idx.search("report 150", apps=[])
    per = (time.perf_counter() - start) / 20
    assert hits and per < 0.1, f"{per * 1000:.1f} ms per search"
