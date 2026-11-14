"""The Halo is its own app (halos-halo): SAINT's taskbar pin must never mean the Halo's edge windows.
Asked for three times — these tests pin the split down."""

import io
import json
import sys

import pytest

from core.events import Event, EventType
from tests.test_halos_desktop import qapp  # noqa: F401  (fixture)
from ui import halo_app


class _FakeHalo:
    from PySide6.QtCore import QObject, Signal

    class _S(QObject):
        from PySide6.QtCore import Signal
        open_requested = Signal()
        preview_ended = Signal()

    def __init__(self):
        self.s = self._S()
        self.open_requested, self.preview_ended = self.s.open_requested, self.s.preview_ended
        self.visible, self.previewing, self.refreshed, self.previews = False, False, 0, []

    def set_visible(self, on):
        self.visible = on

    def preview(self, ms):
        self.previewing = True
        self.previews.append(ms)
        self.visible = True

    def refresh(self):
        self.refreshed += 1


def test_child_applies_saints_messages(qapp):
    from ui.reactive import UIBus
    bus, halo, out = UIBus(), _FakeHalo(), io.StringIO()
    seen = []
    bus.event.connect(lambda ev: seen.append(ev.type))
    child = halo_app.HaloChild(halo, bus, out)
    child.handle(json.dumps({"state": {"state": "listening", "label": "Listening"}}))
    assert bus.state["state"] == "listening" and EventType.ASSISTANT_STATE in seen
    child.handle(json.dumps({"np": {"title": "Song", "is_playing": True}}))
    assert bus.now_playing()["title"] == "Song"                   # no media pollers in the child: SAINT says
    child.handle(json.dumps({"event": EventType.PLAN_STEP, "payload": {"i": 1}}))
    assert seen[-1] == EventType.PLAN_STEP
    child.handle(json.dumps({"visible": True}))
    assert halo.visible
    child.handle(json.dumps({"refresh": 1}))
    assert halo.refreshed == 1
    for junk in ("", "not json", "[1,2]", "null"):
        child.handle(junk)                                        # never crashes on a bad line
    halo.open_requested.emit()
    assert out.getvalue().splitlines()[-1] == "open"


def test_preview_then_hidden_again_unless_wanted(qapp):
    from ui.reactive import UIBus
    halo, out = _FakeHalo(), io.StringIO()
    child = halo_app.HaloChild(halo, UIBus(), out)
    child.handle(json.dumps({"preview": 1200}))
    assert halo.previews == [1200] and halo.visible
    halo.previewing = False
    halo.preview_ended.emit()
    assert "preview_ended" in out.getvalue() and not halo.visible    # mode "off": the preview was only a flash


def test_proxy_forwards_only_what_the_halo_draws(qapp, monkeypatch):
    sent = []
    monkeypatch.setattr(halo_app.HaloProxy, "_start", lambda self: None)
    proxy = halo_app.HaloProxy()
    monkeypatch.setattr(proxy, "_send", lambda obj: sent.append(obj))
    proxy._forward(Event(EventType.ASSISTANT_STATE, {"state": "speaking"}))
    proxy._forward(Event(EventType.PLAN_DONE, {"id": 1}))
    proxy._forward(Event(EventType.AI_STREAM_TOKEN, {"t": "x"}))     # chat tokens never cross the pipe
    assert sent == [{"state": {"state": "speaking"}}, {"event": EventType.PLAN_DONE, "payload": {"id": 1}}]
    proxy.set_visible(True)
    proxy.set_visible(True)
    assert sent[-1] == {"visible": True} and sum(1 for m in sent if "visible" in m) == 1
    proxy.preview(900)
    assert proxy.previewing and sent[-1] == {"preview": 900}


def test_real_child_process_round_trip():
    """Start `python -m ui.halo_app` for real: a preview flashes and ends, and closing stdin quits it."""
    import os
    import subprocess
    p = subprocess.Popen([sys.executable, "-m", "ui.halo_app"], cwd=halo_app.ROOT, text=True,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    try:
        p.stdin.write(json.dumps({"state": {"state": "listening"}}) + "\n")
        p.stdin.write(json.dumps({"preview": 300}) + "\n")
        p.stdin.flush()
        assert p.stdout.readline().strip() == "preview_ended"
        p.stdin.close()                                   # SAINT quit: the Halo goes with it
        assert p.wait(timeout=20) == 0
    finally:
        if p.poll() is None:
            p.kill()


def test_only_linux_splits_and_it_can_be_turned_off(monkeypatch):
    from core.config import config
    monkeypatch.setattr(halo_app.sys, "platform", "win32")
    assert not halo_app.separate_process()
    monkeypatch.setattr(halo_app.sys, "platform", "linux")
    monkeypatch.setattr(config, "get", lambda k, d=None: False if k == "overlay.halo_process" else d)
    assert not halo_app.separate_process()


def test_packaging_gives_the_halo_its_own_hidden_launcher_and_kwin_treats_it_as_a_helper():
    import os
    root = halo_app.ROOT
    desk = open(os.path.join(root, "packaging/linux/rootfs/usr/share/applications/halos-halo.desktop")).read()
    assert "NoDisplay=true" in desk and "StartupWMClass=halos-halo" in desk
    js = open(os.path.join(root, "packaging/linux/rootfs/usr/share/kwin/scripts/saint-shell/contents/code/main.js")).read()
    assert '"halos-halo"' in js
