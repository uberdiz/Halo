"""core/audio_doctor.py with faked pactl/systemctl output: nothing real runs."""
import json

import pytest

from core import audio_doctor


def sink(name, desc="", mute=False, pct=40, ports=None):
    return {"name": name, "description": desc or name, "mute": mute, "ports": ports or [],
            "volume": {"front-left": {"value_percent": f"{pct}%"}, "front-right": {"value_percent": f"{pct}%"}}}


@pytest.fixture
def fake(monkeypatch):
    state = {"sinks": [], "sources": [], "sink": "", "source": "", "after_restart": None, "cards": [],
             "inputs": [], "profile_sinks": {}}
    calls = []

    def sh(argv):
        calls.append(argv)
        if argv[:2] == ["systemctl", "--user"] and state["after_restart"]:
            state.update(state.pop("after_restart"))
        if argv[-2:] == ["list", "sinks"]:
            return json.dumps(state["sinks"])
        if argv[-2:] == ["list", "sources"]:
            return json.dumps(state["sources"])
        if argv[-2:] == ["list", "cards"]:
            return json.dumps(state["cards"])
        if argv[-2:] == ["list", "sink-inputs"]:
            return json.dumps(state["inputs"])
        if argv[1] == "set-card-profile":          # the card makes its sink, like PipeWire does
            for c in state["cards"]:
                if c["name"] == argv[2]:
                    c["active_profile"] = argv[3]
            if argv[3] in state["profile_sinks"]:
                state["sinks"].append(state["profile_sinks"][argv[3]])
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
    assert r["ok"] and r["did"] == [] and r["message"].startswith("Sound looks fine")
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


# --------------------------------------------------------------------------- NVIDIA HDMI/DP and the mixer
NV = "alsa_card.pci-0000_01_00.1"


def nvidia_card(active="off", available=False, monitor=""):
    profiles = {"off": {"description": "Off", "sinks": 0, "available": True, "priority": 0}}
    ports = {}
    for i, suffix in enumerate(["", "-extra1", "-extra2", "-extra3"]):
        prof = f"output:hdmi-stereo{suffix}"
        profiles[prof] = {"description": f"Digital Stereo (HDMI {i + 1}) Output", "sinks": 1, "sources": 0,
                          "priority": 5900 - i * 100, "available": available and i == 1}
        ports[f"hdmi-output-{i}"] = {"description": f"HDMI / DisplayPort {i + 1}", "profiles": [prof],
                                     "availability": "available" if available and i == 1 else "not available",
                                     "properties": {"device.product.name": monitor} if monitor and i == 1 else {}}
    return {"name": NV, "active_profile": active, "profiles": profiles, "ports": ports,
            "properties": {"device.description": "GB206 High Definition Audio Controller", "device.vendor.id": "0x10de"}}


def nv_sink(profile):
    return sink(f"alsa_output.pci-0000_01_00.1.{profile.split(':')[1]}", "GB206 Digital Stereo (HDMI)",
                ports=[{"name": "hdmi-output-1", "availability": "available"}])


def test_nvidia_card_off_and_no_other_output_is_turned_on(fake):
    """The reported bug: monitor speakers over HDMI, card profile "off" (ELD not read), Dummy Output only."""
    state, calls = fake
    state.update(sinks=[sink("auto_null", "Dummy Output")], sink="auto_null", cards=[nvidia_card()],
                 profile_sinks={"output:hdmi-stereo": nv_sink("output:hdmi-stereo")})
    r = audio_doctor.repair(settle=0)
    assert ["pactl", "set-card-profile", NV, "output:hdmi-stereo"] in calls      # highest priority, though "unavailable"
    assert ["pactl", "set-default-sink", "alsa_output.pci-0000_01_00.1.hdmi-stereo"] in calls
    assert not [c for c in calls if c[0] == "systemctl"]                       # no restart needed
    assert r["ok"] and "turned on GB206" in r["message"]


def test_plugged_hdmi_profile_wins_and_streams_move(fake):
    state, calls = fake
    state.update(sinks=[sink("auto_null")], sink="auto_null", cards=[nvidia_card(available=True)],
                 profile_sinks={"output:hdmi-stereo-extra1": nv_sink("output:hdmi-stereo-extra1")},
                 inputs=[{"index": 7, "sink": 0, "properties": {"application.name": "Firefox"}}])
    r = audio_doctor.repair(settle=0)
    assert ["pactl", "set-card-profile", NV, "output:hdmi-stereo-extra1"] in calls
    assert ["pactl", "move-sink-input", "7", "alsa_output.pci-0000_01_00.1.hdmi-stereo-extra1"] in calls
    assert "moved 1 playing app" in r["message"]


def test_other_output_present_leaves_unplugged_hdmi_off_but_says_so(fake):
    state, calls = fake
    state.update(sinks=[sink("alsa_output.analog", "Speakers")], sink="alsa_output.analog", cards=[nvidia_card()])
    r = audio_doctor.repair(settle=0)
    assert not [c for c in calls if c[1] == "set-card-profile"]
    assert r["ok"] and "Settings › Sound" in r["message"] and r["note"]


def test_other_output_present_turns_on_plugged_monitor(fake):
    state, calls = fake
    state.update(sinks=[sink("alsa_output.analog", "Speakers")], sink="alsa_output.analog",
                 cards=[nvidia_card(available=True)])
    audio_doctor.repair(settle=0)
    assert ["pactl", "set-card-profile", NV, "output:hdmi-stereo-extra1"] in calls
    assert not [c for c in calls if c[1] == "set-default-sink"]                 # the default stays yours


def test_unplugged_default_moves_to_plugged_output(fake):
    state, calls = fake
    state.update(sinks=[sink("alsa_output.analog", "Headphones", ports=[{"availability": "not available"}]),
                        sink("alsa_output.hdmi", "HDMI", ports=[{"availability": "available"}])],
                 sink="alsa_output.analog")
    r = audio_doctor.repair(settle=0)
    assert ["pactl", "set-default-sink", "alsa_output.hdmi"] in calls and r["ok"]


def test_outputs_lists_every_hdmi_profile_with_the_monitor_name(fake):
    from core import sound
    state, _ = fake
    state.update(sinks=[sink("alsa_output.analog", "Speakers")], sink="alsa_output.analog",
                 cards=[nvidia_card(available=True, monitor="DELL U2723QE")])
    outs = sound.outputs()
    assert [o["kind"] for o in outs] == ["sink"] + ["profile"] * 4
    assert outs[0]["default"]
    hdmi2 = next(o for o in outs if o["profile"] == "output:hdmi-stereo-extra1")
    assert hdmi2["label"].startswith("DELL U2723QE (") and hdmi2["available"] and hdmi2["hdmi"]
    assert not next(o for o in outs if o["profile"] == "output:hdmi-stereo")["available"]   # listed anyway


def test_use_output_turns_profile_on_and_moves_apps(fake):
    from core import sound
    state, calls = fake
    state.update(sinks=[sink("alsa_output.analog")], cards=[nvidia_card()],
                 profile_sinks={"output:hdmi-stereo-extra2": nv_sink("output:hdmi-stereo-extra2")},
                 inputs=[{"index": 3, "sink": 99, "properties": {"application.name": "Spotify"}}])
    o = next(o for o in sound.outputs() if o["profile"] == "output:hdmi-stereo-extra2")
    got = sound.use_output(o, settle=0)
    assert got == "alsa_output.pci-0000_01_00.1.hdmi-stereo-extra2"
    assert ["pactl", "set-card-profile", NV, "output:hdmi-stereo-extra2"] in calls
    assert ["pactl", "set-default-sink", got] in calls and ["pactl", "move-sink-input", "3", got] in calls


def test_apps_volume_mute_route_and_combine(fake):
    from core import sound
    state, calls = fake
    a, b = sink("alsa_output.analog"), sink("bluez_output.AA_BB.1")
    a["index"], b["index"] = 40, 41
    state.update(sinks=[a, b], inputs=[{"index": 9, "sink": 41, "mute": True, "properties": {
        "application.name": "Firefox", "media.name": "YouTube"},
        "volume": {"mono": {"value_percent": "80%"}}}])
    assert sound.apps() == [{"id": 9, "app": "Firefox", "media": "YouTube", "sink": "bluez_output.AA_BB.1",
                             "percent": 80, "mute": True}]
    sound.set_app_volume(9, 300)
    sound.set_app_mute(9, False)
    sound.move_app(9, "alsa_output.analog")
    sound.set_volume("alsa_output.analog", 65)
    assert ["pactl", "set-sink-input-volume", "9", "150%"] in calls                # clamped
    assert ["pactl", "set-sink-input-mute", "9", "0"] in calls
    assert ["pactl", "move-sink-input", "9", "alsa_output.analog"] in calls
    assert ["pactl", "set-sink-volume", "alsa_output.analog", "65%"] in calls
    assert sound.combine(["alsa_output.analog", "bluez_output.AA_BB.1"]) == sound.COMBINED
    load = next(c for c in calls if c[1] == "load-module")
    assert load[2:5] == ["module-combine-sink", "sink_name=halo_combined",
                         "slaves=alsa_output.analog,bluez_output.AA_BB.1"]
    assert calls.index(["pactl", "unload-module", "module-combine-sink"]) < calls.index(load)
    assert ["pactl", "set-default-sink", "halo_combined"] in calls
    with pytest.raises(ValueError):
        sound.combine(["alsa_output.analog"])
    with pytest.raises(ValueError):
        sound.move_app(9, "x; rm -rf /")
