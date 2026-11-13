"""SAINT's actions for HalOS's own apps: files.open (a folder in a new Files tab), downloads.list, taskmgr.open. Found
from plain phrases by keywords, safe (no question asked), and they start the app instead of driving it."""
import sys

import pytest

from core import actions
from core.actions import SAFE, ActionLog, execute, registry
from core.actions import executor, log as log_mod
from core.actions.sets import halos_apps


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):          # every action module: none may take its Windows path
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    spawned = []
    monkeypatch.setattr(halos_apps, "_spawn", spawned.append)
    monkeypatch.setattr(halos_apps.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    yield spawned


def test_registered_safe_and_found_from_plain_words():
    for aid in ("files.open", "downloads.list", "taskmgr.open"):
        a = registry.get(aid)
        assert a is not None and a.risk == SAFE and a.available("linux")
    assert registry.search("what's downloading")[0].id == "downloads.list"
    assert registry.search("open task manager")[0].id == "taskmgr.open"
    assert "files.open" in [a.id for a in registry.search("open my downloads folder")[:3]]


def test_files_open_a_home_folder_in_a_new_tab(setup, tmp_path, monkeypatch):
    monkeypatch.setattr(halos_apps.Path, "home", lambda: tmp_path)
    (tmp_path / "Downloads").mkdir()
    r = execute("files.open", {"path": "my downloads"}, source="saint")
    assert r.ok and "new tab" in r.text
    assert setup[-1] == ["/usr/bin/halos-files", str(tmp_path / "Downloads")]
    r = execute("files.open", {"path": str(tmp_path), "new_tab": False}, source="saint")
    assert setup[-1][-1] == "--new-window"
    assert execute("files.open", {"path": str(tmp_path / "nope")}, source="saint").code == "NOT_FOUND"


def test_downloads_list_answers_and_can_show_the_page(setup, monkeypatch):
    from core import downloads
    monkeypatch.setattr(downloads, "snapshot", lambda: [downloads.Item("Dota 2", "Steam", 50, 100)])
    r = execute("downloads.list", {}, source="saint")
    assert r.ok and r.text == "One thing is downloading: Dota 2 · 50%." and r.data["items"][0]["percent"] == 50
    assert setup == []
    execute("downloads.list", {"show": True}, source="saint")
    assert setup[-1] == ["/usr/bin/saint", "--page", "Downloads"]


def test_taskmgr_opens_on_a_page(setup):
    assert execute("taskmgr.open", {}, source="saint").ok
    assert setup[-1] == ["/usr/bin/saint-taskmgr", "--page", "Processes"]
    execute("taskmgr.open", {"page": "Performance"}, source="saint")
    assert setup[-1][-1] == "Performance"
    assert execute("taskmgr.open", {"page": "Kernel"}, source="saint").code == "INVALID_PARAMS"
