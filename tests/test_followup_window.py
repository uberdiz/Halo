"""While the avatar is on screen SAINT listens ~20 s without the wake word - never in a game, fullscreen or a call."""

import json
import time

import pytest

from core import followup
from core.events import EventType


class _GM:
    busy = False
    overlays_blocked = False


@pytest.fixture
def no_game(monkeypatch):
    import core.game_mode as gm
    g = _GM()
    monkeypatch.setattr(gm, "game_mode", g)
    monkeypatch.setattr(followup, "in_call", lambda: False)
    return g


def _voice(monkeypatch):
    from modules.voice.module import VoiceModule, ListenPhase
    v = VoiceModule.__new__(VoiceModule)
    import threading
    v._phase_lock = threading.RLock()
    v._phase = ListenPhase.WAKE
    v._listening = True
    v._command_deadline = 0.0
    v._command_reason = ""
    v._command_window = 0.0
    v._awaiting_stt = False
    monkeypatch.setattr(VoiceModule, "wake_mode", property(lambda self: True))
    monkeypatch.setattr(VoiceModule, "_saint_is_talking", lambda self: False)
    return v, ListenPhase


def test_blocked_by_games_fullscreen_and_calls(monkeypatch, no_game):
    assert followup.blocked(call=lambda: False) == ""
    assert followup.blocked(call=lambda: True) == "call"
    no_game.overlays_blocked = True
    assert followup.blocked(call=lambda: False) == "fullscreen"
    no_game.busy = True
    assert followup.blocked(call=lambda: False) == "game"


def test_a_voice_app_capturing_the_mic_is_a_call(monkeypatch):
    monkeypatch.setattr(followup, "_call", {"at": -1e9, "on": False})
    assert followup.in_call(now=0.0, apps=lambda: ["Discord Discord"])
    monkeypatch.setattr(followup, "_call", {"at": -1e9, "on": False})
    assert not followup.in_call(now=0.0, apps=lambda: ["python3 SAINT", "pw-record"])


def test_pactl_rows_are_read(monkeypatch):
    monkeypatch.setattr(followup.sys, "platform", "linux")
    monkeypatch.setattr(followup.shutil, "which", lambda n: "/usr/bin/pactl")
    rows = [{"properties": {"application.process.binary": "vesktop", "application.name": "WEBRTC VoiceEngine"}}]
    run = lambda argv, **kw: type("R", (), {"returncode": 0, "stdout": json.dumps(rows)})()
    assert followup._capturing_apps(run) == ["vesktop WEBRTC VoiceEngine"]


def test_hook_emits_the_event_only_when_allowed(monkeypatch, no_game):
    got = []
    monkeypatch.setattr(followup.event_bus, "emit_event", lambda t, p=None: got.append((t, p)))
    assert followup.open_followup_window(20, "avatar") is True
    assert got == [(followup.EVENT, {"seconds": 20.0, "source": "avatar"})]
    monkeypatch.setattr(followup, "in_call", lambda: True)
    assert followup.open_followup_window() is False and len(got) == 1


def test_voice_enters_the_follow_up_state(monkeypatch, no_game):
    v, Phase = _voice(monkeypatch)
    states = []
    from modules.voice import module as vm
    monkeypatch.setattr(vm.assistant_state, "set", lambda st, detail="", **info: states.append((st, detail, info)))
    assert v.open_followup(20.0, "avatar")
    assert v._phase == Phase.COMMAND and v._command_reason == "follow-up (avatar)"
    assert v.unaddressed_window(v._command_reason)            # still needs speech that sounds like a request
    assert 19 < v._command_deadline - time.monotonic() <= 20
    st, detail, info = states[-1]
    assert st == vm.AssistantState.COMMAND_LISTENING and info == {"followup": True, "window": 20.0}
    assert "no wake word" in detail


def test_follow_up_never_cuts_a_question_short_or_runs_in_a_call(monkeypatch, no_game):
    v, Phase = _voice(monkeypatch)
    v._phase, v._command_reason = Phase.COMMAND, "awaiting reply"
    v._command_deadline = time.monotonic() + 5
    assert not v.open_followup(20.0)
    assert v._command_reason == "awaiting reply"
    v._phase, v._command_reason = Phase.WAKE, ""
    monkeypatch.setattr(followup, "in_call", lambda: True)
    assert not v.open_followup(20.0) and v._phase == Phase.WAKE


def test_the_bus_event_reaches_the_voice_module(monkeypatch, no_game):
    v, Phase = _voice(monkeypatch)
    from core.events import Event
    v._on_bus_event(Event(followup.EVENT, {"seconds": 18, "source": "avatar"}))
    assert v._phase == Phase.COMMAND and v._command_window == 18.0


def test_turn_end_follow_up_is_skipped_in_a_call(monkeypatch, no_game):
    v, Phase = _voice(monkeypatch)
    from core.events import Event
    rests = []
    monkeypatch.setattr(type(v), "_return_to_rest_phase", lambda self, reason="": rests.append(reason))
    monkeypatch.setattr(followup, "in_call", lambda: True)
    v._on_bus_event(Event(EventType.CONVERSATION_TURN_END, {}))
    assert rests == ["turn end"] and v._phase == Phase.WAKE
