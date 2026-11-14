"""The universal downloads manager inside HalOS Files: active and finished downloads, Open / Show in folder, Cancel
for SAINT's own installs (between steps only), and a Trash entry in the sidebar."""
import os
import threading
import time
from pathlib import Path

import pytest

from core import downloads as dl


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_finished_items_newest_first_without_partials(tmp_path):
    now = time.time()
    for name, age in (("old.iso", 30 * 86400), ("new.zip", 10), ("mid.pdf", 3600), ("x.part", 1), (".hidden", 1)):
        (tmp_path / name).write_bytes(b"x" * 5)
        os.utime(tmp_path / name, (now - age, now - age))
    items = dl.finished_items([tmp_path], now=now)
    assert [i.name for i in items] == ["new.zip", "mid.pdf"]
    assert items[0].state == "finished" and items[0].path == str(tmp_path / "new.zip") and items[0].total == 5
    partial = dl.browser_items([tmp_path], now=now)
    assert partial[0].path == str(tmp_path / "x.part")


def test_cancel_reaches_a_tracker_in_another_process(tmp_path):
    with dl.Tracker("store:x", "Installing X", "SAINT Store", directory=tmp_path, every_s=0) as t:
        item = dl.reported_items(tmp_path)[0]
        assert item.cancellable and not t.cancel.is_set()
        assert dl.request_cancel("store:x", tmp_path)
        t.progress(1, 2)
        assert t.cancel.is_set()
    assert not list(tmp_path.iterdir())                        # report and cancel flag both cleaned up
    assert not dl.request_cancel("store:x", tmp_path)          # nothing running: nothing to cancel


def test_the_package_queue_stops_between_steps_when_cancelled():
    from core import pkg_queue
    stop = threading.Event()
    stop.set()
    with pytest.raises(pkg_queue.QueueError):
        pkg_queue.Gate(cancel=stop).before(type("S", (), {"argv": ["flatpak", "install", "x"]})())


def test_cards_offer_the_right_buttons(qapp, tmp_path):
    from ui.settings_pages.downloads import DownloadsPage
    shown = []
    f = tmp_path / "a.zip"
    f.write_bytes(b"x")
    page = DownloadsPage(source=lambda: [], finished=lambda: [], on_show=shown.append)
    page.show_items([dl.Item("Installing X", "SAINT Store", key="store:x", cancellable=True),
                     dl.Item("b", "Browser", 1, path=str(tmp_path / "b.part"))],
                    [dl.Item("a.zip", "Finished", 1, 1, state="finished", key="f", path=str(f))])
    store, browser, done = page.cards["store:x"], page.cards["Browser:b"], page.cards["f"]
    assert not store.cancel_btn.isHidden() and store.show_btn.isHidden()
    assert browser.cancel_btn.isHidden() and not browser.show_btn.isHidden() and browser.open_btn.isHidden()
    assert not done.open_btn.isHidden() and done.bar.isHidden() and not page.done_title.isHidden()
    done.show_btn.click()
    assert shown == [str(f)]
    page.show_items([], [])
    assert not page.cards and page.done_title.isHidden() and not page.empty.isHidden()


def test_files_sidebar_has_downloads_and_trash(qapp, tmp_path, monkeypatch):
    from core import file_index as fi
    from ui import files_app
    home = tmp_path / "home"
    (home / "Downloads").mkdir(parents=True)
    (home / "Downloads/report.pdf").write_bytes(b"%PDF")
    (home / ".local/share/Trash/files").mkdir(parents=True)
    monkeypatch.setattr(files_app.FilesWindow, "reindex", lambda self: None)
    monkeypatch.setattr(files_app, "list_drives", lambda: [])
    monkeypatch.setattr(files_app, "trash_dir", lambda: str(home / ".local/share/Trash/files"))
    from ui.settings_pages import downloads as page_mod
    monkeypatch.setattr(page_mod, "run_async", lambda fn, ok=None, err=None: ok(fn()))
    monkeypatch.setattr(dl, "snapshot", lambda: [])
    monkeypatch.setattr(dl, "finished_items", lambda: [
        dl.Item("report.pdf", "Finished", 4, 4, state="finished", key="f", path=str(home / "Downloads/report.pdf"))])
    w = files_app.FilesWindow(str(home), index=fi.FileIndex(tmp_path / "idx.sqlite"), roots=[str(home)])
    try:
        rows = {w.places.item(i).text(): w.places.item(i) for i in range(w.places.count())}
        assert "Trash" in rows and Path(rows["Trash"].data(256)).name == "files"
        w._place_clicked(rows["Downloads & installs"])
        assert w.middle.currentWidget() is w.downloads_page
        w.downloads_page.refresh()                                   # what showing the page does
        card = w.downloads_page.cards["f"]
        card.show_btn.click()                                        # opens the folder here, file selected
        assert w.middle.currentWidget() is w.tabs and Path(w.current) == (home / "Downloads").resolve()
    finally:
        w.sizes.shutdown()
        w.close()
