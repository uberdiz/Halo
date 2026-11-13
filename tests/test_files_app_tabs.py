"""HalOS Files, Explorer-style: breadcrumbs and typed paths, folder sizes off the GUI thread with a cache, recent
files, drives in the sidebar, tabs with their own history, and drops that go through the file actions."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import actions
from core import file_index as fi
from core.actions import ActionLog, executor, log as log_mod


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_breadcrumbs_from_home_or_the_root(tmp_path):
    from ui.files_app import breadcrumbs
    home = tmp_path / "home"
    crumbs = breadcrumbs(str(home / "Documents" / "Tax"), home=str(home))
    assert [c[0] for c in crumbs] == ["Home", "Documents", "Tax"]
    assert crumbs[-1][1] == str(home / "Documents" / "Tax")
    outside = breadcrumbs(str(tmp_path / "x"), home=str(home))
    assert outside[0][1] == Path(str(tmp_path)).anchor and outside[-1] == ("x", str(tmp_path / "x"))


def test_typed_locations(tmp_path, monkeypatch):
    from ui.files_app import parse_location
    (tmp_path / "Docs").mkdir()
    (tmp_path / "Docs/a.txt").write_text("x")
    monkeypatch.setenv("HALO_T", str(tmp_path))
    assert parse_location("Docs", str(tmp_path)) == (str((tmp_path / "Docs").resolve()), None)
    assert parse_location("$HALO_T/Docs/a.txt", "/") == (str((tmp_path / "Docs").resolve()),
                                                         str((tmp_path / "Docs/a.txt").resolve()))
    assert parse_location((tmp_path / "Docs").resolve().as_uri(), "/")[0] == str((tmp_path / "Docs").resolve())
    assert parse_location("nope/not-here", str(tmp_path)) == (None, None)
    assert parse_location("   ", str(tmp_path)) == (None, None)


def test_recent_files_newest_first_existing_only(tmp_path):
    from ui.files_app import recent_files
    a, b = tmp_path / "a b.pdf", tmp_path / "b.txt"
    a.write_text("x")
    b.write_text("x")
    xbel = tmp_path / "recently-used.xbel"
    xbel.write_text(f"""<?xml version="1.0"?><xbel version="1.0">
      <bookmark href="{a.as_uri()}" modified="2026-11-10T10:00:00Z"/>
      <bookmark href="{b.as_uri()}" modified="2026-11-12T10:00:00Z"/>
      <bookmark href="{(tmp_path / 'gone.txt').as_uri()}" modified="2026-11-13T10:00:00Z"/>
      <bookmark href="https://example.org/" modified="2026-11-13T11:00:00Z"/></xbel>""")
    assert [Path(p).name for p in recent_files(str(xbel))] == ["b.txt", "a b.pdf"]
    assert recent_files(str(tmp_path / "missing.xbel")) == []


def test_folder_size_counts_everything_below(tmp_path):
    from ui.files_app import folder_size
    (tmp_path / "a/b").mkdir(parents=True)
    (tmp_path / "a/one").write_bytes(b"x" * 100)
    (tmp_path / "a/b/two").write_bytes(b"x" * 50)
    assert folder_size(str(tmp_path)) == 150


def test_folder_sizes_cached_and_never_on_the_gui_thread(qapp, tmp_path):
    import threading
    from ui.files_app import FolderSizes
    calls = []

    def walk(path, stop):
        calls.append(threading.current_thread() is threading.main_thread())
        return 4242
    sizes = FolderSizes(walk=walk)
    got = []
    sizes.ready.connect(lambda p, n: got.append((p, n)))
    assert sizes.get(str(tmp_path)) is None                   # answered at once, worked out in the background
    assert sizes.get(str(tmp_path)) is None and len(sizes.pending) == 1   # asked twice, walked once
    sizes.pool.waitForDone(3000)
    qapp.processEvents()
    assert got == [(str(tmp_path), 4242)] and calls == [False]
    assert sizes.get(str(tmp_path)) == 4242 and len(calls) == 1          # from the cache
    (tmp_path / "new").write_text("x")                                     # the folder changed: walk again,
    os.utime(tmp_path, (1, 1))
    assert sizes.get(str(tmp_path)) == 4242                                # showing the old size meanwhile
    sizes.pool.waitForDone(3000)
    qapp.processEvents()
    assert len(calls) == 2
    assert sizes.get("/proc") is None and len(calls) == 2                 # virtual filesystems aren't walked


def test_drive_entries_skip_system_partitions():
    from core import drives
    from ui.files_app import drive_entries
    vols = [drives.Volume("/dev/sda1", is_esp=True, fstype="vfat"),
            drives.Volume("/dev/sda2", mountpoint="/", size=100, free=40, fstype="ext4"),
            drives.Volume("/dev/sdb1", label="USB", removable=True, size=8, fstype="exfat"),
            drives.Volume("/dev/sdc1", fstype="BitLocker", size=10)]
    out = drive_entries(vols)
    assert [e["label"] for e in out] == ["HalOS (this drive)", "USB", "sdc1"]
    assert out[0]["free"] == 40 and out[1]["free"] is None and out[1]["icon"] == "drive-removable-media-usb"
    assert out[2]["locked"]


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    home = tmp_path / "home"
    for d in ("Documents", "Downloads"):
        (home / d).mkdir(parents=True)
    (home / "Downloads/report.pdf").write_bytes(b"%PDF")
    from ui import files_app
    monkeypatch.setattr(files_app.FilesWindow, "reindex", lambda self: None)
    monkeypatch.setattr(files_app, "list_drives", lambda: [])
    w = files_app.FilesWindow(str(home), index=fi.FileIndex(tmp_path / "idx.sqlite"), roots=[str(home)],
                              confirm=lambda r: True)
    w.home = home
    yield w
    w.sizes.shutdown()
    w.close()


def test_tabs_have_their_own_history(window):
    home = window.home
    window.open_folder(str(home / "Documents"))
    window.new_tab(str(home / "Downloads"))
    assert window.tabs.count() == 2 and window.current == str(home / "Downloads")
    assert window.tabs.tabText(1) == "Downloads" and window.pathbar.path == str(home / "Downloads")
    window._cycle(1)
    assert window.current == str(home / "Documents")
    window.tab().back()
    assert window.current == str(home)
    window.tab().forward()
    assert window.current == str(home / "Documents")
    window.tab().up()
    assert window.current == str(home) and window.tab().history[-1] == str(home / "Documents")
    window.close_tab(window.tabs.currentIndex())
    assert window.tabs.count() == 1 and window.current == str(home / "Downloads")


def test_views_and_typed_path(window):
    from PySide6.QtWidgets import QListView
    window.set_view(2)
    assert window.tab().view() is window.tab().items and window.tab().items.viewMode() == QListView.IconMode
    window.new_tab()
    assert window.tab().mode == 2                               # a new tab keeps the view you chose
    window.set_view(0)
    window.go_to(str(window.home / "Downloads" / "report.pdf"))
    assert window.current == str((window.home / "Downloads").resolve())
    assert window.selected().endswith("report.pdf")
    window.go_to("no/such/place")
    assert "Couldn't find" in window.status.text()


def test_drop_moves_through_the_actions_and_can_be_undone(window):
    src = window.home / "Downloads/report.pdf"
    moved = window.drop([str(src)], str(window.home / "Documents"))
    assert moved == 1 and (window.home / "Documents/report.pdf").exists() and not src.exists()
    assert log_mod.action_log.entries()[0]["action"] == "files.move"
    assert window.drop([str(window.home / "Documents/report.pdf")], str(window.home / "Documents")) == 0
    window.undo()
    assert src.exists()


def test_open_command_from_a_second_launch_opens_a_tab(window):
    window.handle_command(f"open:{window.home / 'Documents'}")
    assert window.tabs.count() == 2 and window.current == str((window.home / "Documents").resolve())


def test_recent_view_and_sidebar_drives(window):
    window.show_recent([str(window.home / "Downloads/report.pdf")])
    assert window.middle.currentWidget() is window.results and window.results.item(0).data(256).title == "report.pdf"
    window.show_drives([{"label": "USB", "path": "", "size": 8, "free": None, "icon": "drive-removable-media-usb",
                         "volume": SimpleNamespace(), "locked": False}])
    item = window.places.item(window.places.count() - 1)
    assert "Not mounted" in item.text() and item.data(256) is None
