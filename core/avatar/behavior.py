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
import re
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
    bias: dict = field(default_factory=dict)   # anchor -> 0..1, the person's habits (core/avatar/habits.py)


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
        """Window anchors only when the focused window is known (Wayland: the KWin script reports it); the
        person's habits (``ctx.bias``) make the anchors they like likelier."""
        choice = self.rng.choices(anchors, [1.0 + 2.0 * ctx.bias.get(a, 0.0) for a in anchors])[0]
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


# ---------------------------------------------------------------- framing, perches and quiet spots
# Where her feet, seat and eyes are in the avatar window, as a fraction of its height from the top (avatar3d.qml's
# cameras). Head and shoulders is a bust: its bottom edge is what rests on things.
FEET = {"full": 0.955, "portrait": 1.0}
SEAT = {"full": 0.55, "portrait": 1.0}


def view_of(cfg: dict) -> str:
    return "full" if cfg.get("view") == "full" or cfg.get("style") == "hologram" else "portrait"


def perch_point(size: tuple, window: tuple, view: str, x: Optional[float] = None, sitting: bool = True) -> tuple:
    """Top-left that puts her on ``window``'s top edge: sitting on it, or standing (dancing) on it. ``x``: where
    along the edge (her centre, screen px); kept on the window, clear of its ends (title-bar buttons)."""
    aw, ah = size
    wx, wy, ww, _wh = window
    cx = wx + ww * 0.62 if x is None else x
    margin = min(ww / 2, max(aw * 0.35, 90))
    cx = max(wx + margin, min(cx, wx + ww - margin))
    return int(cx - aw / 2), int(wy - ah * (SEAT if sitting else FEET)[view])


def overlap(a: tuple, b: Optional[tuple]) -> float:
    """Area of rectangles a and b (x, y, w, h) overlapping."""
    if not b:
        return 0.0
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return float(max(0, w) * max(0, h))


def body_rect(pos: tuple, size: tuple) -> tuple:
    """The part of her window that she fills (the window is wider than she is)."""
    aw, ah = size
    return (pos[0] + aw * 0.25, pos[1] + ah * 0.04, aw * 0.5, ah * 0.92)


def covers(pos: tuple, size: tuple, window: Optional[tuple], share: float = 0.2) -> bool:
    """She'd hide more than ``share`` of herself in front of ``window`` (what the person is working in)."""
    r = body_rect(pos, size)
    return overlap(r, window) > share * r[2] * r[3]


def settle_spots(size: tuple, view: str, screen: tuple, window: Optional[tuple]) -> dict:
    """Unobtrusive places to rest on ``screen`` (its available area: above the taskbar): standing on the taskbar
    beside the focused window or in a corner, sitting on the window's top edge when there's room above it, or
    peeking in from the side. anchor -> top-left."""
    aw, ah = size
    sx, sy, sw, sh = screen
    floor = int(sy + sh - ah * FEET[view])               # standing on the taskbar (the available area's bottom)
    spots = {"corner": (sx + sw - aw - 16, floor), "corner-left": (sx + 16, floor),
             "peek": (sx + sw - int(aw * 0.55), floor)}
    if window:
        wx, wy, ww, _wh = window
        if wx + ww + aw + 8 <= sx + sw:
            spots["beside"] = (wx + ww + 8, floor)
        if wx - aw - 8 >= sx:
            spots["beside-left"] = (wx - aw - 8, floor)
        perch = perch_point(size, window, view)
        if perch[1] >= sy and wy > sy + 24:              # room above the window for her upper body
            spots["titlebar"] = perch
    return spots


def settle(size: tuple, view: str, screen: tuple, window: Optional[tuple], here: tuple,
           bias: Optional[dict] = None, favourite: Optional[tuple] = None) -> tuple:
    """(anchor, (x, y)): the quiet spot that hides least of the focused window, then the one the person's habits
    favour (``bias`` anchor -> weight; ``favourite``: a learned spot), then the nearest (she doesn't hop around)."""
    spots = settle_spots(size, view, screen, window)
    if favourite:
        spots["habit"] = tuple(int(c) for c in favourite)
    bias = bias or {}
    _sx, _sy, sw, sh = screen
    area = size[0] * size[1] * 0.46

    def score(item):
        anchor, pos = item
        hidden = overlap(body_rect(pos, size), window) / area
        dist = (abs(pos[0] - here[0]) + abs(pos[1] - here[1])) / max(1, sw + sh)
        return hidden * 4 + (0.6 if anchor == "peek" else 0) - min(1.0, bias.get(anchor, 0.0)) * 0.8 + dist * 0.5
    return min(sorted(spots.items()), key=score)


def pick_screen(screens: List[tuple], cursor: Optional[tuple] = None, window: Optional[tuple] = None,
                here: Optional[tuple] = None) -> int:
    """Index of the monitor she belongs on: the one with the cursor, else the focused window's centre, else where
    she is; 0 when nothing matches (a monitor that's gone can't strand her)."""
    def at(pt):
        if pt is None:
            return None
        for i, (x, y, w, h) in enumerate(screens):
            if x <= pt[0] < x + w and y <= pt[1] < y + h:
                return i
        return None
    centre = (window[0] + window[2] / 2, window[1] + window[3] / 2) if window else None
    for pt in (cursor, centre, here):
        i = at(pt)
        if i is not None:
            return i
    return 0


def walk_plan(start: tuple, end: tuple, size: tuple, px_per_s: float = 220.0, max_s: float = 4.0,
              interval_s: float = 0.04):
    """A walk along the floor from ``start`` to ``end`` (top-lefts): evenly spaced points (a steady pace, unlike a
    glide's ease), and the clip speed so her steps keep up with the ground. None when it isn't a walk: too short,
    or a change of height (that's a hop)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if abs(dx) < size[0] * 0.6 or abs(dy) > size[1] * 0.15:
        return None
    seconds = min(max_s, abs(dx) / px_per_s)
    n = max(2, int(seconds / interval_s))
    points = [(round(start[0] + dx * i / n), round(start[1] + dy * i / n)) for i in range(1, n + 1)]
    stride = size[0] * 0.55                               # ~two steps per walk cycle
    return points, max(0.6, min(3.0, abs(dx) / seconds / stride)), (1 if dx > 0 else -1)


def dance_speed(now_playing: Optional[dict]) -> float:
    """Clip speed for one bob per beat: the track's tempo when the player reports one, else a comfortable 112
    BPM. The "bob" clip is one second for two bobs, so 120 BPM is speed 1."""
    try:
        bpm = float((now_playing or {}).get("tempo") or (now_playing or {}).get("bpm") or 112)
    except (TypeError, ValueError):
        bpm = 112.0
    while bpm > 180:
        bpm /= 2
    while bpm < 60:
        bpm *= 2
    return bpm / 120.0


# ---------------------------------------------------------------- idle animations
IDLE_CLIPS = ("stretch", "look-around", "sit-swing", "glance", "nod")
NIGHT_CLIPS = ("yawn", "stretch", "look-around")
IDLE_EVERY = (20.0, 60.0)                 # seconds between idle animations


def idle_clip(rng: random.Random, hour: int) -> str:
    """A small thing to do while nothing else plays; yawns at night."""
    return rng.choice(NIGHT_CLIPS if hour >= 23 or hour < 6 else IDLE_CLIPS)


def idle_delay(rng: random.Random) -> float:
    return rng.uniform(*IDLE_EVERY)


# ---------------------------------------------------------------- popping in for SAINT's actions
PRESENCE = ("always", "pop")
POP_HOLD = 5.0                            # seconds she stays after the last action in "pop" mode


class Presence:
    """Is she on screen? "always", or "pop": only around SAINT's actions, gone POP_HOLD seconds after the last."""

    def __init__(self, mode: str = "always", hold: float = POP_HOLD):
        self.mode = mode if mode in PRESENCE else "always"
        self.hold = hold
        self.until = 0.0

    def visible(self, now: float) -> bool:
        return self.mode == "always" or now < self.until

    def poke(self, now: float) -> bool:
        """Something happened (an action started): keep her around. True when this brings her in."""
        was = self.visible(now)
        self.until = max(self.until, now + self.hold)
        return not was


_GESTURES = (("nod",("audio", "sound", "volume", "media", "music", "spotify", "mic")),
             ("typing", ("files", "file", "shell", "code", "dev", "packages", "git", "write", "edit", "aide")),
             ("point", ("apps", "app", "windows", "window", "browser", "open", "launch", "tile")),
             ("wave", ("power", "lock", "sleep", "restart", "shutdown", "logout")))


def gesture(action: str, failed: bool = False, dx: Optional[float] = None) -> str:
    """The small gesture she makes for an action (an action id like "files.move" or a tool name). ``dx``: where
    its target is relative to her (screen x, + to the right), so she points the right way."""
    if failed:
        return "shrug"
    words = set(re.split(r"[._\s-]+", (action or "").lower()))
    for clip, keys in _GESTURES:
        if words & set(keys):
            if clip == "point":                 # +X is her left, and she faces you: your right is her left
                return "point-right" if dx is not None and dx < 0 else "point-left"
            return clip
    return "nod"


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
