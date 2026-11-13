"""Avatar animation clips, the clip builder, the desktop behaviour engine, and the KWin geometry reports."""

import pytest

from core.avatar import AvatarState, behavior, body, clips
from core.saint_dbus import parse_active, parse_placed


def test_every_primitive_is_valid_and_samples():
    for name, clip in clips.PRIMITIVES.items():
        c = clips.validate(clip)
        assert c["name"] == name
        assert clips.sample(c, 0.0) is not None


def test_sample_ends_unless_looping():
    assert clips.sample(clips.get("nod"), 5.0) is None
    assert clips.sample(clips.get("dance"), 50.0) is not None


def test_compose_builds_a_playable_clip_and_rejects_unknown_moves():
    c = clips.compose(["wave", "nod", "spin"], "hello-move")
    assert c["duration"] == pytest.approx(1.8 + 0.9 + 1.4)
    assert [k["t"] for k in c["keys"]] == sorted(k["t"] for k in c["keys"])
    with pytest.raises(clips.ClipError):
        clips.compose(["moonwalk"], "x")
    with pytest.raises(clips.ClipError):
        clips.compose([], "x")


def test_validate_clamps_and_refuses_bad_data():
    c = clips.validate({"name": "big", "duration": 999, "keys": [{"t": 0, "pose": {"head": [500, 0, 0], "hop": 9}}]})
    assert c["duration"] == clips.MAX_DURATION and c["keys"][0]["pose"]["head"][0] == 60 and c["keys"][0]["pose"]["hop"] == 1
    for bad in ({"name": "Bad Name", "keys": [{"t": 0, "pose": {}}]},
                {"name": "ok", "keys": [{"t": 0, "pose": {"code": "rm -rf"}}]},
                {"name": "ok", "keys": [{"t": 0.5, "pose": {}}, {"t": 0.1, "pose": {}}]},
                {"name": "ok", "keys": [{"t": 0, "pose": {"L": {"upper": [0, 0, 0], "lower": [0, 1, 0]}}}]}):
        with pytest.raises(clips.ClipError):
            clips.validate(bad)


def test_save_load_remove(tmp_path):
    clips.save(clips.compose(["cheer", "clap"], "party"), tmp_path)
    assert clips.get("party", tmp_path)["name"] == "party"
    assert "party" in clips.names(tmp_path)
    with pytest.raises(clips.ClipError):
        clips.save(dict(clips.PRIMITIVES["wave"]), tmp_path)        # built-ins can't be overwritten
    assert clips.remove("party", tmp_path) and clips.get("party", tmp_path) is None


def test_clip_pose_drives_the_body_including_legs():
    still = body.BodyDriver().step(AvatarState.IDLE, 0, 0, 1.0)
    sitting = body.BodyDriver().step(AvatarState.IDLE, 0, 0, 1.0, 1.0, clips.sample(clips.get("sit"), 0.79))
    assert still["J_Bip_L_UpperLeg"] != sitting["J_Bip_L_UpperLeg"]
    assert still["J_Bip_L_UpperLeg"] == pytest.approx(body.IDENTITY)


def test_behaviour_follows_the_context():
    e = behavior.BehaviorEngine(seed=3)
    assert e.next(behavior.Context(app_class="steam_app_42")).anchor == "hidden"
    assert e.next(behavior.Context(fullscreen=True)).anchor == "hidden"
    assert e.next(behavior.Context(idle_s=20 * 60)).clip == "sleepy"
    assert e.next(behavior.Context(enabled=False)).clip == ""
    code = [e.next(behavior.Context(app_class="code", window=(0, 0, 800, 600))) for _ in range(12)]
    assert any(b.anchor == "titlebar" for b in code)
    assert any(b.new_clip for b in code)                      # it builds its own animations now and then
    assert all(b.anchor not in ("titlebar", "edge") for b in
               (e.next(behavior.Context(app_class="code")) for _ in range(12)))   # no window known: no window anchors


def test_behaviour_is_deterministic_for_a_seed():
    ctx = behavior.Context(app_class="firefox", window=(10, 10, 900, 700))
    a, b = behavior.BehaviorEngine(seed=7), behavior.BehaviorEngine(seed=7)
    assert [a.next(ctx).clip for _ in range(10)] == [b.next(ctx).clip for _ in range(10)]


def test_anchor_points_stay_on_screen():
    screen = (0, 0, 1920, 1080)
    x, y = behavior.anchor_point("titlebar", (200, 300), (400, 400, 800, 600), screen)
    assert 400 <= x <= 1200 and y < 400
    top = behavior.anchor_point("edge", (200, 300), (400, 400, 800, 600), screen, 1.0)
    bottom = behavior.anchor_point("edge", (200, 300), (400, 400, 800, 600), screen, 0.0)
    assert top[1] < bottom[1]
    assert behavior.anchor_point("stay", (200, 300), None, screen) is None


def test_kwin_geometry_reports_are_parsed_strictly():
    assert parse_placed("SAINT Avatar|120,-40") == ("SAINT Avatar", 120, -40)
    assert parse_placed("SAINT Avatar|1,2;rm") is None
    assert parse_active("org.kde.konsole|0,0,1920,1040") == ("org.kde.konsole", 0, 0, 1920, 1040)
    assert parse_active("x|0,0,-5,10") is None
