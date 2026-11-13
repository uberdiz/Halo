"""The avatar as a desktop companion: keeping off the living wallpaper's voice visual, the behaviour context,
beat scheduling, pop-in presence, idle animations, outfits and the avatar actions."""

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
