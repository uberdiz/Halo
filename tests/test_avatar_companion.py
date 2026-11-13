"""The avatar as a desktop companion: keeping off the living wallpaper's voice visual, the behaviour context,
beat scheduling, pop-in presence, idle animations, outfits and the avatar actions."""

import os

import pytest

from core.avatar import behavior

APPLETSRC = """[Containments][1]
activityId=abc
wallpaperplugin=org.halos.living

[Containments][1][Wallpaper][org.halos.living][General]
LogoScale=0.3
LogoX=0.5
LogoY=0.5
ShowLogo=true
Source=saint
BarStyle=bars

[Containments][2]
wallpaperplugin=org.kde.image
"""


def test_reads_the_living_wallpaper_from_plasma(tmp_path):
    f = tmp_path / "appletsrc"
    f.write_text(APPLETSRC, encoding="utf-8")
    v = behavior.read_living(f)
    assert v["LogoX"] == "0.5" and v["ShowLogo"] is True and v["Source"] == "saint"
    f.write_text("[Containments][2]\nwallpaperplugin=org.kde.image\n", encoding="utf-8")
    assert behavior.read_living(f) is None
    assert behavior.read_living(tmp_path / "missing") is None


def test_avatar_keeps_off_the_logo_when_both_react_to_the_voice(tmp_path):
    from ui.settings_pages import wallpaper
    f = tmp_path / "appletsrc"
    f.write_text(APPLETSRC, encoding="utf-8")
    screen = (0, 0, 1920, 1080)
    keep = behavior.logo_rect(wallpaper.clean(behavior.read_living(f)), screen)
    kx, ky, kw, kh = keep
    assert kx < 960 < kx + kw and ky < 540 < ky + kh            # around the centred logo
    size = (180, 290)
    x, y = behavior.avoid((900, 450), size, keep, screen)       # dropped right on the logo
    assert x + size[0] <= kx or x >= kx + kw or y + size[1] <= ky or y >= ky + kh
    assert 0 <= x <= 1920 - size[0] and 0 <= y <= 1080 - size[1]
    assert behavior.avoid((10, 10), size, keep, screen) == (10, 10)                 # already clear: untouched
    # the wallpaper doesn't move with SAINT's voice (or shows no logo): nothing to keep off
    assert behavior.logo_rect(wallpaper.clean({"Source": "desktop"}), screen) is None
    assert behavior.logo_rect(wallpaper.clean({"Source": "saint", "ShowLogo": False}), screen) is None
    assert behavior.logo_rect(None, screen) is None


SCREENS = [(0, 0, 1920, 1080)]


def test_context_from_the_desktop():
    ctx = behavior.build_context(("konsole", 100, 100, 800, 600), SCREENS, 25, idle_s=-3, music=True)
    assert ctx.app_class == "konsole" and ctx.window == (100, 100, 800, 600) and ctx.hour == 1
    assert ctx.idle_s == 0 and ctx.music_playing and not ctx.fullscreen
    assert behavior.build_context(("mpv", 0, 0, 1920, 1080), SCREENS, 12).fullscreen      # covers the monitor
    assert behavior.build_context(None, SCREENS, 12, game=True).fullscreen
    assert behavior.build_context(None, SCREENS, 12).window is None


def test_games_and_fullscreen_hide_her_and_low_battery_makes_her_sleepy():
    e = behavior.BehaviorEngine(seed=1)
    assert e.next(behavior.build_context(("firefox", 0, 0, 1920, 1080), SCREENS, 12)).anchor == "hidden"
    assert e.next(behavior.build_context(None, SCREENS, 12, game=True)).anchor == "hidden"
    beat = e.next(behavior.build_context(None, SCREENS, 12, battery_low=True))
    assert beat.clip in ("sleepy", "yawn")


def test_glides_are_eased_not_linear():
    path = behavior.glide_path((0, 0), (300, 0), 15)
    assert len(path) == 15 and path[-1] == (300, 0)
    steps = [b[0] - a[0] for a, b in zip([(0, 0)] + path, path)]
    assert steps[0] < steps[7] > steps[-1]                 # slow, fast, slow


def test_shy_scoots_toward_the_roomier_side():
    assert behavior.shy_spot((1700, 500), (180, 290), SCREENS[0])[0] < 1700
    assert behavior.shy_spot((40, 500), (180, 290), SCREENS[0])[0] > 40
    x, _ = behavior.shy_spot((1740, 500), (180, 290), SCREENS[0])
    assert 0 <= x <= 1920 - 180


@pytest.fixture
def floating(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    monkeypatch.setenv("SAINT_DATA_DIR", str(tmp_path / "data"))
    import core.config
    import ui.avatar
    import ui.avatar.companion as comp
    cfg = core.config.Config(path=str(tmp_path / "c.json"))
    for mod in (core.config, ui.avatar):
        monkeypatch.setattr(mod, "config", cfg)
    monkeypatch.setattr(comp, "idle_seconds", lambda: 0.0)
    monkeypatch.setattr(comp, "battery_low", lambda: False)
    from core.game_mode import game_mode
    monkeypatch.setattr(game_mode, "running", False)
    monkeypatch.setattr(game_mode, "_fullscreen", False)
    f = ui.avatar.FloatingAvatar()
    f.companion.engine = behavior.BehaviorEngine(seed=2)
    yield f
    f.companion.stop_motion()
    f.hide()


def _settle(c):
    for _ in range(80):
        if not c.moving():
            break
        c._advance()


def test_companion_glides_to_the_beat_and_gets_out_of_the_way_of_games(floating, monkeypatch):
    c = floating.companion
    c.active = ("konsole", 300, 300, 900, 600)
    c.next_beat()
    assert c.beat is not None and c.beat.anchor != "hidden"
    _settle(c)
    target = behavior.anchor_point(c.beat.anchor, (floating.width(), floating.height()), (300, 300, 900, 600),
                                   c._screen())
    if target and c.beat.anchor != "edge":
        assert (floating.current_pos().x(), floating.current_pos().y()) == tuple(target)
    from core.game_mode import game_mode
    monkeypatch.setattr(game_mode, "running", True)
    c.next_beat()
    assert c.hidden and not floating.wanted()
    monkeypatch.setattr(game_mode, "running", False)
    c.next_beat()
    assert not c.hidden and floating.wanted()
