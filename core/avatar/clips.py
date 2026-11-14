"""
core/avatar/clips.py

Animation clips for SAINT's full-body avatar, and the builder that lets SAINT make new ones.

A clip is plain JSON data (never code), keyframes over normalised time 0..1:

    {"name": "hello-there", "duration": 2.4, "loop": false, "hold": false,
     "keys": [{"t": 0.0, "pose": {"R": {"upper": [-0.7, 0.3, 0.3], "lower": [0, 1, 0.2]}, "head": [0, -8, -4]}},
              {"t": 1.0, "pose": {...}}]}

A key's ``pose`` overrides only the parts it names, on top of the state pose from core/avatar/body.py:

    L, R        arm directions {"upper": [x, y, z], "lower": [x, y, z]} in model space (+X her left, +Y up, +Z forward)
    head        [pitch, yaw, roll] degrees      spine   [pitch, yaw, roll] degrees
    hips_z      side lean degrees               hips_y  turn degrees          shoulders  shrug degrees
    legs        {"L": [upper_pitch, lower_pitch], "R": [...]} degrees (sitting, climbing, stepping)
    hop         0..1 jump height (the window bobs), scale  0.5..1.5 size pulse (popping in)

``loop`` repeats the clip; ``hold`` keeps a one-shot clip's last pose once it has played (sitting down stays
sitting) until another clip replaces it.

Primitives are short named clips (wave, nod, stretch, climb, ...). ``compose`` strings primitives together into a
new clip; SAINT's ``avatar.create_animation`` action and the behaviour engine use it, so SAINT can build its own
animations without any model call: a model only picks the primitive names. Every clip is validated and clamped
before it is played or saved (a hand-edited or model-written clip can't break the avatar).

Built-in primitives live here; user and SAINT-made clips in <data_dir>/avatar_clips/<name>.json.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional

MAX_KEYS = 64
MAX_DURATION = 30.0
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_VEC_KEYS = ("head", "spine")
_NUM = {"hips_z": (-25, 25), "hips_y": (-180, 180), "shoulders": (-15, 20), "hop": (0, 1), "scale": (0.5, 1.5)}


def _arm(upper, lower):
    return {"upper": list(upper), "lower": list(lower)}


def _mirror(arm):
    return {"upper": [-arm["upper"][0], *arm["upper"][1:]], "lower": [-arm["lower"][0], *arm["lower"][1:]]}


DOWN = _arm((0.22, -0.97, 0.06), (0.12, -0.92, 0.3))
UP_L = _arm((0.35, 0.93, 0.05), (0.2, 0.98, 0.0))
WAVE_UP = _arm((-0.75, 0.25, 0.35), (-0.1, 1.0, 0.25))


def _k(t, **pose):
    return {"t": t, "pose": pose}


# name -> (duration seconds, loop, keys)
PRIMITIVES: Dict[str, dict] = {
    "wave": {"duration": 1.8, "keys": [
        _k(0.0, R=WAVE_UP), _k(0.25, R=_arm((-0.75, 0.25, 0.35), (-0.45, 0.9, 0.2)), head=[-4, -6, -5]),
        _k(0.5, R=_arm((-0.75, 0.25, 0.35), (0.25, 0.95, 0.2))), _k(0.75, R=_arm((-0.75, 0.25, 0.35), (-0.45, 0.9, 0.2))),
        _k(1.0, R=WAVE_UP)]},
    "wave-left": {"duration": 1.8, "keys": [
        _k(0.0, L=_mirror(WAVE_UP)), _k(0.5, L=_mirror(_arm((-0.75, 0.25, 0.35), (0.25, 0.95, 0.2))), head=[-4, 6, 5]),
        _k(1.0, L=_mirror(WAVE_UP))]},
    "nod": {"duration": 0.9, "keys": [_k(0.0, head=[0, 0, 0]), _k(0.35, head=[14, 0, 0]), _k(0.7, head=[-4, 0, 0]),
                                     _k(1.0, head=[0, 0, 0])]},
    "shake-head": {"duration": 1.0, "keys": [_k(0.0, head=[2, 0, 0]), _k(0.25, head=[2, -16, 0]),
                                            _k(0.6, head=[2, 16, 0]), _k(1.0, head=[2, 0, 0])]},
    "bow": {"duration": 1.6, "keys": [_k(0.0, spine=[0, 0, 0]), _k(0.45, spine=[28, 0, 0], head=[18, 0, 0]),
                                     _k(1.0, spine=[0, 0, 0], head=[0, 0, 0])]},
    "stretch": {"duration": 2.6, "keys": [_k(0.0, L=DOWN, R=_mirror(DOWN)), _k(0.4, L=UP_L, R=_mirror(UP_L),
                                                                               spine=[-8, 0, 0], head=[-14, 0, 0]),
                                         _k(0.7, L=UP_L, R=_mirror(UP_L), spine=[-6, 0, 8]),
                                         _k(1.0, L=DOWN, R=_mirror(DOWN), spine=[0, 0, 0], head=[0, 0, 0])]},
    "yawn": {"duration": 2.2, "keys": [_k(0.0), _k(0.3, R=_arm((-0.2, -0.6, 0.75), (0.2, 0.9, 0.4)), head=[-10, 0, 0]),
                                      _k(0.75, R=_arm((-0.2, -0.6, 0.75), (0.2, 0.9, 0.4)), head=[-12, 0, 4]),
                                      _k(1.0, R=_mirror(DOWN), head=[0, 0, 0])]},
    "cheer": {"duration": 1.4, "keys": [_k(0.0, L=DOWN, R=_mirror(DOWN)), _k(0.35, L=UP_L, R=_mirror(UP_L), hop=0.6),
                                       _k(0.6, L=UP_L, R=_mirror(UP_L), hop=0.0), _k(0.8, hop=0.4),
                                       _k(1.0, L=DOWN, R=_mirror(DOWN), hop=0.0)]},
    "clap": {"duration": 1.2, "keys": [_k(i / 6, L=_arm((0.15, -0.6, 0.8), ((-0.5 if i % 2 else -0.2), 0.3, 0.85)),
                                          R=_arm((-0.15, -0.6, 0.8), ((0.5 if i % 2 else 0.2), 0.3, 0.85)))
                                       for i in range(7)]},
    "point-left": {"duration": 1.4, "keys": [_k(0.0), _k(0.4, L=_arm((0.85, 0.1, 0.5), (0.9, 0.15, 0.4)), head=[0, 25, 0]),
                                            _k(1.0, L=_arm((0.85, 0.1, 0.5), (0.9, 0.15, 0.4)), head=[0, 25, 0])]},
    "point-right": {"duration": 1.4, "keys": [_k(0.0), _k(0.4, R=_arm((-0.85, 0.1, 0.5), (-0.9, 0.15, 0.4)),
                                                       head=[0, -25, 0]),
                                             _k(1.0, R=_arm((-0.85, 0.1, 0.5), (-0.9, 0.15, 0.4)), head=[0, -25, 0])]},
    "hop": {"duration": 0.8, "keys": [_k(0.0, hop=0.0), _k(0.45, hop=1.0, legs={"L": [-20, 30], "R": [-20, 30]}),
                                     _k(1.0, hop=0.0)]},
    "spin": {"duration": 1.4, "keys": [_k(0.0, hips_y=0), _k(0.5, hips_y=180), _k(1.0, hips_y=360 - 0.001)]},
    "dance": {"duration": 2.0, "loop": True, "keys": [
        _k(i / 8, hips_z=(8 if i % 2 else -8), hop=(0.25 if i % 2 else 0.0), head=[0, 0, (-8 if i % 2 else 8)],
           L=_arm((0.6, (0.4 if i % 4 < 2 else -0.3), 0.6), (0.5, 0.8, 0.3)),
           R=_arm((-0.6, (-0.3 if i % 4 < 2 else 0.4), 0.6), (-0.5, 0.8, 0.3))) for i in range(9)]},
    "think": {"duration": 2.0, "keys": [_k(0.0), _k(0.3, R=_arm((-0.2, -0.75, 0.62), (0.35, 0.86, 0.38)),
                                                head=[-8, -14, -6]),
                                       _k(1.0, R=_arm((-0.2, -0.75, 0.62), (0.35, 0.86, 0.38)), head=[-6, -10, -6])]},
    "shrug": {"duration": 1.2, "keys": [_k(0.0), _k(0.4, shoulders=12, L=_arm((0.5, -0.82, 0.25), (0.55, 0.05, 0.83)),
                                                R=_mirror(_arm((0.5, -0.82, 0.25), (0.55, 0.05, 0.83)))),
                                       _k(1.0, shoulders=0)]},
    "typing": {"duration": 1.0, "loop": True, "keys": [
        _k(i / 4, head=[14, 0, 0], spine=[6, 0, 0], L=_arm((0.28, -0.75, 0.6), (-0.25, -0.18 + (0.08 if i % 2 else 0), 0.95)),
           R=_arm((-0.28, -0.75, 0.6), (0.25, -0.18 + (0 if i % 2 else 0.08), 0.95))) for i in range(5)]},
    "sit": {"duration": 0.8, "hold": True, "keys": [_k(0.0), _k(1.0, legs={"L": [-80, 85], "R": [-80, 85]}, spine=[4, 0, 0],
                                                L=_arm((0.3, -0.9, 0.3), (0.1, -0.6, 0.8)),
                                                R=_arm((-0.3, -0.9, 0.3), (-0.1, -0.6, 0.8)))]},
    "sit-swing": {"duration": 2.4, "loop": True, "keys": [
        _k(i / 4, legs={"L": [-80, 85 + (20 if i % 2 else -10)], "R": [-80, 85 + (-10 if i % 2 else 20)]},
           spine=[4, 0, 0], head=[6, (8 if i % 2 else -8), 0]) for i in range(5)]},
    "climb": {"duration": 1.6, "loop": True, "keys": [
        _k(0.0, L=UP_L, R=_arm((-0.3, 0.2, 0.9), (-0.2, 0.6, 0.7)), legs={"L": [-50, 70], "R": [-10, 10]}, hop=0.0),
        _k(0.5, R=_mirror(UP_L), L=_arm((0.3, 0.2, 0.9), (0.2, 0.6, 0.7)), legs={"L": [-10, 10], "R": [-50, 70]},
           hop=0.5),
        _k(1.0, L=UP_L, R=_arm((-0.3, 0.2, 0.9), (-0.2, 0.6, 0.7)), legs={"L": [-50, 70], "R": [-10, 10]}, hop=1.0)]},
    "peek": {"duration": 2.4, "keys": [_k(0.0, hips_z=0, head=[0, 0, 0]), _k(0.35, hips_z=-14, head=[0, 18, -12]),
                                      _k(0.7, hips_z=-14, head=[-4, 22, -12]), _k(1.0, hips_z=0, head=[0, 0, 0])]},
    "pop-in": {"duration": 0.7, "keys": [_k(0.0, scale=0.5, hop=0.0), _k(0.5, scale=1.15, hop=0.5),
                                        _k(0.75, scale=0.95, hop=0.1), _k(1.0, scale=1.0, hop=0.0)]},
    "glance": {"duration": 1.6, "keys": [_k(0.0, head=[0, 0, 0]), _k(0.25, head=[6, 24, 4]), _k(0.55, head=[12, 22, 4]),
                                        _k(0.7, head=[2, 20, 2]), _k(1.0, head=[0, 0, 0])]},
    "look-around": {"duration": 3.2, "keys": [_k(0.0, head=[0, 0, 0]), _k(0.25, head=[-4, 26, 3], hips_z=3),
                                             _k(0.5, head=[-2, 0, 0], hips_z=0), _k(0.75, head=[-4, -26, -3], hips_z=-3),
                                             _k(1.0, head=[0, 0, 0], hips_z=0)]},
    "sleepy": {"duration": 3.0, "loop": True, "keys": [_k(0.0, head=[18, 0, 6], spine=[8, 0, 0]),
                                                      _k(0.5, head=[26, 0, 10], spine=[10, 0, 0]),
                                                      _k(1.0, head=[18, 0, 6], spine=[8, 0, 0])]},
}
SIT_LEGS = {"L": [-80, 85], "R": [-80, 85]}      # her legs while she sits on a window's top edge
SIT_POSE = {"legs": SIT_LEGS, "hips_y": 25.0}  # the base pose then: turned a little, so the sit reads from the front
PRIMITIVES.update({
    # a step cycle for walking along the taskbar; the window moves, ui/avatar turns her the way she walks
    "walk": {"duration": 1.0, "loop": True, "keys": [
        _k(i / 4, legs={"L": [(-28, 0, 22, 0, -28)[i], (8, 30, 12, 30, 8)[i]],
                        "R": [(22, 0, -28, 0, 22)[i], (12, 30, 8, 30, 12)[i]]},
           L=_arm((0.22, -0.96, (-0.28, 0, 0.28, 0, -0.28)[i]), (0.12, -0.9, 0.35)),
           R=_arm((-0.22, -0.96, (0.28, 0, -0.28, 0, 0.28)[i]), (-0.12, -0.9, 0.35)),
           hop=(0.0, 0.12, 0.0, 0.12, 0.0)[i], spine=[4, 0, 0], head=[2, 0, 0]) for i in range(5)]},
    # "Hey SAINT": leans in, a hand cupped by her ear, then holds it while she listens
    "listen": {"duration": 1.0, "hold": True, "keys": [
        _k(0.0), _k(1.0, R=_arm((-0.55, -0.55, 0.45), (0.5, 0.85, -0.1)), head=[4, -8, 10], spine=[5, 0, 0])]},
    # popping up from the bottom of the screen: a little crouch, a jump and a landing
    "pop-up": {"duration": 0.9, "keys": [
        _k(0.0, legs={"L": [-45, 70], "R": [-45, 70]}, hop=0.0, L=UP_L, R=_mirror(UP_L)),
        _k(0.45, legs={"L": [-10, 15], "R": [-10, 15]}, hop=0.8),
        _k(0.75, legs={"L": [-30, 45], "R": [-30, 45]}, hop=0.0, L=DOWN, R=_mirror(DOWN)),
        _k(1.0, legs={"L": [0, 0], "R": [0, 0]}, hop=0.0)]},
    # dancing on a window's top edge: bobbing knees, one bob per beat (ui/avatar sets the speed from the tempo)
    "bob": {"duration": 1.0, "loop": True, "keys": [
        _k(i / 4, legs={"L": [(-18 if i % 2 else 0), (30 if i % 2 else 0)],
                        "R": [(-18 if i % 2 else 0), (30 if i % 2 else 0)]},
           hips_z=(5 if i in (1, 2) else -5), head=[(6 if i % 2 else 0), 0, (6 if i in (1, 2) else -6)],
           L=_arm((0.45, -0.75, 0.45), (0.2, (0.6 if i % 2 else 0.9), 0.4)),
           R=_arm((-0.45, -0.75, 0.45), (-0.2, (0.9 if i % 2 else 0.6), 0.4))) for i in range(5)]},
})
for _name, _c in PRIMITIVES.items():
    _c.setdefault("loop", False)
    _c.setdefault("hold", False)
    _c["name"] = _name


class ClipError(ValueError):
    """A clip that can't be played; the message is shown to the user."""


# ---------------------------------------------------------------- validation
def _clampf(v, lo, hi) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ClipError(f"{v!r} isn't a number")
    if math.isnan(f) or math.isinf(f):
        raise ClipError("numbers must be finite")
    return max(lo, min(hi, f))


def _vec(v, n=3, lo=-1.0, hi=1.0) -> List[float]:
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise ClipError(f"expected {n} numbers")
    return [_clampf(c, lo, hi) for c in v]


def clean_pose(p) -> dict:
    if not isinstance(p, dict):
        raise ClipError("a key's pose must be an object")
    out = {}
    for side in ("L", "R"):
        if side in p:
            arm = p[side]
            if not isinstance(arm, dict) or set(arm) - {"upper", "lower"} or not {"upper", "lower"} <= set(arm):
                raise ClipError(f"{side} needs upper and lower directions")
            out[side] = {k: _vec(arm[k], 3, -1.5, 1.5) for k in ("upper", "lower")}
            for k, d in out[side].items():
                if sum(c * c for c in d) < 1e-4:
                    raise ClipError(f"{side} {k} direction is zero")
    for k in _VEC_KEYS:
        if k in p:
            out[k] = _vec(p[k], 3, -60, 60)
    for k, (lo, hi) in _NUM.items():
        if k in p:
            out[k] = _clampf(p[k], lo, hi)
    if "legs" in p:
        legs = p["legs"]
        if not isinstance(legs, dict) or set(legs) - {"L", "R"}:
            raise ClipError("legs must be {L: [upper, lower], R: [...]}")
        out["legs"] = {s: _vec(legs[s], 2, -120, 120) for s in legs}
    unknown = set(p) - set(out)
    if unknown:
        raise ClipError(f"unknown pose part {sorted(unknown)[0]!r}")
    return out


def validate(clip) -> dict:
    """A clean copy of ``clip`` or ClipError."""
    if not isinstance(clip, dict):
        raise ClipError("a clip must be an object")
    name = str(clip.get("name", "")).strip().lower()
    if not _NAME.match(name):
        raise ClipError("name: 1-40 lowercase letters, digits or '-'")
    keys = clip.get("keys")
    if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_KEYS:
        raise ClipError(f"keys: 1-{MAX_KEYS} keyframes")
    out_keys, last = [], -1.0
    for k in keys:
        if not isinstance(k, dict):
            raise ClipError("each key must be an object")
        t = _clampf(k.get("t", 0), 0, 1)
        if t < last:
            raise ClipError("keys must be in time order")
        last = t
        out_keys.append({"t": t, "pose": clean_pose(k.get("pose", {}))})
    return {"name": name, "duration": _clampf(clip.get("duration", 2.0), 0.2, MAX_DURATION),
            "loop": bool(clip.get("loop", False)), "hold": bool(clip.get("hold", False)), "keys": out_keys}


# ---------------------------------------------------------------- sampling
def _lerp(a, b, f):
    if isinstance(a, dict):
        return {k: _lerp(a[k], b[k], f) if k in b else a[k] for k in a}
    if isinstance(a, list):
        return [x + (y - x) * f for x, y in zip(a, b)]
    return a + (b - a) * f


def _ease(f: float) -> float:
    return f * f * (3 - 2 * f)


def sample(clip: dict, elapsed: float) -> Optional[dict]:
    """The pose overrides at ``elapsed`` seconds, or None when a non-looping clip has ended (a ``hold`` clip keeps
    its last pose instead)."""
    d = clip["duration"]
    if elapsed >= d and not clip["loop"]:
        return dict(clip["keys"][-1]["pose"]) if clip.get("hold") else None
    u = (elapsed % d) / d if clip["loop"] else max(0.0, elapsed / d)
    keys = clip["keys"]
    if u <= keys[0]["t"]:
        return dict(keys[0]["pose"])
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= u <= b["t"]:
            span = b["t"] - a["t"]
            f = _ease((u - a["t"]) / span) if span > 0 else 1.0
            pose = dict(a["pose"])
            for part, val in b["pose"].items():
                pose[part] = _lerp(pose[part], val, f) if part in pose and type(pose[part]) is type(val) else val
            return pose
    return dict(keys[-1]["pose"])


# ---------------------------------------------------------------- the builder
def compose(primitives: List[str], name: str, speed: float = 1.0, loop: bool = False) -> dict:
    """A new clip that plays the named primitives one after another (each keeps its own timing)."""
    if not primitives or len(primitives) > 12:
        raise ClipError("choose 1-12 moves")
    missing = [p for p in primitives if p not in PRIMITIVES]
    if missing:
        raise ClipError(f"unknown move {missing[0]!r}; known: {', '.join(sorted(PRIMITIVES))}")
    speed = _clampf(speed, 0.25, 4.0)
    total = sum(PRIMITIVES[p]["duration"] for p in primitives) / speed
    keys, start = [], 0.0
    for p in primitives:
        prim = PRIMITIVES[p]
        span = prim["duration"] / speed / total
        for k in prim["keys"]:
            keys.append({"t": round(start + k["t"] * span, 4), "pose": k["pose"]})
        start += span
    if len(keys) > MAX_KEYS:                     # keep every primitive's first and last key, thin the middle
        step = len(keys) / MAX_KEYS
        keys = [keys[int(i * step)] for i in range(MAX_KEYS - 1)] + [keys[-1]]
    return validate({"name": name, "duration": min(MAX_DURATION, total), "loop": loop, "keys": keys})


# ---------------------------------------------------------------- library on disk
def clips_dir() -> Path:
    from core.paths import data_dir
    d = data_dir() / "avatar_clips"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(clip: dict, folder: Optional[Path] = None) -> dict:
    clip = validate(clip)
    if clip["name"] in PRIMITIVES:
        raise ClipError(f"{clip['name']} is a built-in move; pick another name")
    folder = folder or clips_dir()
    tmp = folder / f"{clip['name']}.json.tmp"
    tmp.write_text(json.dumps(clip, indent=1), encoding="utf-8")
    tmp.replace(folder / f"{clip['name']}.json")
    return clip


def remove(name: str, folder: Optional[Path] = None) -> bool:
    if not _NAME.match(str(name)):
        return False
    p = (folder or clips_dir()) / f"{name}.json"
    if p.is_file():
        p.unlink()
        return True
    return False


def saved(folder: Optional[Path] = None) -> Dict[str, dict]:
    out = {}
    for p in sorted((folder or clips_dir()).glob("*.json")):
        try:
            c = validate(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
        out[c["name"]] = c
    return out


def get(name: str, folder: Optional[Path] = None) -> Optional[dict]:
    name = str(name or "").strip().lower()
    if name in PRIMITIVES:
        return validate(PRIMITIVES[name])
    return saved(folder).get(name)


def names(folder: Optional[Path] = None) -> List[str]:
    return sorted(PRIMITIVES) + sorted(saved(folder))
