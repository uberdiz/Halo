"""
core/avatar/behavior.py

What SAINT's avatar does on the desktop while the person works: sits on the focused window's title bar, climbs
its edge, peeks in from the side of the screen, dances while music plays, stretches after a long stretch of work,
gets sleepy late at night, and keeps out of the way of games and fullscreen apps.

Deterministic and model-free: ``BehaviorEngine.next(ctx)`` picks the next *beat* from the context with a seeded
random choice for variety, so the same context and seed always give the same beat (and tests can check it).
Now and then it also builds a new animation out of primitives that suit the moment (core/avatar/clips.compose)
and keeps the newest few: that is "SAINT making its own animations".

A beat says which clip to play, where the avatar window goes (``anchor``) and for how long. ui/avatar turns the
anchor into a screen position from the focused window's geometry (reported by the saint-shell KWin script).

Anchors:
    stay        where the person put it
    titlebar    sitting on the top edge of the focused window
    edge        on the focused window's right edge, climbing up it
    peek        at the side of the screen, half out of view
    corner      the bottom-right corner of the screen
    hidden      out of the way (games, fullscreen, the person said so)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

CODE = ("code", "aide", "vscodium", "codium", "kate", "konsole", "jetbrains", "pycharm", "idea", "kitty", "alacritty",
        "zed", "neovide", "sublime")
BROWSER = ("firefox", "chromium", "chrome", "brave", "vivaldi", "edge", "zen", "librewolf", "opera")
MUSIC = ("spotify", "elisa", "rhythmbox", "strawberry", "vlc", "mpv", "audacious")
GAMES = ("steam_app", "gamescope", "steam", "lutris", "heroic", "minecraft", "wine")
OFFICE = ("libreoffice", "soffice", "okular", "obsidian", "notion", "evince", "onlyoffice")
CHAT = ("discord", "telegram", "signal", "slack", "element", "thunderbird")


def category(app_class: str) -> str:
    a = (app_class or "").lower()
    for name, words in (("game", GAMES), ("code", CODE), ("music", MUSIC), ("browser", BROWSER),
                        ("office", OFFICE), ("chat", CHAT)):
        if any(w in a for w in words):
            return name
    return "other" if a else "none"


@dataclass
class Context:
    app_class: str = ""
    window: Optional[tuple] = None        # (x, y, w, h) of the focused window, when known
    hour: int = 12
    idle_s: float = 0.0                   # seconds since the person last typed or moved the mouse
    music_playing: bool = False
    fullscreen: bool = False
    busy: bool = False                    # SAINT itself is listening / thinking / speaking / working
    enabled: bool = True                  # avatar.behaviors
    battery_low: bool = False             # on battery and nearly empty: she gets sleepy


@dataclass
class Beat:
    clip: str
    anchor: str = "stay"
    seconds: float = 20.0
    reason: str = ""
    new_clip: Optional[dict] = field(default=None, repr=False)   # an animation built for this moment


# moments -> primitives that suit them, for building new animations
_MOOD = {"code": ["typing", "think", "nod", "sit-swing"], "music": ["dance", "hop", "spin", "cheer", "clap"],
         "browser": ["peek", "point-left", "point-right", "think"], "office": ["think", "nod", "stretch"],
         "chat": ["wave", "nod", "peek"], "other": ["wave", "stretch", "nod", "peek"],
         "night": ["yawn", "sleepy", "stretch"]}


class BehaviorEngine:
    BUILD_EVERY = 6           # roughly one in this many beats is a freshly built animation
    KEEP_BUILT = 12

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.built: List[dict] = []
        self._n = 0

    def next(self, ctx: Context) -> Beat:
        self._n += 1
        cat = category(ctx.app_class)
        if not ctx.enabled:
            return Beat("", "stay", 30, "desktop play is off")
        if ctx.fullscreen or cat == "game":
            return Beat("", "hidden", 60, "a game or fullscreen app is in front")
        if ctx.busy:
            return Beat("", "stay", 8, "SAINT is busy; the state animation plays")
        night = ctx.hour >= 23 or ctx.hour < 6
        if ctx.idle_s > 15 * 60:
            return Beat("sleepy", "corner", 120, "nobody's been at the PC for a while")
        if ctx.idle_s > 5 * 60:
            return Beat(self.rng.choice(["stretch", "yawn"]), "stay", 20, "a quiet moment")
        if ctx.battery_low:
            return Beat(self.rng.choice(["sleepy", "yawn"]), "stay", 60, "the battery is nearly empty")
        if self._n % self.BUILD_EVERY == 0:
            beat = self._build(cat if not night else "night", ctx)
            if beat:
                return beat
        if night and self.rng.random() < 0.5:
            return Beat(self.rng.choice(["yawn", "sleepy"]), "corner", 40, "it's late")
        if ctx.music_playing or cat == "music":
            return Beat(self.rng.choice(["dance", "dance", "hop", "clap"]), self._near(ctx, ["titlebar", "stay"]), 30,
                        "music is playing")
        if cat == "code":
            return Beat(self.rng.choice(["sit-swing", "typing", "think"]), self._near(ctx, ["titlebar", "titlebar", "edge"]),
                        45, "you're coding: she keeps you company on the window")
        if cat == "browser":
            return Beat(self.rng.choice(["peek", "think", "sit-swing"]), self.rng.choice(["peek", "titlebar"])
                        if ctx.window else "peek", 30, "browsing")
        if cat in ("office", "chat"):
            return Beat(self.rng.choice(["sit-swing", "nod", "wave"]), self._near(ctx, ["titlebar", "stay"]), 30, cat)
        return Beat(self.rng.choice(["stretch", "wave", "peek", "climb"]), self._near(ctx, ["edge", "stay", "peek"]), 25,
                    "idle on the desktop")

    def _near(self, ctx: Context, anchors: List[str]) -> str:
        """Window anchors only when the focused window is known (Wayland: the KWin script reports it)."""
        choice = self.rng.choice(anchors)
        return choice if ctx.window or choice not in ("titlebar", "edge") else "stay"

    def _build(self, mood: str, ctx: Context) -> Optional[Beat]:
        from core.avatar import clips
        moves = list(_MOOD.get(mood, _MOOD["other"]))
        self.rng.shuffle(moves)
        picked = moves[:self.rng.randint(2, 3)]
        name = f"saint-{mood}-{self._n}"
        try:
            clip = clips.compose(picked, name, speed=self.rng.choice([0.8, 1.0, 1.25]))
        except clips.ClipError:
            return None
        self.built = (self.built + [clip])[-self.KEEP_BUILT:]
        anchor = "titlebar" if ctx.window and mood in ("code", "office") else "stay"
        return Beat(name, anchor, clip["duration"] + 4, f"made a new move for this: {' + '.join(picked)}", clip)

    def built_clip(self, name: str) -> Optional[dict]:
        return next((c for c in self.built if c["name"] == name), None)


def anchor_point(anchor: str, size: tuple, window: Optional[tuple], screen: tuple, progress: float = 0.0):
    """Top-left (x, y) for the avatar window of ``size`` (w, h) at ``anchor``, inside ``screen`` (x, y, w, h).
    ``progress`` 0..1 moves along the anchor (climbing up an edge). None for "stay"/"hidden"."""
    aw, ah = size
    sx, sy, sw, sh = screen

    def clamp(x, y):
        return (int(max(sx - aw // 2, min(x, sx + sw - aw // 2))), int(max(sy, min(y, sy + sh - ah))))
    if anchor == "titlebar" and window:
        x, y, w, _h = window
        return clamp(x + w - aw - 40, y - int(ah * 0.78))           # her feet on the title bar, near the right
    if anchor == "edge" and window:
        x, y, w, h = window
        top, bottom = y - ah * 0.6, y + h - ah
        return clamp(x + w - aw * 0.45, bottom + (top - bottom) * max(0.0, min(1.0, progress)))
    if anchor == "peek":
        return clamp(sx + sw - int(aw * 0.55), sy + sh - ah - 40)
    if anchor == "corner":
        return clamp(sx + sw - aw - 24, sy + sh - ah - 24)
    return None


# ---------------------------------------------------------------- the desktop around her
def is_fullscreen(window: Optional[tuple], screens) -> bool:
    """The focused window covers a whole monitor (x, y, w, h each): a game or video in fullscreen."""
    if not window:
        return False
    x, y, w, h = window
    return any(x <= sx + 2 and y <= sy + 2 and x + w >= sx + sw - 2 and y + h >= sy + sh - 2
               for sx, sy, sw, sh in screens)


def build_context(active: Optional[tuple], screens, hour: int, idle_s: float = 0.0, music: bool = False,
                  game: bool = False, busy: bool = False, enabled: bool = True, battery_low: bool = False) -> Context:
    """The behaviour engine's view of the desktop. ``active`` is the KWin report (class, x, y, w, h) or None;
    ``game``: a game is running or something fullscreen is in front (core.game_mode)."""
    app_class, window = (active[0], tuple(active[1:5])) if active else ("", None)
    return Context(app_class=app_class, window=window, hour=int(hour) % 24, idle_s=max(0.0, float(idle_s)),
                   music_playing=bool(music), fullscreen=bool(game) or is_fullscreen(window, screens),
                   busy=bool(busy), enabled=bool(enabled), battery_low=bool(battery_low))


def glide_path(start: tuple, end: tuple, steps: int = 15) -> List[tuple]:
    """``steps`` points from ``start`` to ``end`` (both excluded / included), eased in and out: a move, not a snap."""
    steps = max(1, int(steps))
    out = []
    for i in range(1, steps + 1):
        f = i / steps
        f = f * f * (3 - 2 * f)
        out.append((round(start[0] + (end[0] - start[0]) * f), round(start[1] + (end[1] - start[1]) * f)))
    return out


def shy_spot(pos: tuple, size: tuple, screen: tuple) -> tuple:
    """Where she scoots to when the cursor comes close (shy mode): one and a half widths toward the roomier side."""
    x, y = pos
    aw, _ah = size
    sx, _sy, sw, _sh = screen
    room_left, room_right = x - sx, sx + sw - (x + aw)
    nx = x - int(aw * 1.5) if room_left > room_right else x + int(aw * 1.5)
    return max(sx, min(nx, sx + sw - aw)), y


# ---------------------------------------------------------------- the living wallpaper's voice visual
LIVING = "org.halos.living"
APPLETSRC = "plasma-org.kde.plasma.desktop-appletsrc"


def read_living(path=None) -> Optional[dict]:
    """The living wallpaper's settings from Plasma's config (the first desktop that uses it), booleans typed;
    None when no desktop uses it. Pass the result through ui/settings_pages/wallpaper.clean()."""
    import configparser
    from pathlib import Path
    path = Path(path) if path else Path.home() / ".config" / APPLETSRC
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
    except (OSError, UnicodeDecodeError, configparser.Error):
        return None
    for sec in cp.sections():                      # "[Containments][1]" parses as section "Containments][1"
        if cp.get(sec, "wallpaperplugin", fallback="") == LIVING:
            general = f"{sec}][Wallpaper][{LIVING}][General"
            raw = dict(cp[general]) if cp.has_section(general) else {}
            return {k: (v.strip().lower() == "true") if v.strip().lower() in ("true", "false") else v
                    for k, v in raw.items()}
    return None


def logo_rect(values: Optional[dict], screen: tuple) -> Optional[tuple]:
    """(x, y, w, h) of the wallpaper logo and its bars/ring when they move with SAINT's voice (Source "saint"),
    None otherwise. ``values`` are clean()ed wallpaper settings; ``screen`` the monitor's full geometry."""
    if not values or values.get("Source") != "saint" or not values.get("ShowLogo", True):
        return None
    sx, sy, sw, sh = screen
    size = min(sw, sh) * float(values.get("LogoScale", 0.28))
    cx, cy = sx + sw * float(values.get("LogoX", 0.5)), sy + sh * float(values.get("LogoY", 0.5))
    if values.get("Bars", True) and values.get("BarStyle", "bars") == "bars":
        half = size * 0.85                         # main.qml: bars 1.7 logos wide, ~0.75 logo below it
        return int(cx - half), int(cy - size / 2), int(2 * half), int(size * 1.3)
    half = size * 0.75                             # the ring (or the bare logo, with a margin)
    return int(cx - half), int(cy - half), int(2 * half), int(2 * half)


def avoid(pos: tuple, size: tuple, keep: Optional[tuple], screen: tuple, gap: int = 16) -> tuple:
    """``pos`` (the avatar's top-left) moved the shortest way out of ``keep`` (x, y, w, h), staying on ``screen``
    when it can."""
    if not keep:
        return tuple(pos)
    x, y = pos
    aw, ah = size
    kx, ky, kw, kh = keep
    if x + aw <= kx or x >= kx + kw or y + ah <= ky or y >= ky + kh:
        return tuple(pos)
    sx, sy, sw, sh = screen
    options = [(kx - aw - gap, y), (kx + kw + gap, y), (x, ky - ah - gap), (x, ky + kh + gap)]
    inside = [o for o in options if sx <= o[0] <= sx + sw - aw and sy <= o[1] <= sy + sh - ah]
    return min(inside or options, key=lambda o: abs(o[0] - x) + abs(o[1] - y))
