"""The universal download detector: browsers, Steam, packages, AI models, SAINT's answer and the Downloads page."""
import os
import time

import pytest

from core import downloads as dl


@pytest.fixture(autouse=True)
def fresh():
    dl._seen.clear()
    yield


def test_browser_partial_files_with_speed_and_paused_ones(tmp_path):
    f = tmp_path / "ubuntu.iso.crdownload"
    f.write_bytes(b"x" * 1_000_000)
    old = tmp_path / "game.zip.part"
    old.write_bytes(b"x" * 10)
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    (tmp_path / "done.pdf").write_bytes(b"x")
    now = time.time()
    first = {i.name: i for i in dl.browser_items([tmp_path], now=now)}
    assert set(first) == {"ubuntu.iso", "game.zip"} and first["ubuntu.iso"].speed == 0
    f.write_bytes(b"x" * 3_000_000)
    second = {i.name: i for i in dl.browser_items([tmp_path], now=now + 2)}
    assert second["ubuntu.iso"].speed == pytest.approx(1_000_000)
    assert second["game.zip"].state == "paused"


def test_steam_downloads_by_game_name(tmp_path):
    root = tmp_path / "Steam"
    (root / "steamapps/downloading/570/sub").mkdir(parents=True)
    (root / "steamapps/downloading/570/sub/a.vpk").write_bytes(b"x" * 500)
    (root / "steamapps/appmanifest_570.acf").write_text('"AppState"\n{\n\t"appid"\t\t"570"\n\t"name"\t\t"Dota 2"\n}\n')
    items = dl.steam_items([root], now=5.0)
    assert len(items) == 1 and items[0].name == "Dota 2" and items[0].done == 500


def test_package_tools_and_the_install_queue():
    items = dl.package_items(processes=lambda: ["explorer", "pacman", "flatpak", "pacman"], queued=lambda: 3)
    names = [i.name for i in items]
    assert names == ["Arch packages: installing or updating", "Flatpak: installing or updating", "2 more app installs queued"]
    assert dl.package_items(processes=lambda: ["ollama"], queued=lambda: 0) == []      # Ollama comes from model_pull


def test_model_pull_progress():
    running = {"running": True, "model": "llama3.1:8b", "completed": 2_450_000_000, "total": 4_900_000_000}
    item = dl.model_items(lambda: running)[0]
    assert item.percent == 50 and "llama3.1:8b" in item.name
    assert dl.model_items(lambda: {"running": False}) == []


def test_a_broken_source_is_left_out_not_fatal(tmp_path):
    items = dl.snapshot(model_items={"state": lambda: {"running": True, "model": "x", "completed": 1, "total": 2}},
                        package_items={"processes": lambda: 1 / 0},
                        browser_items={"dirs": [tmp_path]}, steam_items={"roots": []})
    assert [i.source for i in items] == ["SAINT"]


def test_summary_in_words():
    assert dl.summary([]) == "Nothing is downloading right now."
    one = dl.Item("Dota 2", "Steam", 50, 100, 2_000_000)
    assert dl.summary([one]) == "One thing is downloading: Dota 2 · 50% · 2.0 MB/s."
    two = dl.summary([one, dl.Item("ubuntu.iso", "Browser", 5_000_000)])
    assert two.startswith("2 things are downloading:") and "5 MB so far" in two


@pytest.mark.parametrize("text", ["what's downloading", "what is downloading right now", "is anything downloading",
                                  "what's updating on my pc", "show my downloads"])
def test_saint_answers_from_the_detector(text, monkeypatch):
    from modules.agent import os_intents
    monkeypatch.setattr(dl, "snapshot", lambda **kw: [dl.Item("Dota 2", "Steam", 50, 100)])
    intent = os_intents.parse_os(text)
    assert intent is not None and intent.name == "os.downloads"
    assert intent.run().text == "One thing is downloading: Dota 2 · 50%."


def test_downloads_page_shows_items_and_only_refreshes_while_open(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.settings_pages import downloads as page_mod
    monkeypatch.setattr(page_mod, "run_async", lambda fn, done, failed: done(fn()))
    page = page_mod.DownloadsPage(source=lambda: [dl.Item("Dota 2", "Steam", 50, 100), dl.Item("x.iso", "Browser", 9)])
    assert not page.timer.isActive()
    page.show()
    assert page.timer.isActive() and page.list.count() == 2 and page.empty.isHidden()
    page.hide()
    assert not page.timer.isActive()
