"""Downloads, live: ETA, smoothed speed, flatpak/pacman progress lines, reports from SAINT's own installers (the Store,
Flathub, the Visual Shop), rare deduplicated toasts, and the Downloads page's progress cards."""
import os

import pytest

from core import downloads as dl


@pytest.fixture(autouse=True)
def fresh():
    dl._seen.clear()
    yield


def test_eta_from_speed_or_from_the_tool():
    item = dl.Item("ubuntu.iso", "Browser", 1_000_000_000, 4_000_000_000, 10_000_000)
    assert item.eta == pytest.approx(300) and "about 5 min left" in item.text()
    assert dl.Item("x", "Steam", 0, 0, 5e6).eta is None                       # size unknown: no guess
    assert dl.Item("x", "Steam", 1, 2, 5e6, state="paused").eta is None
    assert dl.Item("x", "Flathub", pct=40, eta_s=75).eta == 75
    assert [dl.fmt_eta(s) for s in (None, 3, 30, 90, 3600, 5400)] == [
        "", "", "under a minute left", "about 2 min left", "about 1 h left", "about 1 h 30 min left"]


def test_speed_is_smoothed_so_the_eta_doesnt_jump():
    assert dl._speed("k", 0, 0.0) == 0.0
    assert dl._speed("k", 1000, 1.0) == pytest.approx(1000)
    assert dl._speed("k", 4000, 2.0) == pytest.approx(0.4 * 3000 + 0.6 * 1000)


@pytest.mark.parametrize("line,pct,speed,eta", [
    ("Installing 2/3… ████████▌            43%  2.4 MB/s  00:12", 43, 2.4e6, 12),
    (" firefox-132.0-1-x86_64   65.2 MiB  10.1 MiB/s 00:03 [######-------]  54%", 54, 10.1 * 2 ** 20, 3),
    ("Downloading org.gimp.GIMP 100%  1:02:03", 100, 0.0, 3723),
])
def test_progress_lines_from_flatpak_and_pacman(line, pct, speed, eta):
    p = dl.parse_progress(line)
    assert p["pct"] == pct and p["speed"] == pytest.approx(speed) and p["eta_s"] == eta


def test_no_progress_in_a_plain_line():
    assert dl.parse_progress("Looking for matches…") is None


def test_tracker_reports_reach_other_processes_and_vanish_when_done(tmp_path):
    clock = [1000.0]
    t = dl.Tracker("store:org.gimp.GIMP", "Installing GIMP", "Flathub", directory=tmp_path, clock=lambda: clock[0])
    with t:
        t.line("Installing 1/1… ████  43%  2.4 MB/s  00:12")
        items = dl.reported_items(tmp_path, now=clock[0])
        assert len(items) == 1 and items[0].percent == 43 and items[0].eta == 12 and items[0].source == "Flathub"
        clock[0] += 0.1
        t.line("Installing 1/1… █████  50%  2.4 MB/s  00:10")               # throttled: not written yet
        assert dl.reported_items(tmp_path, now=clock[0])[0].percent == 43
    assert dl.reported_items(tmp_path, now=clock[0]) == []
    dead = dl.Tracker("k", "Dead install", "SAINT Store", directory=tmp_path, clock=lambda: 0.0)
    dead.progress(10, 100)
    dead._write(force=True)
    assert dl.reported_items(tmp_path, now=dl.REPORT_TTL_S + 1) == [] and not list(tmp_path.glob("*.json"))
    crashed = tmp_path / "crashed.json"                             # its process is gone: cleaned up at once
    crashed.write_text('{"key": "c", "name": "c", "at": 5, "pid": 999999999}')
    assert dl.reported_items(tmp_path, now=6) == [] and not crashed.exists()


def test_store_report_replaces_the_bare_package_row(tmp_path):
    dl.Tracker("store:x", "Installing GIMP", "Flathub", directory=tmp_path)._write(force=True)
    items = dl.snapshot(model_items={"state": lambda: {}}, reported_items={"directory": tmp_path},
                        package_items={"processes": lambda: ["flatpak"], "queued": lambda: 0},
                        browser_items={"dirs": []}, steam_items={"roots": []})
    assert [i.name for i in items] == ["Installing GIMP"]


def test_toasts_are_rare_and_deduplicated():
    n = dl.Notifier()
    iso = dl.Item("ubuntu.iso", "Browser", 1, 10)
    blip = dl.Item("tiny.zip", "Browser", 1, 10)
    assert n.changes([iso, blip], now=0) == []                   # just appeared: not yet
    assert n.changes([iso], now=5) == []                         # tiny.zip came and went quickly: never mentioned
    assert n.changes([iso], now=15) == [("Downloading", iso.text())]
    assert n.changes([iso], now=40) == [] and n.changes([iso], now=700) == []   # said once while it runs
    assert n.changes([], now=720) == [("Download finished", "ubuntu.iso")]
    a, b = dl.Item("a.iso", "Browser"), dl.Item("b.iso", "Browser")
    n.changes([a, b], now=800)
    assert n.changes([a, b], now=815)[0][0] == "2 downloads started"           # a burst is one toast
    assert n.changes([], now=820) == []                                       # 20 s apart at most…
    assert n.changes([], now=840) == [("2 downloads finished", "a.iso, b.iso")]   # …held, not lost


def test_downloads_page_updates_cards_in_place():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.settings_pages import downloads as page_mod
    page = page_mod.DownloadsPage(source=lambda: [])
    page.show_items([dl.Item("Dota 2", "Steam", 50, 100, 1.0)])
    card = page.cards["Steam:Dota 2"]
    page.show_items([dl.Item("Dota 2", "Steam", 60, 100, 10.0), dl.Item("x.iso", "Browser", 9)])
    assert page.cards["Steam:Dota 2"] is card and card.pct.text() == "60%" and page.list.count() == 2
    page.show_items([])
    assert page.cards == {} and not page.empty.isHidden()
