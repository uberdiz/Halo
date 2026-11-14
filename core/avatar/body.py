"""
core/avatar/body.py

Full-body animation for a VRoid/VRM humanoid (bones J_Bip_*), procedural and deterministic so it is tested
without a GPU. Each SAINT state has an *activity*: a pose made of arm directions and spine/head angles plus a
little motion on top (breathing, weight shift, typing, waving, nodding). ``BodyDriver.step`` eases from pose to
pose and returns, per bone, a rotation quaternion (w, x, y, z) in the bone's parent frame that the QML scene
pre-multiplies onto the bone's rest rotation.

Model space: +X is the model's left, +Y up, +Z forward (towards the viewer). The rest pose is a T-pose whose bones
are near-identity, so "the left upper arm points along +X" at rest.

    idle       relaxed, breathing, slow weight shift, looks around now and then
    listening  leans in, head tilted, hands loosely together
    thinking   right hand to chin, eyes and head up and aside
    planning   gestures to her right, where the plan cards float
    working    types on a floating keyboard, head slightly down
    speaking   open-hand gestures that follow the voice level, small nods
    success    waves      ·  warning: raises a hand  ·  error: shrugs, small head shake
    offline    rests: head down, arms hanging

On top of the state pose: a *base pose* (sitting on a window's edge, turned the way she walks) under the clip
that's playing, and a *look* (yaw, pitch degrees: + is to the screen's right / down) that turns her head and eyes
towards the cursor or the text being typed.
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from core.avatar import AvatarState

Quat = Tuple[float, float, float, float]
Vec = Tuple[float, float, float]


# --------------------------------------------------------------------------- tiny quaternion maths
def q_mul(a: Quat, b: Quat) -> Quat:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


def q_conj(q: Quat) -> Quat:
    return (q[0], -q[1], -q[2], -q[3])


def q_rotate(q: Quat, v: Vec) -> Vec:
    r = q_mul(q_mul(q, (0.0, *v)), q_conj(q))
    return (r[1], r[2], r[3])


def q_axis(axis: Vec, deg: float) -> Quat:
    h = math.radians(deg) / 2
    n = math.sqrt(sum(c * c for c in axis)) or 1.0
    s = math.sin(h) / n
    return (math.cos(h), axis[0] * s, axis[1] * s, axis[2] * s)


def q_euler(x: float = 0, y: float = 0, z: float = 0) -> Quat:
    return q_mul(q_mul(q_axis((0, 1, 0), y), q_axis((1, 0, 0), x)), q_axis((0, 0, 1), z))


def q_between(a: Vec, b: Vec) -> Quat:
    """Shortest rotation taking direction a onto direction b."""
    na, nb = math.sqrt(sum(c * c for c in a)), math.sqrt(sum(c * c for c in b))
    a, b = tuple(c / na for c in a), tuple(c / nb for c in b)
    d = sum(x * y for x, y in zip(a, b))
    if d < -0.9999:                                   # opposite: any perpendicular axis
        return q_axis((0, 0, 1) if abs(a[0]) > 0.5 else (1, 0, 0), 180)
    cx = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    q = (1 + d, *cx)
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)                    # type: ignore[return-value]


def q_slerp(a: Quat, b: Quat, t: float) -> Quat:
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = tuple(-c for c in b), -d               # type: ignore[assignment]
    if d > 0.9995:
        q = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        th = math.acos(d)
        s = math.sin(th)
        q = tuple(x * math.sin((1 - t) * th) / s + y * math.sin(t * th) / s for x, y in zip(a, b))
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)                    # type: ignore[return-value]


IDENTITY: Quat = (1.0, 0.0, 0.0, 0.0)


# --------------------------------------------------------------------------- poses
def _mirror(v: Vec) -> Vec:
    return (-v[0], v[1], v[2])


RELAXED = {"upper": (0.22, -0.97, 0.06), "lower": (0.12, -0.92, 0.3)}       # left side; right is mirrored


def pose(state: AvatarState, t: float, level: float) -> Dict[str, object]:
    """Target pose: arm directions (model space) and spine/neck/head/shoulder euler angles (degrees)."""
    s = math.sin
    L = dict(RELAXED)
    R = {"upper": _mirror(RELAXED["upper"]), "lower": _mirror(RELAXED["lower"])}
    spine = [0.0, 0.0, 0.0]
    head = [0.0, 6 * s(t * 0.21) + 3 * s(t * 0.53), 0.0]                     # looks around a little
    hips_z = 1.6 * s(t * 0.35)                                                 # weight shift
    shoulders = 0.0
    breath = 1.2 * s(t * 1.7)
    hand_tap = 0.0

    if state == AvatarState.LISTENING:
        spine[0], head = 5.0, [4.0, 4 * s(t * 0.4), 9.0]
        L = {"upper": (0.12, -0.9, 0.42), "lower": (-0.55, -0.1, 0.83)}
        R = {"upper": _mirror(L["upper"]), "lower": _mirror(L["lower"])}
    elif state == AvatarState.THINKING:
        head = [-8.0, -14 + 3 * s(t * 0.3), -6.0]
        R = {"upper": (-0.2, -0.75, 0.62), "lower": (0.35, 0.86, 0.38)}       # hand to chin
        L = {"upper": (0.15, -0.88, 0.45), "lower": (-0.6, 0.1, 0.8)}        # arm across, supporting the elbow
    elif state == AvatarState.PLANNING:
        head = [2.0, -22.0, 0.0]
        R = {"upper": (-0.75, -0.05 + 0.08 * s(t * 1.2), 0.66), "lower": (-0.8, 0.15, 0.58)}   # points to the cards
        L = {"upper": (0.2, -0.9, 0.38), "lower": (0.05, -0.35, 0.94)}
    elif state == AvatarState.WORKING:
        spine[0], head = 6.0, [14.0, 3 * s(t * 0.5), 0.0]
        L = {"upper": (0.28, -0.75, 0.6), "lower": (-0.25, -0.18, 0.95)}
        R = {"upper": _mirror(L["upper"]), "lower": _mirror(L["lower"])}
        hand_tap = 1.0
    elif state == AvatarState.SPEAKING:
        g = max(0.0, s(t * 2.1)) * (0.35 + level)                           # open-hand beats with the voice
        L = {"upper": (0.25, -0.88, 0.38), "lower": (0.25, -0.2 + 0.6 * g, 0.9)}
        R = {"upper": (-0.25, -0.9, 0.3), "lower": (-0.15, -0.55 + 0.4 * max(0.0, s(t * 1.7 + 1)), 0.8)}
        head = [3 * s(t * 3.1) * (0.3 + level), 4 * s(t * 0.6), 2 * s(t * 0.9)]
    elif state == AvatarState.SUCCESS:
        R = {"upper": (-0.75, 0.25, 0.35), "lower": (-0.1 + 0.35 * s(t * 7.0), 1.0, 0.25)}  # waves
        head = [-4.0, -6.0, -5.0]
    elif state == AvatarState.WARNING:
        L = {"upper": (0.25, -0.35, 0.9), "lower": (0.05, 0.9, 0.42)}       # raised hand: "hold on"
        head, spine[0] = [6.0, 0.0, 0.0], 3.0
    elif state == AvatarState.ERROR:
        L = {"upper": (0.5, -0.82, 0.25), "lower": (0.55, 0.05, 0.83)}      # shrug, palms up
        R = {"upper": _mirror(L["upper"]), "lower": _mirror(L["lower"])}
        shoulders, head = 7.0, [5.0, 10 * s(t * 5.0), 0.0]
    elif state == AvatarState.OFFLINE:
        head, spine[0], breath = [24.0, 0.0, 0.0], 8.0, 0.5 * s(t * 1.0)
        L = {"upper": (0.12, -0.99, 0.04), "lower": (0.08, -0.99, 0.08)}
        R = {"upper": _mirror(L["upper"]), "lower": _mirror(L["lower"])}
        hips_z = 0.0
    return {"L": L, "R": R, "spine": spine, "head": head, "hips_z": hips_z, "shoulders": shoulders,
            "breath": breath, "tap": hand_tap, "hips_y": 0.0, "legs": {}}


def overlay(p: Dict[str, object], over: Optional[Dict[str, object]]) -> Dict[str, object]:
    """A clip's pose overrides (core/avatar/clips.py) on top of the state pose. Arms are replaced per side; a clip
    that moves the arms also stops the typing tap."""
    if not over:
        return p
    out = dict(p)
    for k, v in over.items():
        if k in ("L", "R"):
            out[k] = {"upper": tuple(v["upper"]), "lower": tuple(v["lower"])}
            out["tap"] = 0.0
        elif k in ("head", "spine"):
            out[k] = list(v)
        elif k == "legs":
            out["legs"] = dict(v)
        elif k not in ("hop", "scale"):          # hop and scale move the window, not bones (ui/avatar)
            out[k] = v
    return out


def rotations(p: Dict[str, object], t: float, intensity: float = 1.0) -> Dict[str, Quat]:
    """Pose -> per-bone rotations in the parent frame (to pre-multiply onto the rest rotation)."""
    k = max(0.0, min(1.5, intensity))
    out: Dict[str, Quat] = {}
    sp = p["spine"]
    out["J_Bip_C_Hips"] = q_euler(y=p.get("hips_y", 0.0), z=p["hips_z"] * k)
    for side in ("L", "R"):                           # legs only while a clip bends them (sitting, climbing, hops)
        upper, lower = (p.get("legs") or {}).get(side, (0.0, 0.0))
        out[f"J_Bip_{side}_UpperLeg"] = q_euler(x=upper)
        out[f"J_Bip_{side}_LowerLeg"] = q_euler(x=lower)
    out["J_Bip_C_Spine"] = q_euler(x=sp[0] * 0.4 * k, z=-p["hips_z"] * 0.6 * k)
    out["J_Bip_C_Chest"] = q_euler(x=(sp[0] * 0.35 - p["breath"]) * k)
    out["J_Bip_C_UpperChest"] = q_euler(x=(sp[0] * 0.25 + p["breath"] * 0.6) * k)
    h = p["head"]
    out["J_Bip_C_Neck"] = q_euler(x=h[0] * 0.4 * k, y=h[1] * 0.4 * k, z=h[2] * 0.4 * k)
    out["J_Bip_C_Head"] = q_euler(x=h[0] * 0.6 * k, y=h[1] * 0.6 * k, z=h[2] * 0.6 * k)
    yaw, pitch = p.get("eyes", (0.0, 0.0))             # the eyes follow the look, a little ahead of the head
    for side in ("L", "R"):
        out[f"J_Adj_{side}_FaceEye"] = q_euler(x=_clamp(pitch * 0.3, 8), y=_clamp(yaw * 0.35, 12))
    out["J_Bip_L_Shoulder"] = q_euler(z=p["shoulders"] * k)
    out["J_Bip_R_Shoulder"] = q_euler(z=-p["shoulders"] * k)
    for side, rest_dir in (("L", (1.0, 0.0, 0.0)), ("R", (-1.0, 0.0, 0.0))):
        arm = p[side]
        qu = q_between(rest_dir, arm["upper"])
        out[f"J_Bip_{side}_UpperArm"] = qu
        # the forearm's rest direction in its parent's (rotated upper arm's) frame is rest_dir as well
        local_target = q_rotate(q_conj(qu), arm["lower"])
        out[f"J_Bip_{side}_LowerArm"] = q_between(rest_dir, local_target)
        tap = p["tap"] * 12 * math.sin(t * 11 + (0 if side == "L" else 1.7))
        out[f"J_Bip_{side}_Hand"] = q_euler(x=tap * k)
    return out


def _clamp(v: float, lim: float) -> float:
    return max(-lim, min(lim, float(v)))


LOOK_YAW, LOOK_PITCH = 35.0, 20.0          # how far the head turns to look at something


def look_angles(dx: float, dy: float, depth: float = 900.0) -> Tuple[float, float]:
    """Head (yaw, pitch) degrees towards a point ``dx``, ``dy`` screen pixels from her eyes (+ right / down)."""
    return (_clamp(math.degrees(math.atan2(dx, depth)), LOOK_YAW * 1.6),
            _clamp(math.degrees(math.atan2(dy, depth)), LOOK_PITCH * 1.6))


def with_look(p: Dict[str, object], look: Optional[Tuple[float, float]], clip_head: bool) -> Dict[str, object]:
    """Turn the pose's head towards ``look``; less when a clip moves the head itself (a nod still reads)."""
    if not look:
        return p
    yaw, pitch = look
    w = 0.35 if clip_head else 0.8
    head = list(p["head"])
    head[1] = _clamp(head[1] + _clamp(yaw, LOOK_YAW) * w, 60)
    head[0] = _clamp(head[0] + _clamp(pitch, LOOK_PITCH) * w, 60)
    return dict(p, head=head, eyes=(yaw, pitch))


class BodyDriver:
    """Eases from the current pose to the state's pose (~0.4 s) and returns this frame's bone rotations."""

    def __init__(self):
        self.current: Dict[str, Quat] = {}

    def step(self, state: AvatarState, t: float, level: float, dt: float,
             intensity: float = 1.0, clip_pose: Optional[Dict[str, object]] = None,
             base_pose: Optional[Dict[str, object]] = None,
             look: Optional[Tuple[float, float]] = None) -> Dict[str, Quat]:
        p = overlay(overlay(pose(state, t, level), base_pose), clip_pose)
        p = with_look(p, look, bool(clip_pose and "head" in clip_pose))
        target = rotations(p, t, intensity)
        a = 1 - math.exp(-dt / 0.18)
        for bone, q in target.items():
            self.current[bone] = q_slerp(self.current.get(bone, q), q, a)
        return dict(self.current)
