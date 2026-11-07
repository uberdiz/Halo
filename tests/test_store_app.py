"""SAINT Store as its own app: the catalogue, app pages, live status, and one store / task manager on the image.
Nothing here touches the network or runs a command."""

import gzip
import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import saintos_apps as sa          # noqa: E402
from core import store, store_browse         # noqa: E402
from core.store import Result                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FS = ROOT / "packaging/linux/rootfs"


def hit(app_id, name=None, main="graphics", subs=(), installs=0):
    return {"app_id": app_id, "name": name or app_id.rsplit(".", 1)[-1], "summary": "s", "icon": "",
            "main_categories": main, "sub_categories": list(subs), "installs_last_month": installs}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    from core.config import config
    config.set("store.artwork", False, persist=False)
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ the catalogue
def test_flathub_pages_are_cached_and_stale_beats_nothing(cache):
    calls = []
    page = {"hits": [hit("org.a.Alpha")], "totalPages": 3}
    assert store_browse.flathub_page("", 1, fetch=lambda u: calls.append(u) or page, now=1000)[1] == 3
    assert "collection/popular?page=1" in calls[0]
    store_browse.flathub_page("", 1, fetch=lambda u: calls.append(u) or page, now=1001)
    assert len(calls) == 1

    def down(_u):
        raise ConnectionError("offline")
    hits, _pages = store_browse.flathub_page("", 1, fetch=down, now=1000 + store_browse.PAGE_TTL + 1)
    assert hits[0]["app_id"] == "org.a.Alpha"
    with pytest.raises(ConnectionError):
        store_browse.flathub_page("game", 1, fetch=down)


def test_catalogue_pages_through_every_source_once():
    pages = {1: [hit("org.a.Alpha"), hit("org.b.Krita", "Krita")], 2: [hit("org.c.Gamma")]}
    catalogue = store_browse.Catalogue(
        flathub=lambda cat, page, per: (pages[page], 2),
        arch=lambda cat: [Result("repo", "krita", "krita"), Result("repo", "kate", "Kate")],
        aur=lambda: [Result("aur", "yay", "yay")])
    seen = []
    more = True
    while more:
        rows, more = catalogue.next_page()
        seen += [(r.source, r.id) for r in rows]
    assert seen == [("flathub", "org.a.Alpha"), ("flathub", "org.b.Krita"), ("flathub", "org.c.Gamma"),
                    ("repo", "kate"), ("aur", "yay")]      # Arch's krita is the Flathub Krita already listed


def test_catalogue_shows_picks_as_picks_and_survives_a_source_failing():
    catalog = {"blender": sa.App("blender", "Blender", "Creative", "flatpak", "org.blender.Blender")}

    def down(*_a):
        raise ConnectionError("offline")
    catalogue = store_browse.Catalogue(catalog=catalog, flathub=lambda c, p, n: ([hit("org.blender.Blender", "Blender")], 1),
                                       arch=down, aur=lambda: [])
    rows, _more = catalogue.next_page()
    assert rows[0].source == "featured" and rows[0].id == "blender"
    assert catalogue.next_page() == ([], False) and catalogue.failed == ["repo"]


def test_categories_filter_and_the_aur_only_lists_under_all():
    asked = []
    catalogue = store_browse.Catalogue("Games", flathub=lambda c, p, n: asked.append(c) or ([], 0),
                                       arch=lambda c: asked.append(c) or [], aur=lambda: asked.append("aur") or [])
    catalogue.next_page()
    assert asked == ["game", "game"]
    assert store_browse.Catalogue("AI").next_page() == ([], False)      # SAINT's picks only


def test_arch_listing_uses_the_system_catalog_with_categories():
    index = {"kate": {"name": "Kate", "summary": "Editor", "categories": ["Utility"], "screenshots": [], "repo": "extra"},
             "krita": {"name": "Krita", "summary": "Paint", "categories": ["Graphics"], "screenshots": ["u"]}}
    assert [r.id for r in store_browse.arch_apps("", index=index)] == ["krita", "kate"]    # pictures first
    assert [r.id for r in store_browse.arch_apps("utility", index=index)] == ["kate"]


def test_aur_listing_keeps_the_popular_real_apps(cache):
    rows = [{"Name": "good-app", "NumVotes": 50, "Popularity": 2.0, "Description": "d"},
            {"Name": "better-app", "NumVotes": 90, "Popularity": 9.0},
            {"Name": "good-app-git", "NumVotes": 99, "Popularity": 9.0},
            {"Name": "libfoo", "NumVotes": 99, "Popularity": 9.0},
            {"Name": "nobody-uses", "NumVotes": 1, "Popularity": 0.1}]
    calls = []
    got = store_browse.aur_apps(fetch=lambda u: calls.append(u) or gzip.compress(json.dumps(rows).encode()), now=1000)
    assert [r.id for r in got] == ["better-app", "good-app"]
    assert store_browse.aur_apps(fetch=lambda u: calls.append(u) or b"", now=1001)[0].extra["votes"] == 90
    assert len(calls) == 1                                   # one download a day


# ------------------------------------------------------------------ apps like this
def test_similar_is_deterministic_ranked_and_never_the_app_itself():
    me = Result("flathub", "org.blender.Blender", "Blender", extra={"categories": ["graphics", "3DGraphics"]})
    same_as_me = Result("featured", "blender", "Blender", extra={"method": "flatpak", "ref": "org.blender.Blender",
                                                                 "category": "Creative"})
    close = Result("flathub", "org.free.CAD", "FreeCAD", extra={"categories": ["graphics", "3DGraphics"]})
    popular = Result("flathub", "org.x.Popular", "Popular", extra={"categories": ["graphics"], "installs": 99})
    quiet = Result("flathub", "org.x.Quiet", "Quiet", extra={"categories": ["graphics"], "installs": 1})
    other = Result("flathub", "org.x.Game", "Game", extra={"categories": ["game"]})
    ranked = store_browse.similar(me, [quiet, other, same_as_me, popular, close, me])
    assert [r.name for r in ranked] == ["FreeCAD", "Popular", "Quiet"]
    assert ranked == store_browse.similar(me, [close, popular, quiet, other])
    assert len(store_browse.similar(me, [close, popular, quiet], limit=2)) == 2


def test_similar_for_works_offline_from_the_picks(cache):
    catalog = sa.load_catalog()

    def down(_u):
        raise ConnectionError("offline")
    found = store_browse.similar_for(store.pick_result(catalog["blender"]), catalog, fetch=down, meta={})
    assert found and all(r.extra["category"] == "Creative" and r.id != "blender" for r in found)


# ------------------------------------------------------------------ status, removing, opening
def test_installed_snapshot_answers_for_every_kind_of_result():
    outputs = {"flatpak": "org.blender.Blender\n", "pacman": "git\nvisual-studio-code-bin\nkate\n"}
    snap = store.installed_snapshot(run=lambda argv, **k: type("R", (), {"returncode": 0, "stdout": outputs[argv[0]]})())
    catalog = sa.load_catalog()
    assert store.is_installed(Result("flathub", "org.blender.Blender", "B"), snap)
    assert store.is_installed(store.pick_result(catalog["blender"]), snap)
    assert store.is_installed(store.pick_result(catalog["vscode"]), snap)
    assert not store.is_installed(store.pick_result(catalog["steam"]), snap)
    assert not store.is_installed(store.pick_result(catalog["dev-tools"]), snap)       # only part of the bundle
    assert store.is_installed(Result("repo", "kate", "Kate"), snap)
    assert not store.is_installed(Result("repo", "kate2", "x", installed=True), snap)  # removed since the search

    def missing(*_a, **_k):
        raise FileNotFoundError
    none = store.installed_snapshot(run=missing)
    assert none == {"flatpak": None, "pacman": None}
    assert store.is_installed(Result("repo", "kate", "Kate", installed=True), none)    # unknown: keep what it said


def test_uninstall_plans_are_argument_lists_from_checked_names():
    catalog = sa.load_catalog()
    assert store.uninstall_plan(Result("flathub", "org.a.Alpha", "A"))[0].argv == \
        ["flatpak", "uninstall", "-y", "--noninteractive", "org.a.Alpha"]
    assert store.uninstall_plan(store.pick_result(catalog["vscode"]))[0].argv == \
        ["pkexec", "pacman", "-R", "--noconfirm", "visual-studio-code-bin"]
    assert store.uninstall_plan(store.pick_result(catalog["claude-code"]), home="/home/u")[0].argv == \
        ["npm", "uninstall", "-g", "--prefix", "/home/u/.local", "@anthropic-ai/claude-code"]
    for bad in (store.pick_result(catalog["dev-tools"]), Result("repo", "saint", "SAINT"),
                Result("repo", "plasma-desktop", "Plasma"), Result("windows", "A.B", "AB")):
        assert not store.can_uninstall(bad)
        with pytest.raises(ValueError):
            store.uninstall_plan(bad)
    with pytest.raises(ValueError):
        store.uninstall_plan(Result("repo", "-rf", "bad"))


def test_launching_prefers_the_packages_own_launcher():
    def run(files):
        return lambda argv, **k: type("R", (), {"returncode": 0, "stdout": "\n".join(files)})()
    assert store.launch_argv(Result("flathub", "org.a.Alpha", "A")) == ["flatpak", "run", "org.a.Alpha"]
    assert store.launch_argv(Result("repo", "kate", "Kate"), run=run(["/usr/bin/kate", "/usr/share/applications/k.desktop"])) \
        == ["gio", "launch", "/usr/share/applications/k.desktop"]
    assert store.launch_argv(Result("repo", "tool", "T"), run=run(["/usr/bin/tool"])) == ["/usr/bin/tool"]
    assert store.launch_argv(Result("repo", "lib", "L"), run=run(["/usr/lib/x.so"])) is None
    assert store.launch_argv(Result("windows", "A.B", "AB")) is None


def test_finish_says_removed_when_removing():
    title, _body = sa.finish({"x": True}, {}, names={"x": "X"}, which=lambda t: None, verb="Removed")
    assert title == "Removed 1 app"
    assert sa.summary({"x": False}, {}, names={"x": "X"}, verb="Removed")[0] == "Nothing was removed"


# ------------------------------------------------------------------ its own app
def test_open_store_app_and_query_links():
    from ui.store_app import query_from
    calls = []
    assert store.open_store_app("blender", popen=lambda a, **k: calls.append(a), exists=lambda p: True)
    assert calls == [["/usr/bin/saint-store", "blender"]]
    assert store.open_store_app(popen=lambda a, **k: calls.append(a), exists=lambda p: False)
    assert calls[-1][1:3] == ["-m", "ui.store_app"]

    def fails(*_a, **_k):
        raise OSError("no")
    assert store.open_store_app(popen=fails) is False
    assert query_from(["--flag", "appstream://org.kde.kate"]) == "org.kde.kate"
    assert query_from(["vs", "code"]) == "vs code" and query_from([]) == ""


def test_store_is_not_a_page_of_saint_any_more():
    from ui.components.sidebar import LINUX_ONLY, PAGES
    assert "Store" not in [p[0] for p in PAGES] and "Store" not in LINUX_ONLY
    src = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    assert "StorePage" not in src
    assert 'sc.open_store' not in (ROOT / "ui/pages/halo_os.py").read_text(encoding="utf-8")


def test_saint_center_opens_the_store_app(monkeypatch):
    from ui import saintos_center as sc
    opened = []
    monkeypatch.setattr(store, "open_store_app", lambda *a: opened.append(a) or True)
    assert sc.open_store() and opened == [()]


def test_voice_names_reach_saints_own_apps():
    src = (ROOT / "modules/desktop/apps.py").read_text(encoding="utf-8")
    linux = src[src.index("_BUILTIN_LINUX"):src.index("_BUILTIN_WINDOWS")]
    assert "plasma-systemmonitor" not in linux
    for name, exe in (("task manager", "saint-taskmgr"), ("system monitor", "saint-taskmgr"), ("store", "saint-store"),
                      ("app store", "saint-store"), ("discover", "saint-store")):
        assert f'"{name}": ("exe", "{exe}", "{exe}")' in linux


def test_image_has_one_store_and_one_task_manager():
    desktop = (FS / "usr/share/applications/saint-store.desktop").read_text(encoding="utf-8")
    assert "Exec=/usr/bin/saint-store %u" in desktop and "Icon=saint-store" in desktop
    assert "StartupWMClass=saint-store" in desktop and "NoDisplay" not in desktop
    assert "-m ui.store_app" in (FS / "usr/bin/saint-store").read_text(encoding="utf-8")
    assert (FS / "usr/share/icons/hicolor/scalable/apps/saint-store.svg").is_file()
    assert not (FS / "usr/share/applications/saintos-apps.desktop").exists()
    for name in ("org.kde.discover", "org.kde.plasma-systemmonitor", "org.kde.ksysguard"):
        assert "NoDisplay=true" in (FS / f"usr/local/share/applications/{name}.desktop").read_text(encoding="utf-8")
    pkgs = (ROOT / "packaging/arch/profile/packages.x86_64").read_text(encoding="utf-8").split("\n")
    for gone in ("discover", "plasma-systemmonitor", "ksysguard"):
        assert gone not in pkgs
    for kept in ("dolphin", "konsole", "firefox", "archlinux-appstream-data"):
        assert kept in pkgs
    pkg = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert "saint-store" in pkg and "usr/local/share/applications" in pkg
    js = (FS / "usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/saintos-defaults.js").read_text(encoding="utf-8")
    assert "applications:saint-store.desktop" in js and re.search(r'favorites = \[[^\]]*"saint-store.desktop"', js)
    assert "systemsettings.desktop" in js                    # KDE's settings have no SAINT equivalent


# ------------------------------------------------------------------ the window
class FakeCatalogue:
    pages = []

    def __init__(self, category="All", source=None, catalog=None, **_k):
        self.category, self.source, self.failed = category, source, []
        self._left = list(type(self).pages)

    def next_page(self):
        rows = self._left.pop(0) if self._left else []
        return rows, bool(self._left)


def pump(app, until=lambda: True, seconds=2.0):
    import time
    end = time.time() + seconds
    while time.time() < end and not until():
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()


@pytest.fixture
def page(app, monkeypatch):
    from ui.pages import store as page_mod
    FakeCatalogue.pages = [[Result("flathub", f"org.x.App{i}", f"App {i}") for i in range(24)],
                           [Result("flathub", "org.x.Last", "Last")]]
    monkeypatch.setattr(page_mod.store_browse, "Catalogue", FakeCatalogue)
    monkeypatch.setattr(page_mod.store, "installed_snapshot", lambda: {})
    monkeypatch.setattr(page_mod.store_browse, "similar_for",
                        lambda r, catalog=None: [Result("flathub", "org.x.Like", "Like it")])
    return page_mod.StorePage()


def test_home_lists_the_catalogue_a_page_at_a_time(app, page):
    pump(app, lambda: page._browse_grid is not None and page._browse_grid.tiles)
    assert len(page._browse_grid.tiles) == 24 and page._more            # not everything at once
    page._load_more()
    pump(app, lambda: not page._more)
    assert len(page._browse_grid.tiles) == 25 and "25" in page._browse_count.text()
    page._pick_category("Games")
    assert page._category == "Games" and page._hero is None
    pump(app, lambda: page._browse_grid.tiles)
    assert page._catalogue.category == "Games"


def test_a_stale_page_is_dropped(app, page):
    pump(app, lambda: page._browse_grid is not None and page._browse_grid.tiles)
    grid = page._browse_grid
    before = len(grid.tiles)
    page._got_page(page._browse_seq - 1, ([Result("flathub", "org.x.Old", "Old")], False))
    assert len(grid.tiles) == before


def test_the_install_card_only_shows_while_something_is_happening(app, page, monkeypatch):
    assert page.job.isHidden()                               # nothing's installing: no "Installing" on the page
    r = Result("flathub", "org.x.Thing", "Thing")
    monkeypatch.setattr(sa, "blockers", lambda: ([], []))
    monkeypatch.setattr(sa, "run_plan", lambda steps, **k: {r.id: True})
    monkeypatch.setattr(sa, "finish", lambda *a, **k: ("Installed 1 app", "Thing"))
    monkeypatch.setattr(page, "_record", lambda *a, **k: None)
    page.enqueue(r, steps=[sa.Step("x", ["true"], [r.id])])
    assert not page.job.isHidden() and page.busy()
    pump(app, lambda: not page.busy())
    assert page.job.isHidden() and r.installed and "Installed 1 app" in page.status.text()


def test_a_failure_stays_until_dismissed(app, page, monkeypatch):
    r = Result("flathub", "org.x.Thing", "Thing")
    monkeypatch.setattr(sa, "blockers", lambda: ([], []))
    monkeypatch.setattr(sa, "run_plan", lambda steps, **k: {r.id: False})
    monkeypatch.setattr(sa, "finish", lambda *a, **k: ("Nothing was installed", "Thing"))
    monkeypatch.setattr(page, "_record", lambda *a, **k: None)
    page.enqueue(r, steps=[sa.Step("x", ["true"], [r.id])])
    pump(app, lambda: not page.busy())
    assert not page.job.isHidden() and not r.installed and "INSTALLING" not in page.job.title_label.text()
    page.job_dismiss.click()
    assert page.job.isHidden()


def test_install_and_uninstall_update_every_view_without_a_reload(app, page, monkeypatch):
    from ui.components.store_tiles import AppTile
    pump(app, lambda: page._browse_grid is not None and page._browse_grid.tiles)
    blender = next(t for t in page.findChildren(AppTile) if t.result.id == "blender").result
    page.show_details(Result("flathub", "org.blender.Blender", "Blender"))     # the same app, from Flathub
    pump(app, lambda: page._details.similar.tiles)
    details, grid = page._details, page._browse_grid
    tile = next(t for t in page.findChildren(AppTile) if t.result is blender)
    assert details.action.text() == "Install" and details.remove.isHidden()

    monkeypatch.setattr(sa, "blockers", lambda: ([], []))
    monkeypatch.setattr(sa, "run_plan", lambda steps, **k: {details.result.id: True})
    monkeypatch.setattr(sa, "finish", lambda *a, **k: ("Installed 1 app", "Blender"))
    monkeypatch.setattr(page, "_record", lambda *a, **k: None)
    page.enqueue(details.result, steps=[sa.Step("x", ["true"], [details.result.id])])
    assert details.action.text() in ("Installing…", "Queued") and not details.action.isEnabled()
    pump(app, lambda: not page.busy())
    assert details.action.text() == "Open" and not details.remove.isHidden()
    assert tile.action.text() == "Open" and blender.installed and page._hero.install.text() == "Open"
    assert page._browse_grid is grid                         # nothing was rebuilt

    monkeypatch.setattr(sa, "finish", lambda *a, **k: ("Removed 1 app", "Blender"))
    monkeypatch.setattr(QMB := __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMB.Yes))
    page._uninstall(details.result)
    pump(app, lambda: not page.busy())
    assert details.action.text() == "Install" and details.remove.isHidden() and tile.action.text() == "Install"


def test_detail_page_back_returns_to_the_same_list(app, page):
    from ui.components.store_tiles import AppDetails
    pump(app, lambda: page._browse_grid is not None and page._browse_grid.tiles)
    grid = page._browse_grid
    first = grid.tiles[0].result
    page.show_details(first)
    assert isinstance(page._details, AppDetails) and page.views.currentWidget() is page.detail_scroll
    pump(app, lambda: page._details.similar.tiles)
    like = page._details.similar.tiles[0]
    assert like.result.name == "Like it" and not page._details.similar_title.isHidden()
    page.show_details(like.result)                           # from "Apps like this": Back comes back here
    assert page._details.result is like.result
    page._details_back()
    assert page._details.result is first
    page._details_back()
    assert page._details is None and page.views.currentWidget() is page.home_scroll and page._browse_grid is grid


def test_store_window_builds_with_its_identity(app, monkeypatch):
    from ui.pages import store as page_mod
    from ui.store_app import StoreWindow
    FakeCatalogue.pages = []
    monkeypatch.setattr(page_mod.store_browse, "Catalogue", FakeCatalogue)
    monkeypatch.setattr(page_mod.store, "installed_snapshot", lambda: {})
    monkeypatch.setattr(page_mod.store_browse, "similar_for", lambda r, catalog=None: [])
    win = StoreWindow()
    assert win.windowTitle() == "SAINT Store" and not win.windowIcon().isNull()
    win.handle_command("ask:blender")
    assert win.page.query.text() == "blender"
    win.page._debounce.stop()
    win.close()
