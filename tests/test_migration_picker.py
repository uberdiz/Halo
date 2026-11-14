"""Migrate from Windows, by hand: pick any files/folders (copy keeps going past unreadable files, Retry tries just
those), quick-add shortcuts (built-in + your own, saved in config), which Windows (edition, last user), the
wallpaper even when Pictures is a read-only link, and Wallpaper Engine wallpapers."""
import errno
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import windows_migration as wm


def fake_windows(root: Path, users=("seb",)) -> wm.WindowsInstall:
    (root / "Windows/System32/config").mkdir(parents=True)
    (root / "Windows/System32/config/SOFTWARE").write_bytes(b"x")
    (root / "Windows/explorer.exe").write_bytes(b"e")
    for u in users:
        (root / "Users" / u).mkdir(parents=True)
        (root / "Users" / u / "NTUSER.DAT").write_bytes(b"n")
    inst = wm.probe_root(root)
    assert inst is not None
    return inst


BIG_DISK = lambda _p: SimpleNamespace(free=10 ** 12)


def test_last_used_account_and_edition(tmp_path):
    inst = fake_windows(tmp_path / "C", users=("old", "seb"))
    now = os.path.getmtime(tmp_path / "C/Users/seb/NTUSER.DAT")
    os.utime(tmp_path / "C/Users/old/NTUSER.DAT", (now - 9999, now - 9999))
    assert wm.probe_root(tmp_path / "C").last_user == "seb"

    class Hive:
        def __init__(self, path): pass
        def root(self): return "r"
        def node_get_child(self, node, name): return f"{node}/{name}"
        def node_get_value(self, node, name): return name
        def value_string(self, v): return {"ProductName": "Windows 10 Pro", "DisplayVersion": "23H2",
                                           "CurrentBuild": "22631"}[v]
    assert wm.windows_edition(inst.root, hive=Hive) == "Windows 11 Pro 23H2"
    assert wm.windows_edition(inst.root, hive=lambda p: 1 / 0) == ""


def test_copy_paths_keeps_going_and_retry_tries_only_the_failed(tmp_path, monkeypatch):
    inst = fake_windows(tmp_path / "C")
    docs = tmp_path / "C/Users/seb/Documents"
    (docs / "sub").mkdir(parents=True)
    (docs / "a.txt").write_text("a")
    (docs / "sub/wallpaper.jpg").write_text("jpg")
    (docs / "sub/b.txt").write_text("b")
    single = tmp_path / "C/Users/seb/notes.md"
    single.write_text("n")
    real_copy = shutil.copy2

    def flaky(src, dst, **kw):
        if src.endswith("wallpaper.jpg"):
            raise PermissionError(errno.EACCES, "Permission denied")
        return real_copy(src, dst, **kw)
    monkeypatch.setattr(wm.shutil, "copy2", flaky)
    dest = tmp_path / "home/From Windows"
    res = wm.copy_paths(inst, [docs, single, tmp_path / "elsewhere"], dest, usage=BIG_DISK)
    assert res["copied"] == 3 and (dest / "Documents/sub/b.txt").exists() and (dest / "notes.md").exists()
    whys = {Path(e["path"]).name: e["why"] for e in res["errors"]}
    assert "permission denied" in whys["wallpaper.jpg"] and "not on that Windows" in whys["elsewhere"]

    monkeypatch.setattr(wm.shutil, "copy2", real_copy)                     # e.g. after starting Windows once
    again = wm.retry_copies(res["errors"])
    assert again["copied"] == 1 and (dest / "Documents/sub/wallpaper.jpg").read_text() == "jpg"
    assert [Path(e["path"]).name for e in again["errors"]] == ["elsewhere"]
    assert wm.copy_paths(inst, [docs], dest, usage=BIG_DISK)["skipped"] == 3      # nothing overwritten


def test_copy_paths_refuses_when_full(tmp_path):
    inst = fake_windows(tmp_path / "C")
    (tmp_path / "C/Users/seb/big.bin").write_bytes(b"x" * 10)
    res = wm.copy_paths(inst, [tmp_path / "C/Users/seb/big.bin"], tmp_path / "d", usage=lambda _p: SimpleNamespace(free=5))
    assert res["copied"] == 0 and "free" in res["note"]


def test_quick_add_builtin_and_own_shortcuts(tmp_path):
    inst = fake_windows(tmp_path / "C")
    (tmp_path / "C/Users/seb/AppData/Roaming/.minecraft").mkdir(parents=True)
    (tmp_path / "C/Games/Mine").mkdir(parents=True)
    store = {}
    wm.save_quick_add([{"label": "My games", "path": "C:\\Games\\Mine"}], set_=store.__setitem__)
    entries = wm.quick_add_entries(get=lambda k, d=None: store.get(k, d))
    own = [e for e in entries if e["own"]]
    assert own == [{"label": "My games", "path": "C:\\Games\\Mine", "own": True}]
    assert wm.quick_add_path(inst, "seb", own[0]["path"]) == tmp_path / "C/Games/Mine"
    assert wm.quick_add_path(inst, "seb", "AppData/Roaming/.minecraft") is not None
    assert wm.quick_add_path(inst, "seb", "Saved Games") is None                  # not there: greyed out in the UI
    assert wm.quick_add_path(inst, "seb", "../../Windows") is None
    assert wm.relative_quick_path(inst, "seb", tmp_path / "C/Users/seb/AppData") == "AppData"
    assert wm.relative_quick_path(inst, "seb", tmp_path / "C/Games") == "/Games"


def test_wallpaper_skips_unreadable_and_avoids_a_linked_pictures(tmp_path, monkeypatch):
    inst = fake_windows(tmp_path / "C")
    themes = tmp_path / "C/Users/seb/AppData/Roaming/Microsoft/Windows/Themes"
    (themes / "CachedFiles").mkdir(parents=True)
    (themes / "TranscodedWallpaper").write_bytes(b"\xff\xd8 locked")
    (themes / "CachedFiles/CachedImage_1920_1080_POS4.jpg").write_bytes(b"\xff\xd8\xff cached")
    real_open = open

    def guarded(path, *a, **k):
        if str(path).endswith("TranscodedWallpaper"):
            raise PermissionError(errno.EACCES, "Permission denied")
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", guarded)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(wm, "is_link", lambda p: Path(p) == home / "Pictures" or wm.drives.is_link(p))
    r = wm.import_wallpaper(inst, "seb", home, run=lambda *a, **k: None)
    assert r["ok"] and Path(r["path"]).parent == home / wm.WALLPAPER_DIR      # not into the linked Pictures
    assert "permission denied" in r["errors"][0]["why"]


def test_wallpaper_engine_workshop_and_own_projects(tmp_path):
    inst = fake_windows(tmp_path / "C")
    steam = tmp_path / "C/Program Files (x86)/Steam"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps/libraryfolders.vdf").write_text('"libraryfolders" { "1" { "path" "D:\\\\SteamLibrary" } }')
    other = tmp_path / "D/SteamLibrary/steamapps/workshop/content/431960/123456"
    other.mkdir(parents=True)
    (other / "project.json").write_text('{"title": "Rain"}')
    (other / "scene.pkg").write_bytes(b"s")
    mine = steam / "steamapps/common/wallpaper_engine/projects/myprojects/my clock"
    mine.mkdir(parents=True)
    (mine / "project.json").write_text("{}")
    (steam / "steamapps/workshop/content/431960/notanid").mkdir(parents=True)
    items = wm.wallpaper_engine_items(inst, extra_roots=[tmp_path / "D"])
    assert sorted((i["kind"], i["id"]) for i in items) == [("mine", "my clock"), ("workshop", "123456")]

    home = tmp_path / "home"
    (home / ".local/share/Steam").mkdir(parents=True)
    r = wm.import_wallpaper_engine(inst, home, extra_roots=[tmp_path / "D"], usage=BIG_DISK)
    assert r["copied"] == 2 and not r["errors"]
    assert (home / ".local/share/Steam/steamapps/workshop/content/431960/123456/scene.pkg").exists()
    assert (home / wm.WALLPAPER_DIR / "myprojects/my clock/project.json").exists()
    assert wm.import_wallpaper_engine(inst, home, extra_roots=[tmp_path / "D"], usage=BIG_DISK)["kept"] == 2


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_picker_page_ticks_copies_retries_and_saves_shortcuts(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from ui.settings_pages import migrate_windows as mw
    inst = fake_windows(tmp_path / "C")
    inst.edition, inst.size = "Windows 11 Pro 23H2", 512 * 10 ** 9
    docs = tmp_path / "C/Users/seb/Documents"
    docs.mkdir()
    (docs / "a.txt").write_text("a")
    store = {}
    real_entries, real_save = wm.quick_add_entries, wm.save_quick_add
    monkeypatch.setattr(wm, "quick_add_entries", lambda get=None: real_entries(get=lambda k, d=None: store.get(k, d)))
    monkeypatch.setattr(wm, "save_quick_add", lambda own, set_=None: real_save(own, set_=store.__setitem__))
    monkeypatch.setattr(mw, "run_async", lambda fn, ok=None, err=None: ok(fn()))
    page = mw.MigratePage()
    page.show_installs([inst])
    line = page.install_rows.itemAt(0).widget().text()
    assert "Windows 11 Pro 23H2" in line and "last signed in: seb" in line
    page.go(1)
    quick = {page.quick.item(i).text(): page.quick.item(i) for i in range(page.quick.count())}
    assert quick["+ Documents"].flags() & Qt.ItemIsEnabled and not quick["+ Saved Games"].flags()
    page._quick_clicked(quick["+ Documents"])
    assert page.pick_model.picked == [str(docs)] and page.copy_btn.isEnabled()
    assert page.pick_model.data(page.pick_model.index(str(docs / "a.txt")), Qt.CheckStateRole) == Qt.Checked

    page.dest = str(tmp_path / "home/From Windows")
    page._copy_picked()
    assert (tmp_path / "home/From Windows/Documents/a.txt").exists() and "Copied 1 files" in page.pick_result.text()
    page.show_copy_result({"copied": 0, "skipped": 0, "errors": [
        {"path": "x.jpg", "why": "permission denied", "target": str(tmp_path / "t.jpg")}]})
    assert page.fail_list.count() == 1 and not page.retry_btn.isHidden()

    page.add_shortcut(str(docs), label="Docs again")
    assert store[wm.QUICK_KEY] == [{"label": "Docs again", "path": "Documents"}]
    assert any(page.quick.item(i).text() == "★ Docs again" for i in range(page.quick.count()))
    page.remove_shortcut({"label": "Docs again", "path": "Documents", "own": True})
    assert store[wm.QUICK_KEY] == []


def test_browser_step_keeps_going_when_one_import_fails(qapp, tmp_path, monkeypatch):
    from ui.settings_pages import migrate_windows as mw
    inst = fake_windows(tmp_path / "C")
    monkeypatch.setattr(mw, "run_async", lambda fn, ok=None, err=None: ok(fn()))
    page = mw.MigratePage()
    page.show_installs([inst])
    for box in (page.wifi_box, page.saint_box, page.claude_box, page.models_box, page.bookmarks_box, page.vscode_box):
        box.setChecked(False)
    monkeypatch.setattr(wm, "import_wallpaper", lambda *a, **k: (_ for _ in ()).throw(PermissionError("denied")))
    monkeypatch.setattr(wm, "import_wallpaper_engine", lambda *a, **k: {"found": 1, "copied": 1, "kept": 0,
                                                                      "errors": [], "dest": "/w"})
    page._run_browser()
    assert "Wallpaper Engine: 1 copied" in page.browser_result.text()
    assert page.failed_steps == ["wallpaper"] and "denied" in page.step_fail_list.item(0).text()
    monkeypatch.setattr(wm, "import_wallpaper", lambda *a, **k: {"ok": True, "path": "/p.jpg", "applied": False})
    page._run_browser(page.failed_steps)                                         # Retry: only what failed
    assert page.browser_result.text() == "Wallpaper: saved as /p.jpg." and not page.failed_steps
