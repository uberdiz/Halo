"""W10: the Halo is an overlay of its own, not the SAINT app's window. It sits on the desktop's primary monitor
(or every monitor, by setting), a taskbar click can't minimise it, and a second `saint` brings the app window up."""

import json

import pytest

from core import instance
from core.config import DEFAULT_CONFIG
from tests.test_halos_desktop import SHELL_JS, _run_js, needs_node, qapp  # noqa: F401  (qapp is a fixture)
from ui import placement


class _Screen:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _App:
    def __init__(self, *names):
        self._screens = [_Screen(n) for n in names]

    def screens(self):
        return self._screens

    def primaryScreen(self):
        return self._screens[0]


KSCREEN = json.dumps({"outputs": [
    {"name": "HDMI-A-1", "enabled": True, "connected": True, "priority": 2},
    {"name": "DP-1", "enabled": True, "connected": True, "priority": 1},
    {"name": "DP-2", "enabled": False, "connected": True, "priority": 0}]})


def test_kscreen_primary_is_priority_one():
    assert placement.kscreen_primary(KSCREEN) == "DP-1"
    for junk in ("", "not json", "[]", '{"outputs": [{"name": "X", "enabled": true}]}'):
        assert placement.kscreen_primary(junk) == ""


def test_primary_screen_is_the_desktops_not_qts_first(monkeypatch):
    app = _App("HDMI-A-1", "DP-1")                       # Qt on Wayland: the first output listed is "primary"
    monkeypatch.setattr(placement.QGuiApplication, "instance", staticmethod(lambda: app))
    placement.forget_primary()
    asked = []
    ask = lambda: asked.append(1) or "DP-1"
    assert placement.primary_screen(ask).name() == "DP-1"
    assert placement.primary_screen(ask).name() == "DP-1" and len(asked) == 1      # once per monitor layout
    placement.forget_primary()
    assert placement.primary_screen(lambda: "").name() == "HDMI-A-1"               # Plasma didn't say: Qt's
    placement.forget_primary()


def test_halo_defaults_to_always_on_the_primary_screen(qapp, monkeypatch):
    from ui import halo
    assert DEFAULT_CONFIG["overlay"]["halo"] == "always"           # not tied to the SAINT window being minimised
    assert DEFAULT_CONFIG["overlay"]["halo_all_screens"] is False
    h = halo.Halo()
    settings = {"overlay.halo_all_screens": False}
    monkeypatch.setattr(halo.config, "get", lambda k, d=None: settings.get(k, d))
    marker = object()
    monkeypatch.setattr(halo.placement, "primary_screen", lambda: marker)
    assert h._screens() == [marker]
    settings["overlay.halo_all_screens"] = True
    assert h._screens() == qapp.screens()                          # "Show on every monitor"
    h.shutdown()


def test_halo_windows_never_take_focus_or_input(qapp):
    from PySide6.QtCore import Qt
    from ui import halo
    frame = halo._Frame(halo.Halo(), qapp.primaryScreen())
    flags = frame.windowFlags()
    assert flags & Qt.WindowDoesNotAcceptFocus and flags & Qt.WindowTransparentForInput and flags & Qt.Tool
    assert frame.testAttribute(Qt.WA_ShowWithoutActivating)


def test_second_launch_passes_its_activation_token():
    assert instance.COMMANDS.match("token:kwin-1_a2b.c:d")
    for bad in ("token:", "token:a b", "token:a\nquit", "token:" + "x" * 201, "token:$(rm)"):
        assert not instance.COMMANDS.match(bad), bad
    assert instance.activation_token({"XDG_ACTIVATION_TOKEN": "abc-123"}) == "abc-123"
    assert instance.activation_token({"XDG_ACTIVATION_TOKEN": "a b; quit"}) == ""
    assert instance.activation_token({}) == ""


def test_running_saint_uses_the_token_for_its_next_activation(monkeypatch):
    import os
    monkeypatch.delenv(instance.TOKEN_ENV, raising=False)
    from ui.main_window import MainWindow
    shown = []
    fake = type("W", (), {"show_normal": lambda self: shown.append(os.environ.get(instance.TOKEN_ENV))})()
    MainWindow.handle_command(fake, "token:tok-9")
    assert shown == []                                   # the token alone shows nothing
    MainWindow.handle_command(fake, "show")
    assert shown == ["tok-9"]                            # the taskbar click raises the app window with it
    monkeypatch.delenv(instance.TOKEN_ENV, raising=False)


PLACE_HARNESS = r"""
const vm = require('vm');
let added = null;
const ctx = {
  KWin: {}, console,
  workspace: {windowList: () => [], windowAdded: {connect(f) { added = f; }}, windowRemoved: {connect() {}}},
  readConfig: (k, d) => d, registerScreenEdge() {}, callDBus() {}
};
vm.runInNewContext(__SOURCE__, ctx);
function win(caption, cls) {
  const w = {resourceClass: cls, caption, minimized: false, normalWindow: true,
             captionChanged: {connect() {}}, minimizedChanged: {connect(f) { w.onMin = f; }}};
  return w;
}
const halo = win('SAINT Halo frame SAINT:place:0,0,1920,1080', 'saint');
const app = win('SAINT', 'saint');
added(halo); added(app);
halo.minimized = true; halo.onMin();                 // a taskbar click that reached the Halo
app.minimized = true; app.onMin();                   // the app window minimises like any other
console.log(JSON.stringify({halo: [halo.skipTaskbar, halo.skipSwitcher, halo.keepAbove, halo.minimized],
                            app: [!!app.skipTaskbar, app.minimized]}));
"""


@needs_node
def test_shell_keeps_the_halo_off_the_taskbar_and_unminimised():
    out = _run_js(PLACE_HARNESS, SHELL_JS)
    assert out["halo"] == [True, True, True, False]
    assert out["app"] == [False, True]                   # only the app window belongs to the taskbar icon


HELPER_HARNESS = PLACE_HARNESS.replace("added(halo); added(app);", """
const mini = win('SAINT mini player SAINT:helper', 'saint');
added(halo); added(app); added(mini);""").replace(
    "app: [!!app.skipTaskbar, app.minimized]}", "app: [!!app.skipTaskbar, app.minimized], "
    "mini: [mini.skipTaskbar, mini.skipSwitcher, mini.frameGeometry === undefined]}")


@needs_node
def test_shell_keeps_helper_windows_off_the_taskbar_without_placing_them():
    out = _run_js(HELPER_HARNESS, SHELL_JS)
    assert out["mini"] == [True, True, True]
    assert out["app"] == [False, True]


def test_wayland_show_retries_with_the_token_then_asks_kwin(monkeypatch):
    """A hidden SAINT shown from the launcher: the first activation can't work (no surface yet), so the copy
    of the token is used again once mapped, and KWin activates SAINT's own window if that fails too."""
    import os
    import threading
    from PySide6 import QtCore
    from ui.main_window import MainWindow
    from modules.desktop.linux import kwin as kwin_mod
    monkeypatch.delenv(instance.TOKEN_ENV, raising=False)
    monkeypatch.setattr(QtCore.QTimer, "singleShot", staticmethod(lambda _ms, fn: fn()))
    monkeypatch.setattr(threading.Thread, "start", lambda self: self.run())
    activated, tokens = [], []

    class FakeKWin:
        def windows(self):
            from modules.desktop.backend import RawWindow
            return [RawWindow("other", "SAINT", "x", 0, 0, 1, 1, False, False, False, os.getpid() + 1),
                    RawWindow("mine", "SAINT", "saint", 0, 0, 1, 1, False, False, False, os.getpid())]

        def activate(self, handle):
            activated.append(handle)
    monkeypatch.setattr(kwin_mod, "KWinWindows", FakeKWin)
    fake = type("W", (), {"isActiveWindow": lambda s: False, "isVisible": lambda s: True,
                          "windowTitle": lambda s: "SAINT", "_launch_token": "tok-7",
                          "activateWindow": lambda s: tokens.append(os.environ.get(instance.TOKEN_ENV)),
                          "_kwin_activate": MainWindow._kwin_activate})()
    MainWindow._wayland_activate(fake)
    assert tokens == ["tok-7"] and fake._launch_token == ""
    assert activated == ["mine"]
    monkeypatch.delenv(instance.TOKEN_ENV, raising=False)
