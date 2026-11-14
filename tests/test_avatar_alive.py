"""The avatar feeling alive: animations that keep playing, sitting on / dancing on windows, resting out of the way,
walking, looking at the pointer, learned habits, popping up for "Hey SAINT", and the head-and-shoulders toggle."""

import random

import pytest

from core.avatar import AvatarState, behavior, body, clips
from core.avatar.habits import Habits
from tests.test_avatar_companion import floating  # noqa: F401  (fixture)

SCREEN = (0, 0, 1920, 1040)                    # above a 40 px taskbar
SIZE = (184, 288)                              # full body, size 160


# ---------------------------------------------------------------- the reset bug
def test_a_clip_the_person_asked_for_outlasts_her_own_play(floating):
    v = floating.view
    assert v.play_clip("dance", user=True)
    assert not v.play_clip("nod")                       # a gesture / beat / idle clip can't cut it short
    v.stop_clip(user=False)
    assert v.clip_name() == "dance" and v.user_clip()
    floating.companion.next_beat()                      # a beat doesn't replace it either
    assert v.clip_name() == "dance"
    v.stop_clip()                                       # the person's Stop does
    assert not v.playing()


def test_sit_holds_instead_of_snapping_back_to_standing():
    sit = clips.get("sit")
    assert sit["hold"] and clips.sample(sit, 30.0)["legs"]["L"] == [-80.0, 85.0]
    assert clips.sample(clips.get("wave"), 30.0) is None          # a gesture still ends
    assert clips.validate({"name": "x", "hold": True, "keys": [{"t": 0, "pose": {}}]})["hold"] is True


def test_her_own_animation_command_is_no_cue_for_a_gesture(floating):
    from core.events import Event, EventType
    v = floating.view
    floating.companion._gesture_at = 0
    floating.companion._event(Event(EventType.ACTION_STARTED, {"action": "avatar.play"}))
    floating.companion._event(Event(EventType.AVATAR_COMMAND, {"play": "cheer"}))
    assert v.clip_name() == "cheer" and v.user_clip()


def test_new_clips_are_valid():
    for name in ("walk", "listen", "pop-up", "bob"):
        c = clips.get(name)
        assert c and clips.sample(c, 0.3) is not None


# ---------------------------------------------------------------- windows
def test_perch_point_sits_her_on_the_top_edge_clear_of_the_buttons():
    win = (400, 300, 1000, 600)
    x, y = behavior.perch_point(SIZE, win, "full")
    assert y == int(300 - SIZE[1] * behavior.SEAT["full"])
    assert 400 + 90 <= x + SIZE[0] / 2 <= 1400 - 90
    _x, ys = behavior.perch_point(SIZE, win, "full", sitting=False)
    assert ys + SIZE[1] * behavior.FEET["full"] == pytest.approx(300, abs=1)
    _x, yp = behavior.perch_point((160, 160), win, "portrait")
    assert yp == 300 - 160                               # a bust rests its bottom edge on the window


def test_dropped_on_a_window_she_sits_and_on_spotify_she_dances(floating, monkeypatch):
    from ui.reactive import ui_bus
    c = floating.companion

    def settle():
        for _ in range(300):
            if not c.moving():
                break
            c._advance()
    c.perch_on(("konsole", 400, 300, 1000, 600))
    settle()
    assert c.sitting and floating.view.base_pose == clips.SIT_POSE
    assert floating.current_pos().y() == behavior.perch_point((floating.width(), floating.height()),
                                                              (400, 300, 1000, 600), "full")[1]
    monkeypatch.setattr(ui_bus, "now_playing", lambda: {"is_playing": True, "tempo": 128})
    c._music = True
    c.perch_on(("spotify", 400, 300, 1000, 600))
    settle()
    assert not c.sitting and floating.view.clip_name() == "bob"
    assert floating.view._speed == pytest.approx(128 / 120)
    c.perch_on(None)
    assert c.perch is None and not c.sitting


def test_dance_speed_follows_the_tempo():
    assert behavior.dance_speed({"tempo": 120}) == 1.0
    assert behavior.dance_speed({"bpm": 240}) == 1.0                 # half time
    assert behavior.dance_speed({}) == pytest.approx(112 / 120)


# ---------------------------------------------------------------- out of the way
def test_settle_never_covers_the_window_you_work_in():
    win = (300, 200, 1000, 700)
    anchor, pos = behavior.settle(SIZE, "full", SCREEN, win, (800, 400))
    assert not behavior.covers(pos, SIZE, win, share=0.05)
    assert anchor in ("titlebar", "beside", "beside-left", "corner", "corner-left")
    maxed = (0, 0, 1920, 1040)                                         # maximised: peek or a corner, never mid-screen
    anchor, pos = behavior.settle(SIZE, "full", SCREEN, maxed, (800, 400))
    assert anchor in ("peek", "corner", "corner-left") and pos[1] + SIZE[1] * 0.955 == pytest.approx(1040, abs=1)


def test_settle_follows_a_learned_favourite():
    fav = (40, 1040 - 288)
    anchor, pos = behavior.settle(SIZE, "full", SCREEN, None, (1700, 700), {"habit": 1.0}, fav)
    assert anchor == "habit" and pos == fav


def test_pick_screen_prefers_the_pointer_then_the_window_and_never_strands_her():
    screens = [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)]
    assert behavior.pick_screen(screens, cursor=(2500, 300)) == 1
    assert behavior.pick_screen(screens, window=(100, 100, 400, 300)) == 0
    assert behavior.pick_screen(screens, cursor=(-9000, 0), here=(-9000, 0)) == 0


def test_walks_along_the_floor_but_hops_up_to_a_window():
    plan = behavior.walk_plan((100, 750), (1300, 750), SIZE)
    assert plan is not None
    points, speed, direction = plan
    assert direction == 1 and points[-1] == (1300, 750) and 0.6 <= speed <= 3.0
    steps = [b[0] - a[0] for a, b in zip(points, points[1:])]
    assert max(steps) - min(steps) <= 1                               # a steady pace
    assert behavior.walk_plan((100, 750), (1300, 200), SIZE) is None   # a climb is a hop, not a walk
    assert behavior.walk_plan((100, 750), (150, 750), SIZE) is None


# ---------------------------------------------------------------- looking
def test_she_looks_at_the_pointer_with_head_and_eyes():
    yaw, pitch = body.look_angles(600, -200)
    assert yaw > 0 and pitch < 0
    d = body.BodyDriver()
    for _ in range(60):
        r = d.step(AvatarState.IDLE, 0.0, 0.0, 0.05, look=(30.0, 0.0))
    still = body.BodyDriver()
    for _ in range(60):
        r0 = still.step(AvatarState.IDLE, 0.0, 0.0, 0.05)
    assert r["J_Bip_C_Head"] != r0["J_Bip_C_Head"] and r["J_Adj_L_FaceEye"] != r0["J_Adj_L_FaceEye"]
    p = body.with_look(body.pose(AvatarState.IDLE, 0, 0), (100.0, 0.0), clip_head=False)
    assert p["head"][1] <= body.LOOK_YAW * 0.8 + 6.5                     # never turns her head off her shoulders


def test_typing_sends_her_eyes_to_the_focused_window(floating, monkeypatch):
    import time
    import ui.avatar.companion as comp
    c = floating.companion
    monkeypatch.setattr(comp, "caret_point", lambda: None)
    c.active = ("kate", 100, 100, 800, 600)
    c._idle_s, c._cursor_at = 0.2, time.monotonic() - 10            # keys going in, pointer still
    floating.view.state = AvatarState.IDLE
    c._update_look()
    assert c.typing() and floating.view.look is not None
    c._cursor((1500, 900)[0], 900)                                 # the pointer moved: she looks at it
    assert not c.typing()


# ---------------------------------------------------------------- habits
def test_habits_learn_a_spot_and_a_liking_and_fade(tmp_path):
    h = Habits(tmp_path / "h.json")
    for _ in range(2):
        h.placed((40, 700), SIZE, SCREEN, hour=14)
    spot = h.favourite_spot(SCREEN, SIZE, 14)
    assert spot is not None and spot[0] < 300 and spot[1] > 500
    assert Habits(tmp_path / "h.json").favourite_spot(SCREEN, SIZE, 15) == spot     # saved, same part of the day
    for _ in range(3):
        h.perched("code")
    assert h.likes_perching("code") > 0.5 and h.anchor_bias("code", 14)["titlebar"] > 0.5
    for _ in range(300):
        h.asked("wave")
    assert sum(h.data["clips"].values()) <= 400                    # bounded: old counts fade
    rng = random.Random(1)
    picks = [h.pick_clip(rng, ["wave", "nod", "stretch"]) for _ in range(200)]
    assert picks.count("wave") > picks.count("nod")


def test_a_corrupt_habits_file_is_ignored(tmp_path):
    (tmp_path / "h.json").write_text("{nope", encoding="utf-8")
    assert Habits(tmp_path / "h.json").favourite_spot(SCREEN, SIZE, 1) is None


# ---------------------------------------------------------------- "Hey SAINT", pop-in, the menu toggle
def test_hey_saint_pops_her_up_from_the_bottom_and_announces_it(floating, monkeypatch):
    from core.events import Event, EventType
    import ui.avatar.companion as comp
    seen = []
    monkeypatch.setattr(comp.Companion, "_appeared", lambda self, reason: seen.append(reason))
    floating.view.cfg["presence"] = "pop"
    floating.companion.restart()
    floating.refresh_visibility()
    assert not floating.isVisible() or not floating.wanted()
    floating.hide()
    floating.companion._event(Event(EventType.ASSISTANT_STATE, {"state": "wake_detected"}))
    assert floating.isVisible() and floating.wanted() and floating.view.opacity == 1.0
    screen = floating.companion._screen()
    assert floating.current_pos().y() > screen[1] + screen[3]           # starts below the bottom edge ...
    for _ in range(300):
        if not floating.companion.moving():
            break
        floating.companion._advance()
    y = floating.current_pos().y()
    assert y < screen[1] + screen[3] - floating.height() * 0.5         # ... and rises into view
    assert floating.view.clip_name() == "listen" and "wake" in seen


def test_showing_her_pops_in(floating):
    floating.hide()
    floating.refresh_visibility()
    assert floating.isVisible() and floating.view.clip_name() == "pop-in"


def test_menu_toggles_head_and_shoulders(floating):
    import core.config
    floating.set_view("portrait")
    assert core.config.config.get("avatar.view") == "portrait" and floating.view.cfg["view"] == "portrait"
    assert floating.width() == floating.height()
    floating.set_view("full")
    assert floating.view.cfg["view"] == "full" and floating.height() > floating.width()


def test_the_window_never_takes_focus(floating):
    from PySide6.QtCore import Qt
    assert floating.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert floating.testAttribute(Qt.WA_ShowWithoutActivating)


def test_kwin_reports_for_perch_cursor_and_work_areas_are_strict():
    from core.saint_dbus import parse_areas, parse_cursor, parse_over
    assert parse_over("SAINT Avatar|Spotify|1,2,3,4") == ("SAINT Avatar", "spotify", 1, 2, 3, 4)
    assert parse_over("SAINT Avatar|x;rm|1,2,3,4") is None
    assert parse_cursor("1,2") == (1, 2) and parse_cursor("1,2,3") is None
    assert parse_areas("0,0,10,10;oops;5,5,0,9") == [(0, 0, 10, 10)]


def test_appearing_and_answering_open_the_wake_free_followup(floating, monkeypatch):
    import sys
    import types
    from core.events import Event, EventType
    calls = []
    fake = types.ModuleType("core.followup")
    fake.open_followup_window = lambda seconds=20.0, source="": calls.append((seconds, source)) or True
    monkeypatch.setitem(sys.modules, "core.followup", fake)
    floating.hide()
    floating.refresh_visibility()                                   # she pops in
    assert calls == [(20.0, "avatar")]
    c = floating.companion
    c._event(Event(EventType.ASSISTANT_STATE, {"state": "speaking"}))
    c._event(Event(EventType.ASSISTANT_STATE, {"state": "idle"}))   # done answering, still out
    assert len(calls) == 2
