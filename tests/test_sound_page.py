"""Settings › Sound (ui/settings_pages/sound.py) with core/sound.py and the sound fix faked: nothing real runs.
The buttons reach the mixer, hidden HDMI outputs get "Turn on and use", and Fix the sound shows what it did."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QPushButton

from ui.settings_pages import sound as page_mod

app = QApplication.instance() or QApplication([])

OUTS = [
    {"kind": "sink", "name": "alsa_output.analog", "label": "Speakers", "card": "c", "profile": "", "available": True,
     "default": True, "percent": 40, "mute": False, "bluetooth": False, "hdmi": False, "combined": False},
    {"kind": "sink", "name": "bluez_output.AA.1", "label": "Headphones", "card": "", "profile": "", "available": True,
     "default": False, "percent": 70, "mute": False, "bluetooth": True, "hdmi": False, "combined": False},
    {"kind": "profile", "name": "", "label": "DELL U2723QE (GB206 · HDMI 2)", "card": "alsa_card.pci-0000_01_00.1",
     "profile": "output:hdmi-stereo-extra1", "available": True, "default": False, "percent": None, "mute": False,
     "bluetooth": False, "hdmi": True, "combined": False},
]
APPS = [{"id": 9, "app": "Firefox", "media": "YouTube", "sink": "alsa_output.analog", "percent": 80, "mute": False}]


@pytest.fixture
def page(monkeypatch):
    calls = []
    monkeypatch.setattr(page_mod, "run_async", lambda fn, done=None, err=None: done(fn()) if done else fn())
    monkeypatch.setattr(page_mod.sys, "platform", "linux")
    monkeypatch.setattr(page_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    s = page_mod.sound
    monkeypatch.setattr(s, "outputs", lambda: OUTS)
    monkeypatch.setattr(s, "apps", lambda: APPS)
    for name in ("set_volume", "set_mute", "move_app", "set_app_volume", "set_app_mute", "combine", "uncombine"):
        monkeypatch.setattr(s, name, lambda *a, n=name: calls.append((n, *a)))
    monkeypatch.setattr(s, "use_output", lambda o: calls.append(("use_output", o["profile"] or o["name"])) or "sinkX")
    monkeypatch.setattr(page_mod.audio_doctor, "repair", lambda: {"message": "I turned on GB206 (HDMI 2).",
                                                                   "ok": True, "did": ["x"], "problems": []})
    p = page_mod.Page()
    return p, calls


def buttons(p, text):
    return [b for b in p.widget.findChildren(QPushButton) if b.text() == text]


def test_lists_hidden_hdmi_and_turns_it_on(page):
    p, calls = page
    assert p.available
    [turn_on] = buttons(p, "Turn on and use")
    turn_on.click()
    assert ("use_output", "output:hdmi-stereo-extra1") in calls
    assert "Sound now plays on DELL U2723QE" in p.msg.text()
    assert len(buttons(p, "Use")) == 1                     # the headphones; the default has no Use button


def test_fix_the_sound_says_what_it_did(page):
    p, _ = page
    p.fix.click()
    assert p.msg.text() == "I turned on GB206 (HDMI 2)." and p.fix.isEnabled()


def test_route_app_and_combine(page):
    p, calls = page
    combo = next(c for c in p.apps_box.findChildren(QComboBox))
    combo.activated.emit(combo.findData("bluez_output.AA.1"))
    assert ("move_app", 9, "bluez_output.AA.1") in calls and "Firefox now plays on Headphones" in p.msg.text()
    for c in p._checks:
        c.setChecked(True)
    p.combine_btn.click()
    assert ("combine", ["alsa_output.analog", "bluez_output.AA.1"]) in calls
    mute = next(c for c in p.apps_box.findChildren(QCheckBox))
    mute.setChecked(True)
    assert ("set_app_mute", 9, True) in calls


def test_off_linux_everything_is_disabled(monkeypatch):
    monkeypatch.setattr(page_mod.sys, "platform", "win32")
    p = page_mod.Page()
    assert not p.available and not p.fix.isEnabled() and "PipeWire" in p.msg.text()
