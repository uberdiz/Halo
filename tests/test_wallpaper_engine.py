"""Wallpaper Engine items found in every Steam library, applied through the Plasma plugin / fallbacks, the action
and its phrases, and the living-wallpaper apply that now reloads and says why Plasma refused."""
import json
import sys
import types

import pytest

from core import wallpaper_engine as we
from ui.settings_pages import wallpaper as wp


def workshop(lib, wid, project, files=("scene.pkg", "preview.gif")):
    d = lib / "steamapps/workshop/content/431960" / wid
    d.mkdir(parents=True)
    (d / "project.json").write_text(json.dumps(project), encoding="utf-8")
    for f in files:
        (d / f).write_bytes(b"x")
    return d


@pytest.fixture
def home(tmp_path):
    native = tmp_path / ".local/share/Steam"
    workshop(native, "111", {"title": "  Neon   City ", "type": "Scene", "file": "scene.pkg", "preview": "preview.gif"})
    workshop(native, "notanid", {"title": "skip me"})
    flat = tmp_path / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
    workshop(flat, "222", {"title": "Rain", "file": "rain.mp4", "preview": "../../secret.png"}, files=("rain.mp4",))
    extra = tmp_path / "Games/SteamLibrary"
    workshop(extra, "333", {"title": "Aurora", "type": "web", "file": "index.html"}, files=("index.html",))
    (native / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders" { "0" { "path" "%s" } "1" { "path" "%s" } }' % (native.as_posix(), extra.as_posix()))
    return tmp_path


def test_items_from_native_flatpak_and_extra_libraries(home):
    found = we.items(home)
    assert [i["title"] for i in found] == ["Aurora", "Neon City", "Rain"]
    by = {i["id"]: i for i in found}
    assert by["111"]["type"] == "scene" and by["111"]["preview"].name == "preview.gif"
    assert by["222"]["type"] == "video" and by["222"]["preview"] is None       # no type -> from the file; ../ refused
    assert by["333"]["type"] == "web" and by["111"]["library"] == home / ".local/share/Steam"
    assert we.find("222", found)["title"] == "Rain" and we.find("neon", found)["id"] == "111"
    assert we.find("nothing like it", found) is None


def test_apply_prefers_the_kde_plugin_and_reloads(home, monkeypatch):
    plug = home / ".local/share/plasma/wallpapers" / we.KDE_PLUGIN
    plug.mkdir(parents=True)
    (plug / "metadata.json").write_text("{}")
    scripts = []

    def run(argv, **kw):
        scripts.append(argv[-1])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    item = we.find("neon", we.items(home))
    assert we.support(home, which=lambda _: None) == "kde"
    assert "Neon City" in we.apply(item, run=run, home=home, which=lambda _: None)
    s = scripts[0]
    assert f"d.wallpaperPlugin = '{we.KDE_PLUGIN}';" in s and "d.writeConfig('WallpaperWorkShopId', '111');" in s
    assert "scene.pkg" in s and s.rstrip().endswith("d.reloadConfig();\n});")


def test_apply_without_support_says_install_and_cli_fallback(home):
    item = we.find("neon", we.items(home))
    with pytest.raises(we.EngineError, match="Install support"):
        we.apply(item, home=home, which=lambda _: None)
    started = []

    def run(argv, **kw):
        out = json.dumps({"outputs": [{"name": "DP-1", "enabled": True}, {"name": "HDMI-A-1", "enabled": False}]})
        return types.SimpleNamespace(returncode=0, stdout=out if argv[0] == "kscreen-doctor" else "", stderr="")
    msg = we.apply(item, run=run, popen=lambda argv, **kw: started.append(argv), home=home,
                   which=lambda n: "/usr/bin/" + n)
    assert "linux-wallpaperengine" in msg
    assert started == [[we.CLI, "--screen-root", "DP-1", "--bg", str(item["dir"])]]


def test_install_support_goes_through_the_package_queue(monkeypatch):
    from core import pkg_queue
    seen = {}

    def run_plan(steps, **kw):
        seen["argv"] = steps[0].argv
        return {"wallpaper-engine": True}
    monkeypatch.setattr(pkg_queue, "run_plan", run_plan)
    assert we.install_support()
    assert seen["argv"][:2] == ["paru", "-S"] and seen["argv"][-1] == we.AUR_PACKAGE


def test_script_refuses_paths_that_would_break_out():
    with pytest.raises(ValueError):
        wp.desktop_script("x.y", {"Key": "a'); evil(); ('"})
    with pytest.raises(ValueError):
        wp.desktop_script("bad plugin'", {})


def test_living_wallpaper_apply_reloads_and_reports_stderr():
    assert "d.reloadConfig();" in wp.plasma_script(wp.DEFAULTS)
    run = lambda argv, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="Error: wallpaper plugin missing")
    why = wp.apply_why(wp.DEFAULTS, run=run)
    assert "wallpaper plugin missing" in why and not wp.apply(wp.DEFAULTS, run=run)


def test_action_and_phrases(home, monkeypatch):
    from core import actions
    from modules.agent import os_intents
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    real = we.items
    monkeypatch.setattr(we, "items", lambda: real(home))
    applied = []
    monkeypatch.setattr(we, "apply", lambda item, screen=-1: applied.append(item["id"]) or "ok")
    a = actions.registry.get("wallpaper.apply_engine")
    assert a is not None and a.available()
    assert a.run({"item": "aurora"}).data["id"] == "333" and applied == ["333"]
    for text, item in [("use the wallpaper engine wallpaper neon city", "neon city"),
                       ("set rain wallpaper engine wallpaper", "rain"), ("use a wallpaper engine wallpaper", None)]:
        intent = os_intents.parse_os(text)
        assert intent is not None and intent.name == "os.wallpaper.apply_engine", text


# --------------------------------------------------------------------------- Windows drives and HalOS Wallpapers
@pytest.fixture
def windows(tmp_path):
    """Two NTFS mounts: C: with Steam in Program Files (x86), D: with a library C:'s libraryfolders.vdf lists."""
    c, d = tmp_path / "mnt/c", tmp_path / "mnt/d"
    steam = c / "Program Files (x86)/Steam"
    workshop(steam, "444", {"title": "Windows Forest", "type": "video", "file": "f.mp4", "preview": "preview.gif"},
             files=("f.mp4", "preview.gif"))
    workshop(d / "SteamLibrary", "555", {"title": "Cyber Rain", "type": "scene", "file": "scene.pkg"})
    (steam / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders" { "0" { "path" "C:\\\\Program Files (x86)\\\\Steam" } "1" { "path" "D:\\\\SteamLibrary" }'
        ' "2" { "path" "E:\\\\..\\\\escape" } }', encoding="utf-8")
    return [c, d]


def test_windows_steam_libraries_are_found_on_every_mounted_drive(home, windows):
    libs = we.windows_libraries(windows)
    assert [p.name for p in libs] == ["Steam", "SteamLibrary"]
    found = {i["id"]: i for i in we.items(home, windows)}
    assert found["444"]["source"] == "windows" and found["555"]["source"] == "windows"
    assert found["111"]["source"] == "halos" and found["444"]["type"] == "video"
    assert we.windows_libraries([]) == []


def test_catalog_has_saint_first_then_engine_then_pictures(home, windows, tmp_path):
    from core import wallpapers as wps
    system = tmp_path / "usr-share-wallpapers"
    (system / "Next/contents/images").mkdir(parents=True)
    (system / "Next/contents/images/1920x1080.png").write_bytes(b"x" * 10)
    (system / "Next/contents/images/640x480.png").write_bytes(b"x")
    (home / "Pictures").mkdir()
    (home / "Pictures/beach.jpg").write_bytes(b"x")
    (home / "Pictures/notes.txt").write_text("no")
    items = wps.catalog(home, system=system, windows=windows)
    assert items[0]["kind"] == "living"
    kinds = [i["kind"] for i in items]
    assert kinds == sorted(kinds, key=["living", "engine", "image"].index)
    pics = {i["title"]: i for i in items if i["kind"] == "image"}
    assert set(pics) == {"Next", "beach"} and pics["Next"]["file"].name == "1920x1080.png"

    scripts = []

    def run(argv, **kw):
        scripts.append(argv[-1])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    assert "living" in wps.apply(items[0], 1, run)
    assert "d.wallpaperPlugin = 'org.halos.living';" in scripts[-1] and "writeConfig(" not in scripts[-1]
    wps.apply(pics["beach"], -1, run)
    assert "org.kde.image" in scripts[-1] and "d.writeConfig('Image', 'file:///" in scripts[-1]
    with pytest.raises(we.EngineError):
        wps.apply({"kind": "nope"}, -1, run)


def test_wallpapers_app_lists_filters_and_applies(home, windows, tmp_path, monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core import wallpapers as wps
    from ui import wallpapers_app as wa
    applied = []
    items = wps.catalog(home, system=tmp_path / "none", windows=windows)
    monkeypatch.setattr(wps, "can_apply", lambda item, home=None: "")
    win = wa.WallpapersWindow(catalog=items, applier=lambda item, screen: applied.append((item["id"], screen)) or "ok")
    assert win.grid.count() == len(items) and win.current["kind"] == "living"
    assert win.customize_btn.isVisibleTo(win) and win.widget_btn.isVisibleTo(win)
    win.nav.setCurrentRow([k for k, _ in wa.VIEWS].index("engine"))
    ids = {win.grid.item(i).data(Qt.UserRole)["id"] for i in range(win.grid.count())}
    assert ids == {"111", "222", "333", "444", "555"}
    win.query.setText("forest")
    assert win.grid.count() == 1 and win.current["id"] == "444" and "Windows drive" in win.meta.text()
    win.apply()
    assert applied == [("444", -1)] and win.status.text() == "ok"
    win.query.setText("")
    pic = tmp_path / "me.png"
    pic.write_bytes(b"x")
    win.add_picture(str(pic))
    assert win.current["id"] == str(pic) and win.view() == "image"
    assert not win.grab().isNull()


def test_wallpapers_app_is_its_own_packaged_app():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    fs = root / "packaging/linux/rootfs"
    desktop = (fs / "usr/share/applications/halos-wallpapers.desktop").read_text(encoding="utf-8")
    assert "Exec=/usr/bin/halos-wallpapers" in desktop and "Icon=halos-wallpapers" in desktop
    assert "-m ui.wallpapers_app" in (fs / "usr/bin/halos-wallpapers").read_text(encoding="utf-8")
    assert 'setDesktopFileName("halos-wallpapers")' in (root / "ui/wallpapers_app.py").read_text(encoding="utf-8")
    pkg = (root / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert "halos-wallpapers," in pkg and "apps/halos-wallpapers.svg" in pkg


def test_migrated_items_and_your_own_projects_are_found(home, monkeypatch):
    """The Windows migration copies workshop items to ~/.local/share/halos/wallpapers/431960/<id> when HalOS has no
    Steam, and your own projects to .../myprojects/<name>: both show up and apply."""
    base = home / ".local/share/halos/wallpapers"
    mig = base / "431960/666"
    mig.mkdir(parents=True)
    (mig / "project.json").write_text(json.dumps({"title": "Moved Over", "type": "video", "file": "m.mp4"}))
    (mig / "m.mp4").write_bytes(b"x")
    mine = base / "myprojects/My Sunset"
    mine.mkdir(parents=True)
    (mine / "project.json").write_text(json.dumps({"title": "My Sunset", "type": "scene", "file": "scene.pkg"}))
    (mine / "scene.pkg").write_bytes(b"x")
    (base / "myprojects/empty").mkdir()                    # no project.json: not a wallpaper
    found = {i["title"]: i for i in we.items(home)}
    assert found["Moved Over"]["source"] == "migrated" and found["Moved Over"]["id"] == "666"
    assert found["My Sunset"]["id"] == "myprojects:My Sunset" and found["My Sunset"]["library"] is None
    assert "empty" not in found and found["Neon City"]["source"] == "halos"
    plug = home / ".local/share/plasma/wallpapers" / we.KDE_PLUGIN
    plug.mkdir(parents=True)
    (plug / "metadata.json").write_text("{}")
    scripts = []
    run = lambda argv, **kw: scripts.append(argv[-1]) or types.SimpleNamespace(returncode=0, stdout="", stderr="")
    we.apply(found["My Sunset"], run=run, home=home, which=lambda _: None)
    assert "SteamLibraryPath" in scripts[-1] and "myprojects" in scripts[-1]
