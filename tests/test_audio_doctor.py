"""core/audio_doctor.py with faked pactl/systemctl output: nothing real runs."""
import json

import pytest

from core import audio_doctor


def sink(name, desc="", mute=False, pct=40, ports=None):
    return {"name": name, "description": desc or name, "mute": mute, "ports": ports or [],
            "volume": {"front-left": {"value_percent": f"{pct}%"}, "front-right": {"value_percent": f"{pct}%"}}}


@pytest.fixture
def fake(monkeypatch):
    state = {"sinks": [], "sources": [], "sink": "", "source": "", "after_restart": None}
    calls = []

    def sh(argv):
        calls.append(argv)
        if argv[:2] == ["systemctl", "--user"] and state["after_restart"]:
            state.update(state.pop("after_restart"))
        if argv[-2:] == ["list", "sinks"]:
            return json.dumps(state["sinks"])
        if argv[-2:] == ["list", "sources"]:
            return json.dumps(state["sources"])
        if argv[-1] == "get-default-sink":
            return state["sink"]
        if argv[-1] == "get-default-source":
            return state["source"]
        if argv[1] == "set-default-sink":
            state["sink"] = argv[2]
        if argv[1] in ("set-sink-mute", "set-sink-volume"):
            for s in state["sinks"]:
                if s["name"] == argv[2]:
                    s.update(mute=False) if "mute" in argv[1] else s.update(sink(s["name"], pct=50, ports=s["ports"]))
        return ""

    monkeypatch.setattr(audio_doctor, "_sh", sh)
    return state, calls


def test_healthy_does_nothing(fake):
    state, calls = fake
    state.update(sinks=[sink("alsa_output.analog")], sink="alsa_output.analog")
    r = audio_doctor.repair(settle=0)
    assert r["ok"] and r["did"] == [] and r["message"] == "Sound looks fine."
    assert not [c for c in calls if c[0] == "systemctl" or c[1].startswith("set-")]


def test_dummy_output_restarts_pipewire(fake):
    state, calls = fake
    state.update(sinks=[sink("auto_null", "Dummy Output")], sink="auto_null",
                 after_restart={"sinks": [sink("alsa_output.analog", "Speakers")], "sink": "alsa_output.analog"})
    r = audio_doctor.repair(settle=0)
    assert ["systemctl", "--user", "restart", "wireplumber", "pipewire", "pipewire-pulse"] in calls
    assert r["ok"] and "restarted" in r["message"]


def test_dummy_after_restart_names_the_packages(fake):
    state, _ = fake
    state.update(sinks=[sink("auto_null", "Dummy Output")], sink="auto_null")
    r = audio_doctor.repair(settle=0)
    assert not r["ok"] and "alsa-ucm-conf" in r["message"]


def test_picks_plugged_analog_over_unplugged_hdmi(fake):
    state, calls = fake
    state.update(sinks=[sink("auto_null"),
                        sink("alsa_output.hdmi", "HDMI", ports=[{"availability": "not available"}]),
                        sink("alsa_output.analog-stereo", "Speakers", ports=[{"availability": "available"}])],
                 sink="auto_null")
    r = audio_doctor.repair(settle=0)
    assert ["pactl", "set-default-sink", "alsa_output.analog-stereo"] in calls
    assert r["ok"]


def test_unmutes_and_raises_sink_and_mic(fake):
    state, calls = fake
    state.update(sinks=[sink("alsa_output.analog", mute=True, pct=0)], sink="alsa_output.analog",
                 sources=[sink("alsa_output.analog.monitor"), sink("alsa_input.mic", mute=True, pct=0)],
                 source="alsa_input.mic")
    r = audio_doctor.repair(settle=0)
    assert ["pactl", "set-sink-mute", "alsa_output.analog", "0"] in calls
    assert ["pactl", "set-sink-volume", "alsa_output.analog", "50%"] in calls
    assert ["pactl", "set-source-mute", "alsa_input.mic", "0"] in calls
    assert ["pactl", "set-source-volume", "alsa_input.mic", "70%"] in calls
    assert "unmuted the microphone" in r["message"]


def test_check_reports_without_changing(fake):
    state, calls = fake
    state.update(sinks=[sink("auto_null")], sink="auto_null")
    assert "Dummy Output" in audio_doctor.check()[0]
    assert not [c for c in calls if c[0] == "systemctl"]


def test_registered_and_phrases(monkeypatch):
    from core import actions
    actions.load_builtin()
    a = actions.registry.get("audio.repair")
    assert a is not None and a.platforms == ("linux",)
    from modules.agent import os_intents
    monkeypatch.setattr(os_intents, "_available", lambda _a: True)
    for phrase in ("fix the sound", "I have no sound", "my audio isn't working", "repair the microphone"):
        intent = os_intents.parse_os(phrase)
        assert intent is not None and intent.name == "os.audio.repair", phrase
