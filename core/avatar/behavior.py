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
