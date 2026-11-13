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
