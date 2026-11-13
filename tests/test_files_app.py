"""HalOS Files: browses, searches in plain words, previews, and changes files only through the OS actions (logged,
undoable). Installed as the default for folders."""
import os
import sys
from pathlib import Path

import pytest

from core import actions
from core import file_index as fi
from core.actions import ActionLog, executor, log as log_mod

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def window(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    home = tmp_path / "home"
    (home / "Documents").mkdir(parents=True)
    (home / "Documents/TaxReturn2025.pdf").write_bytes(b"%PDF")
    (home / "Documents/notes.txt").write_text("remember the milk")
    idx = fi.FileIndex(tmp_path / "idx.sqlite")
    idx.update([str(home)])
    from ui import files_app
    monkeypatch.setattr(files_app.FilesWindow, "reindex", lambda self: None)
    monkeypatch.setattr(fi, "desktop_entries", lambda dirs=None: [])
    w = files_app.FilesWindow(str(home), index=idx, roots=[str(home)], confirm=lambda r: True)
    w.home = home
    yield w
    w.close()


def test_search_shows_results_and_clearing_goes_back_to_the_folder(window):
    window.search.setText("tax return")
    window.run_search()
    assert window.middle.currentWidget() is window.results
    hit = window.results.item(0).data(256)
    assert hit.title == "TaxReturn2025.pdf" and "results in" in window.status.text()
    window.search.setText("")
    window.run_search()
    assert window.middle.currentWidget() is window.tabs and window.tree.isVisibleTo(window.tabs)


def test_preview_shows_text_and_details(window):
    window.preview(str(window.home / "Documents/notes.txt"))
    assert "remember the milk" in window.thumb.text() and "notes.txt" in window.info.text()


def test_changes_go_through_the_actions_and_can_be_undone(window, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    window.open_folder(str(window.home / "Documents"))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Receipts", True))
    window.new_folder()
    assert (window.home / "Documents/Receipts").is_dir() and "Ctrl+Z" in window.status.text()
    window.undo()
    assert not (window.home / "Documents/Receipts").exists()
    entry = log_mod.action_log.entries()[0]
    assert entry["action"] == "files.new_folder" and entry["source"] == "gui"


def test_installed_as_the_default_for_folders():
    desktop = (ROOT / "packaging/linux/rootfs/usr/share/applications/halos-files.desktop").read_text(encoding="utf-8")
    assert "Exec=/usr/bin/halos-files %U" in desktop and "MimeType=inode/directory;" in desktop
    mime = (ROOT / "packaging/linux/rootfs/etc/xdg/mimeapps.list").read_text(encoding="utf-8")
    assert "inode/directory=halos-files.desktop" in mime
    pkg = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert "halos-files" in pkg and '"$fs/etc/xdg/mimeapps.list"' in pkg
