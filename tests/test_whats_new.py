"""The What's new tour: data/whats_new.json is valid and every "Try it" target exists, it shows once per version,
Skip closes it (and still counts as seen), cards step forward and back, and "what's new" finds the action."""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core import actions
from core.actions import ActionLog, executor, log as log_mod, registry
from core.actions.sets import halos_apps
from ui import whats_new

app = QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    store = {}
    monkeypatch.setattr(whats_new.config, "get", lambda k, d=None: store.get(k, d))
    monkeypatch.setattr(whats_new.config, "set", lambda k, v, persist=True: store.__setitem__(k, v))
    spawned = []
    monkeypatch.setattr(halos_apps, "_spawn", spawned.append)
    monkeypatch.setattr(halos_apps.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(whats_new.motion, "enabled", lambda: False)
    return store, spawned


def test_every_try_target_exists():
    from ui import saintos_center as sc, settings_pages
    data = whats_new.load()
    assert data["version"] and len(data["cards"]) >= 10
    pages = {n for n, _ in sc.rail_rows(settings_pages.discover(), os_pages=True)}
    pages |= {"Overview", "Activity", "Tasks", "Music", "Devices", "Memory", "Automations", "History", "Storage",
              "System", "Agent"}
    for card in data["cards"]:
        assert card["title"] and card["body"] and card.get("try"), card
        t = card["try"]
        if "page" in t:
            assert t["page"] in pages, t
        else:
            a = registry.get(t["action"])
            assert a is not None and a.available("linux"), t
            a.validate(t.get("params") or {})


def test_shown_once_per_version(env, tmp_path, monkeypatch):
    store, _ = env
    data = whats_new.load()
    assert whats_new.should_show(data)
    dlg = whats_new.show(only_if_new=True)
    assert dlg is not None and store[whats_new.SEEN_KEY] == data["version"]
    dlg.reject()
    assert whats_new.show(only_if_new=True) is None             # same version: not again after login
    assert whats_new.show() is not None                         # but the tray / Ctrl+K / voice always open it
    store[whats_new.SEEN_KEY] = "0.9"
    assert whats_new.should_show(data)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert whats_new.load(str(bad)) == {} and not whats_new.should_show({})


def test_skip_next_back_and_try(env):
    store, spawned = env
    opened = []
    data = whats_new.load()
    dlg = whats_new.WhatsNewDialog(data, opened.append)
    dlg.show()
    assert dlg.index == 0 and not dlg.back.isVisible()
    dlg.forward()
    assert dlg.index == 1 and dlg.back.isVisible() and dlg.title.text() == data["cards"][1]["title"]
    dlg.go(0)
    assert dlg.index == 0
    page_card = next(i for i, c in enumerate(data["cards"]) if "page" in c["try"])
    dlg.go(page_card)
    dlg.try_it()
    assert opened == [data["cards"][page_card]["try"]["page"]]
    files_card = next(i for i, c in enumerate(data["cards"]) if c["try"].get("action") == "files.open")
    dlg.go(files_card)
    dlg.try_it()
    assert spawned and spawned[-1][0] == "/usr/bin/halos-files"
    dlg.go(len(data["cards"]) - 1)
    assert dlg.next.text() == "Done"
    dlg.skip.click()
    assert not dlg.isVisible()


def test_whats_new_phrase_finds_the_action(env):
    _, spawned = env
    assert registry.search("what's new")[0].id == "whatsnew.show"
    assert actions.execute("whatsnew.show", {}, source="saint").ok
    assert spawned[-1] == ["/usr/bin/saint", "--page", halos_apps.WHATS_NEW_PAGE]
    from core.instance import COMMANDS
    assert COMMANDS.match(f"page:{halos_apps.WHATS_NEW_PAGE}")
