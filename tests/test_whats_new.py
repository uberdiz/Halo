"""The What's new tour: data/whats_new.json is valid and every "Try it" target exists, it shows once per version,
Skip closes it (and still counts as seen), cards step forward and back, and "what's new" finds the action."""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
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
    return store, spawned


def test_every_try_target_exists():
    from ui import saintos_center as sc, settings_pages
    data = whats_new.load()
    assert data["version"] and len(data["cards"]) >= 8
    pages = {n for n, _ in sc.rail_rows(settings_pages.discover(), os_pages=True)}
    pages |= {"Overview", "Activity", "Tasks", "Music", "Devices", "Memory", "Automations", "History", "Storage",
              "System", "Agent", "Sound"}
    for card in data["cards"]:
        assert card["title"] and card["body"] and card.get("try"), card
        t = card["try"]
        if "page" in t:
            assert t["page"] in pages, t
        else:
            a = registry.get(t["action"])
            assert a is not None and a.available("linux"), t
            a.validate(t.get("params") or {})


def test_after_an_update_a_popup_once_then_the_page(env, tmp_path, monkeypatch):
    store, _ = env
    data = whats_new.load()
    assert whats_new.should_show(data)
    toast = whats_new.show(only_if_new=True)                    # first login on a new version: the small popup
    assert isinstance(toast, whats_new.WhatsNewToast) and store[whats_new.SEEN_KEY] == data["version"]
    assert toast.testAttribute(Qt.WA_ShowWithoutActivating)     # never takes focus
    assert toast.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert data["version"] in toast.title.text()
    top = [c["title"] for c in data["cards"] if c.get("top")][:whats_new.TOAST_ITEMS]
    assert top and all(t in toast.lines.text() for t in top)
    toast.close()
    assert whats_new.show(only_if_new=True) is None             # same version: not again after login
    dlg = whats_new.show()                                      # but the tray / Ctrl+K / voice always open the page
    assert isinstance(dlg, whats_new.WhatsNewDialog)
    dlg.close()
    store[whats_new.SEEN_KEY] = "0.9"
    assert whats_new.should_show(data)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert whats_new.load(str(bad)) == {} and not whats_new.should_show({})


def test_popup_click_opens_the_full_page(env):
    data = whats_new.load()
    opened = []
    toast = whats_new.WhatsNewToast(data, lambda: opened.append(True))
    toast.show()
    QTest.mouseClick(toast, Qt.LeftButton)
    assert opened == [True] and not toast.isVisible()


def test_cards_expand_with_details_and_try_opens_the_real_thing(env):
    store, spawned = env
    opened = []
    data = whats_new.load()
    dlg = whats_new.WhatsNewDialog(data, opened.append)
    dlg.show()
    assert len(dlg.items) == len(data["cards"]) and not any(i.expanded() for i in dlg.items)
    first = dlg.items[0]
    QTest.mouseClick(first, Qt.LeftButton)                      # a click opens its detail
    assert first.expanded() and first.try_btn.isVisibleTo(dlg)
    QTest.mouseClick(first, Qt.LeftButton)
    assert not first.expanded()
    with_details = [i for i in dlg.items if i.card.get("details") or i.card.get("how")]
    assert len(with_details) >= 3
    page_card = next(i for i in dlg.items if "page" in i.card["try"])
    page_card.set_expanded(True)
    page_card.try_it()
    assert opened == [page_card.card["try"]["page"]]
    files_card = next(i for i in dlg.items if i.card["try"].get("action") == "files.open")
    files_card.try_it()
    assert spawned and spawned[-1][0] == "/usr/bin/halos-files"
    wall = next(i for i in dlg.items if i.card["try"].get("action") == "wallpaper.open_app")
    wall.try_it()
    assert spawned[-1][0] == "/usr/bin/halos-wallpapers"
    dlg.close_btn.click()
    assert not dlg.isVisible()


def test_screenshots_named_by_cards_ship(env):
    for card in whats_new.load()["cards"]:
        if card.get("image"):
            assert whats_new.image_of(card) is not None, card["image"]
    assert whats_new.image_of({"image": "../etc/passwd"}) is None


def test_whats_new_phrase_finds_the_action(env):
    _, spawned = env
    assert registry.search("what's new")[0].id == "whatsnew.show"
    assert actions.execute("whatsnew.show", {}, source="saint").ok
    assert spawned[-1] == ["/usr/bin/saint", "--page", halos_apps.WHATS_NEW_PAGE]
    from core.instance import COMMANDS
    assert COMMANDS.match(f"page:{halos_apps.WHATS_NEW_PAGE}")
