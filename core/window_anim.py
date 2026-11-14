"""
core/window_anim.py

Window animation presets for the saint-star KWin effect: built-ins, custom files, validation, the sliders, and
writing the chosen ones to kwinrc [Effect-saint-star], where the effect reads them.

Custom animation: one JSON file in ~/.config/halos/animations/ (the Animations page's "Save as" writes these):

    {
      "schema": 1,
      "name": "Soft close",            1-40 letters, digits, spaces, - or _
      "event": "close",                open | close | minimize | desktop
      "duration": 400,                 total milliseconds, 30-3000 (Plasma's animation speed still scales it)
      "burst": false,                  close only: SAINT paints the supernova burst as the window ends
      "segments": [                    1-8 keyframe segments, played one after another
        {
          "span": 0.3,                 share of the duration (spans are scaled to add up to 1)
          "curve": "OutQuad",          Linear, InQuad, OutQuad, InOutQuad, InCubic, OutCubic, InOutCubic, InBack, OutBack
          "curves": {"opacity": "Linear"},   optional: another curve for one property
          "scale": [1.0, 1.06],        [from, to], 0-3      (1 = window size)
          "opacity": [1.0, 1.0],       [from, to], 0-1
          "brightness": [1.0, 1.3],    [from, to], 0-4      (1 = normal)
          "rotation": [0, 0]           [from, to], degrees, -720 to 720
        }
      ]
    }

Properties are optional in a segment. One left out of a segment holds where the last segment left it, or its
neutral value before that. A file that breaks these rules is skipped and reported, and never reaches KWin.

Profiles (bottom of this file) bundle one animation and speed per event; see load_profiles.
"""

import json
import logging
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core import kde_desktop as kde

log = logging.getLogger("saint.window_anim")

EFFECT = "saint-star"
GROUP = "Effect-saint-star"
EVENTS = {"open": "OpenAnim", "close": "CloseAnim", "minimize": "MinimizeAnim", "desktop": "DesktopAnim"}
EVENT_TITLES = {"open": "Open", "close": "Close", "minimize": "Minimize", "desktop": "Desktop switch"}
CURVES = ("Linear", "InQuad", "OutQuad", "InOutQuad", "InCubic", "OutCubic", "InOutCubic", "InBack", "OutBack")
RANGES = {"scale": (0.0, 3.0), "opacity": (0.0, 1.0), "brightness": (0.0, 4.0), "rotation": (-720.0, 720.0)}
NEUTRAL = {"scale": 1.0, "opacity": 1.0, "brightness": 1.0, "rotation": 0.0}
MAX_FILE_BYTES = 64 * 1024
MAX_SEGMENTS = 8
MIN_MS, MAX_MS = 30, 3000
BASE_MS = 280                       # the effect's reduced-motion threshold is measured on this
REDUCED_BELOW_MS = 100
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$")
SYSTEM = "system"                   # minimize: leave Plasma's own effect in charge


def _seg(span, curve, **props):
    return {"span": span, "curve": curve, **props}


# The first preset of each event is what a fresh install plays, and the effect's BUILTIN in main.js must match it
# (tests/test_halos_desktop.py runs the effect to compare).
BUILTIN: Dict[str, List[Dict]] = {
    "open": [
        {"id": "saint-star", "name": "SAINT star", "duration": 280, "segments": [
            {**_seg(1, "OutBack", scale=[0.55, 1], rotation=[-18, 0], opacity=[0, 1], brightness=[1.7, 1]),
             "curves": {"opacity": "OutQuad"}}]},
        {"id": "pop", "name": "Pop", "duration": 220, "segments": [
            _seg(1, "OutBack", scale=[0.85, 1], opacity=[0, 1])]},
        {"id": "fade", "name": "Fade", "duration": 180, "segments": [_seg(1, "OutQuad", opacity=[0, 1])]},
        {"id": "none", "name": "None", "duration": 0, "segments": []},
    ],
    "close": [
        # The window swells a little, then folds away: it shrinks to nothing with a slight turn while it
        # flashes bright (a scripted effect can't bend a window; a real page curl needs a C++/GLSL KWin effect).
        {"id": "fold", "name": "Fold away", "duration": 460, "segments": [
            _seg(0.25, "OutQuad", scale=[1, 1.06], brightness=[1, 1.3], rotation=[0, 0], opacity=[1, 1]),
            {**_seg(0.75, "InCubic", scale=[1.06, 0], brightness=[1.3, 2.4], rotation=[0, 14], opacity=[1, 0]),
             "curves": {"opacity": "InQuad"}}]},
        # The window itself pulls inward, then bursts outward and fades.
        {"id": "supernova", "name": "Supernova", "duration": 420, "segments": [
            _seg(0.45, "InOutQuad", scale=[1, 0.84], brightness=[1, 1.35], opacity=[1, 1]),
            {**_seg(0.55, "OutCubic", scale=[0.84, 1.3], brightness=[1.35, 2.2], opacity=[1, 0]),
             "curves": {"opacity": "Linear"}}]},
        # The window collapses to a point and SAINT paints a star burst there.
        {"id": "star-burst", "name": "Star burst", "duration": 420, "burst": True, "segments": [
            _seg(0.3, "OutQuad", scale=[1, 1.06], brightness=[1, 1.3], opacity=[1, 1]),
            _seg(0.7, "InCubic", scale=[1.06, 0], brightness=[1.3, 2.4], opacity=[1, 0.85])]},
        {"id": "star-out", "name": "Star going out", "duration": 280, "segments": [
            _seg(1, "InQuad", scale=[1, 0], rotation=[0, 30], opacity=[1, 0], brightness=[1, 2.2])]},
        {"id": "shrink", "name": "Shrink", "duration": 200, "segments": [
            _seg(1, "InQuad", scale=[1, 0.8], opacity=[1, 0])]},
        {"id": "fade", "name": "Fade", "duration": 180, "segments": [_seg(1, "InQuad", opacity=[1, 0])]},
        {"id": "none", "name": "None", "duration": 0, "segments": []},
    ],
    "minimize": [
        {"id": SYSTEM, "name": "Plasma default", "duration": 0, "segments": []},
        {"id": "collapse", "name": "Collapse", "duration": 260, "segments": [
            _seg(1, "InCubic", scale=[1, 0.1], opacity=[1, 0], brightness=[1, 1.4])]},
        {"id": "fade", "name": "Fade", "duration": 180, "segments": [_seg(1, "InQuad", opacity=[1, 0])]},
    ],
    "desktop": [
        {"id": "glow", "name": "Glow in", "duration": 280, "segments": [
            _seg(1, "OutCubic", scale=[0.94, 1], brightness=[1.35, 1])]},
        {"id": "zoom", "name": "Zoom", "duration": 300, "segments": [
            _seg(1, "OutBack", scale=[0.85, 1], opacity=[0.6, 1])]},
        {"id": "none", "name": "None", "duration": 0, "segments": []},
    ],
}


def animations_dir() -> Path:
    return Path(kde.config_home()) / "halos" / "animations"


def _number(value, what: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise ValueError(f"{what} must be a number")
    if not low <= value <= high:
        raise ValueError(f"{what} must be between {low:g} and {high:g}")
    return float(value)


def validate(data, event: Optional[str] = None) -> Dict:
    """A preset's JSON -> a clean copy with spans adding up to 1 and every used property in every segment.
    Raises ValueError saying what's wrong. Unknown keys are dropped."""
    if not isinstance(data, dict):
        raise ValueError("an animation is a JSON object")
    if data.get("schema", 1) != 1:
        raise ValueError(f"schema {data.get('schema')!r} isn't one this version knows")
    name = data.get("name")
    if not isinstance(name, str) or not _NAME.match(name):
        raise ValueError("name: 1-40 letters, digits, spaces, - or _")
    ev = data.get("event", event)
    if ev not in EVENTS or (event and ev != event):
        raise ValueError(f"event must be {event or ' / '.join(EVENTS)}")
    duration = _number(data.get("duration"), "duration", MIN_MS, MAX_MS)
    raw = data.get("segments")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SEGMENTS:
        raise ValueError(f"segments: 1 to {MAX_SEGMENTS} of them")

    spans = []
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            raise ValueError(f"segment {i + 1} isn't an object")
        span = _number(s.get("span", 1), f"segment {i + 1} span", 0.001, 1000)
        spans.append(span)
    used = [k for k in RANGES if any(k in s for s in raw)]
    if not used:
        raise ValueError("no segment animates anything")

    hold = dict(NEUTRAL)
    segments = []
    for i, s in enumerate(raw):
        curve = s.get("curve", "Linear")
        if curve not in CURVES:
            raise ValueError(f"segment {i + 1}: unknown curve {curve!r}")
        clean = {"span": spans[i] / sum(spans), "curve": curve}
        curves = s.get("curves")
        if curves is not None:
            if not isinstance(curves, dict) or any(k not in RANGES or v not in CURVES for k, v in curves.items()):
                raise ValueError(f"segment {i + 1}: bad curves")
            clean["curves"] = dict(curves)
        for k in used:
            low, high = RANGES[k]
            if k in s:
                pair = s[k]
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError(f"segment {i + 1}: {k} is [from, to]")
                a = _number(pair[0], f"segment {i + 1} {k}", low, high)
                b = _number(pair[1], f"segment {i + 1} {k}", low, high)
            else:
                a = b = hold[k]
            clean[k] = [a, b]
            hold[k] = b
        segments.append(clean)
    out = {"schema": 1, "name": name, "event": ev, "duration": int(duration), "segments": segments}
    if data.get("burst") and ev == "close":
        out["burst"] = True
    return out


def builtin(event: str, preset_id: str) -> Optional[Dict]:
    for p in BUILTIN.get(event, []):
        if p["id"] == preset_id:
            return p
    return None


def default_preset(event: str) -> Dict:
    return BUILTIN[event][0]


def load_custom(directory: Optional[Path] = None) -> Tuple[Dict[str, List[Dict]], List[str]]:
    """({event: presets}, problems): the valid files, and a line for each one that was skipped."""
    d = Path(directory) if directory is not None else animations_dir()
    found: Dict[str, List[Dict]] = {e: [] for e in EVENTS}
    problems = []
    try:
        files = sorted(d.glob("*.json"))
    except OSError:
        return found, problems
    for f in files:
        try:
            if f.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("too big")
            p = validate(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as e:           # json.JSONDecodeError is a ValueError
            log.warning("animation.bad_file %s: %s", f.name, e)
            problems.append(f"{f.name}: {e}")
            continue
        p["id"] = f"custom:{f.stem}"
        found[p["event"]].append(p)
    return found, problems


def save_custom(preset: Dict, name: str, event: str, directory: Optional[Path] = None) -> Path:
    """Save as a new custom animation; a file of the same name is replaced. ValueError if it wouldn't load back."""
    data = validate({**preset, "schema": 1, "name": name, "event": event}, event)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower() or "animation"
    d = Path(directory) if directory is not None else animations_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{event}-{stem}.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _amplify(value: float, neutral: float, k: float, low: float, high: float) -> float:
    return round(max(low, min(high, neutral + (value - neutral) * k)), 4)


def tuned(preset: Dict, duration: Optional[int] = None, scale: float = 1.0, rotation: float = 1.0,
          brightness: float = 1.0) -> Dict:
    """The sliders, baked into the numbers the effect reads. scale, rotation and brightness are multipliers on how
    far the preset moves from neutral (1 = as designed, 0 = not at all), so the effect itself stays simple."""
    out = dict(preset)
    if duration is not None and preset.get("segments"):
        out["duration"] = max(MIN_MS, min(MAX_MS, int(duration)))
    segments = []
    for s in preset.get("segments", []):
        c = dict(s)
        for k, m in (("scale", scale), ("rotation", rotation), ("brightness", brightness)):
            if k in c:
                c[k] = [_amplify(v, NEUTRAL[k], m, *RANGES[k]) for v in c[k]]
        segments.append(c)
    out["segments"] = segments
    return out


def serialise(preset: Dict) -> str:
    """What goes in kwinrc: the fields the effect reads, plus the page's own (id, tune) to restore its controls."""
    keep = {k: preset[k] for k in ("name", "id", "duration", "burst", "segments", "tune") if k in preset}
    return json.dumps(keep, separators=(",", ":"))


def current(event: str, dirs: Optional[List[str]] = None) -> Dict:
    """The preset configured for an event, or the default if there's none or it's unreadable."""
    text = kde.read_value(kde.KWINRC, GROUP, EVENTS[event], "", dirs)
    if text:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("segments"), list):
                return data
        except ValueError:
            log.warning("animation.bad_config %s", event)
    return default_preset(event)


def reduced_motion(dirs: Optional[List[str]] = None) -> bool:
    return kde.read_value(kde.KWINRC, GROUP, "ReducedMotion", "false", dirs).lower() == "true"


def apply(chosen: Dict[str, Dict], reduced: bool, run: Callable = kde._run) -> bool:
    """Write the chosen presets and tell the effect. Plasma's squash effect stays on only while minimize is on
    "Plasma default": two minimize animations at once look broken."""
    ok = kde.write_value(kde.KWINRC, GROUP, "ReducedMotion", "true" if reduced else "false", run)
    for event, key in EVENTS.items():
        preset = chosen[event]
        system = preset.get("id") == SYSTEM
        ok = kde.write_value(kde.KWINRC, GROUP, key, None if system else serialise(preset), run) and ok
    burst = bool(chosen["close"].get("burst"))
    ok = kde.write_value(kde.KWINRC, kde.SHELL_GROUP, "CloseBurst", "true" if burst else "false", run) and ok
    squash = chosen["minimize"].get("id") == SYSTEM
    ok = kde.write_value(kde.KWINRC, "Plugins", "squashEnabled", None if squash else "false", run) and ok
    bus = kde.qdbus()
    run([bus, "org.kde.KWin", "/Effects", f"org.kde.kwin.Effects.{'loadEffect' if squash else 'unloadEffect'}", "squash"])
    return run([bus, "org.kde.KWin", "/Effects", "org.kde.kwin.Effects.reconfigureEffect", EFFECT])[0] and ok


def animation_factor(dirs: Optional[List[str]] = None) -> float:
    """Plasma's animation speed: 0 is Instant, 1 normal."""
    try:
        return max(0.0, float(kde.read_value("kdeglobals", "KDE", "AnimationDurationFactor", "1", dirs)))
    except ValueError:
        return 1.0


def burst_delay_ms(dirs: Optional[List[str]] = None) -> Optional[int]:
    """How long after a window closes SAINT paints the burst (the collapse's end), or None for no burst: the close
    animation has none, the effect is off, or reduced motion applies (the same rules as the effect's)."""
    plugins = kde.read_config(kde.KWINRC, dirs).get("Plugins", {})
    if plugins.get("saint-starEnabled", "true").lower() == "false":
        return None
    factor = animation_factor(dirs)
    if factor <= 0 or BASE_MS * factor < REDUCED_BELOW_MS or reduced_motion(dirs):
        return None
    preset = current("close", dirs)
    if not preset.get("burst"):
        return None
    return int(max(0, preset.get("duration", 0)) * factor * 0.92)   # the last 8% of the collapse is too small to see


def sample(preset: Dict, t: float, ease: Callable[[str, float], float]) -> Dict[str, float]:
    """Property values at t (0-1) of a preset, for the page's preview. ``ease(curve_name, x)`` is the easing."""
    segments = preset.get("segments") or []
    if not segments:
        return dict(NEUTRAL)
    t = max(0.0, min(1.0, t))
    total = sum(s.get("span", 1) for s in segments)
    at = 0.0
    seg = segments[-1]
    x = 1.0
    for s in segments:
        span = s.get("span", 1) / total
        if t <= at + span:
            seg, x = s, (t - at) / span if span > 0 else 1.0
            break
        at += span
    out = dict(NEUTRAL)
    for k in RANGES:
        if k in seg:
            a, b = seg[k]
            out[k] = a + (b - a) * ease((seg.get("curves") or {}).get(k, seg.get("curve", "Linear")), x)
    return out


# --------------------------------------------------------------------------- profiles
# A profile names what plays for every event, each with its own speed. Built-ins can't be changed; yours live in
# ~/.config/halos/animation_profiles.json: {"active": "SAINT", "profiles": {"Name": {"open": preset, ...}}}.
# The Animations page only writes kwinrc (apply) when you press Save.
DEFAULT_PROFILE = "SAINT"
_BUILTIN_PROFILES = {                 # event: (preset id, duration ms or None for the preset's own)
    "SAINT": {"open": ("saint-star", None), "close": ("fold", None), "minimize": (SYSTEM, None),
              "desktop": ("glow", None)},
    "Supernova": {"open": ("saint-star", None), "close": ("star-burst", None), "minimize": ("collapse", None),
                  "desktop": ("zoom", None)},
    "Snappy": {"open": ("pop", 150), "close": ("shrink", 130), "minimize": ("collapse", 170),
               "desktop": ("glow", 180)},
    "Calm": {"open": ("fade", 320), "close": ("fade", 320), "minimize": ("fade", 300), "desktop": ("none", None)},
    "Off": {"open": ("none", None), "close": ("none", None), "minimize": (SYSTEM, None), "desktop": ("none", None)},
}


def profiles_file() -> Path:
    return Path(kde.config_home()) / "halos" / "animation_profiles.json"


def builtin_profiles() -> Dict[str, Dict[str, Dict]]:
    return {name: {e: {**tuned(builtin(e, pid), ms), "id": pid} for e, (pid, ms) in events.items()}
            for name, events in _BUILTIN_PROFILES.items()}


def clean_event(preset, event: str) -> Dict:
    """One event of a profile, checked like a custom file. ValueError if it's broken."""
    if not isinstance(preset, dict):
        raise ValueError(f"{event}: not an animation")
    pid = str(preset.get("id") or "custom")
    if pid == SYSTEM and event != "minimize":
        raise ValueError(f"{event}: only minimize can be Plasma's own")
    if pid == SYSTEM or not preset.get("segments"):
        name = preset.get("name") if isinstance(preset.get("name"), str) else "None"
        return {"id": pid, "name": name[:40], "duration": 0, "segments": []}
    out = validate({**preset, "schema": 1, "event": event}, event)
    out.pop("schema", None)
    out.pop("event", None)
    out["id"] = pid
    tune = preset.get("tune")
    if isinstance(tune, dict):
        out["tune"] = {k: int(v) for k, v in tune.items() if k in ("scale", "rotation", "brightness")
                       and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 200}
    return out


def clean_profile(data) -> Dict[str, Dict]:
    if not isinstance(data, dict):
        raise ValueError("a profile is an object")
    return {e: clean_event(data.get(e) or default_preset(e), e) for e in EVENTS}


def check_profile_name(name: str, taken=()) -> str:
    name = (name or "").strip()
    if not _NAME.match(name):
        raise ValueError("name: 1-40 letters, digits, spaces, - or _")
    if name in _BUILTIN_PROFILES:
        raise ValueError(f"“{name}” is a built-in profile")
    if name in taken:
        raise ValueError(f"there's already a profile called “{name}”")
    return name


def load_profiles(path: Optional[Path] = None) -> Tuple[Dict[str, Dict[str, Dict]], str]:
    """(your profiles, the active profile's name). A broken file or profile is skipped and logged."""
    f = Path(path) if path is not None else profiles_file()
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.stat().st_size <= MAX_FILE_BYTES else {}
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    mine = {}
    raw = data.get("profiles")
    for name, prof in (raw.items() if isinstance(raw, dict) else []):
        try:
            if name in _BUILTIN_PROFILES or not _NAME.match(str(name)):
                raise ValueError("bad name")
            mine[name] = clean_profile(prof)
        except ValueError as e:
            log.warning("animation.bad_profile %s: %s", name, e)
    active = data.get("active")
    if active not in mine and active not in _BUILTIN_PROFILES:
        active = DEFAULT_PROFILE
    return mine, active


def save_profiles(mine: Dict[str, Dict[str, Dict]], active: str, path: Optional[Path] = None) -> Path:
    f = Path(path) if path is not None else profiles_file()
    data = {"schema": 1, "active": active, "profiles": {n: clean_profile(p) for n, p in mine.items()}}
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(f)                     # never a half-written file
    return f


def same(a: Dict[str, Dict], b: Dict[str, Dict]) -> bool:
    """Do two sets of event presets play the same thing (what serialise writes, less the page's tune)?"""
    def key(p, e):
        try:
            p = clean_event(p or default_preset(e), e)
        except ValueError:
            pass
        return serialise({k: v for k, v in (p or {}).items() if k not in ("tune", "name")})
    return all(key(a.get(e), e) == key(b.get(e), e) for e in EVENTS)

