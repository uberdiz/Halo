"""
SAINT_3D/source/scripts/saint_clips.py

SAINT's hand-authored animation clips: keyframed in Blender on the shipped VRoid rig, exported as clip JSON for
core/avatar/clips.py (data/avatars/saint/clips/<name>.json, which override the procedural clip of the same name).

Run inside Blender (Scripting tab, or Blender MCP) with SAINT_clips.blend open, or an empty file:

    ns = {}; p = r"<repo>/SAINT_3D/source/scripts/saint_clips.py"; exec(compile(open(p).read(), p, "exec"), ns)
    ns["build"]()        # empty file: imports data/avatars/saint/saint.vrm and (re)makes every Action from CLIPS
    ns["export"]()       # samples every SAINT action and writes the JSON clips

To tweak a clip, edit its Action ("saint:<name>") in the Graph Editor / Pose Mode and run export() again;
build() would overwrite hand edits with CLIPS below.

Conventions (the runtime's, core/avatar/body.py): model space +X her left, +Y up, +Z forward. Blender has her
facing -Y with Z up, so model = (bx, bz, -by). Every authored value is a parent-relative rotation in model axes
as euler degrees (x pitch: + leans/nods forward, y yaw: + turns to her left, z roll: + tips to her right) applied
y * x * z like body.q_euler; arms are given as directions like body.py (upper arm, forearm), right-side values
written as their left mirror. The exporter reads the *evaluated* pose, so hand edits on any bone export correctly.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

FPS = 30
SAMPLES_PER_S = 20                         # exported keys per second (clips.py interpolates linearly between them)
C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))     # Blender armature axes -> model axes
REPO = Path(bpy.data.filepath).resolve().parents[2] if bpy.data.filepath else Path(__file__).resolve().parents[3]
VRM = REPO / "data" / "avatars" / "saint" / "saint.vrm"
OUT = REPO / "data" / "avatars" / "saint" / "clips"

BONES = {"hips": "J_Bip_C_Hips", "spine": "J_Bip_C_Spine", "chest": "J_Bip_C_Chest", "upperChest": "J_Bip_C_UpperChest",
         "neck": "J_Bip_C_Neck", "head": "J_Bip_C_Head", "shoulderL": "J_Bip_L_Shoulder", "shoulderR": "J_Bip_R_Shoulder",
         "upperArmL": "J_Bip_L_UpperArm", "lowerArmL": "J_Bip_L_LowerArm", "handL": "J_Bip_L_Hand",
         "upperArmR": "J_Bip_R_UpperArm", "lowerArmR": "J_Bip_R_LowerArm", "handR": "J_Bip_R_Hand",
         "upperLegL": "J_Bip_L_UpperLeg", "lowerLegL": "J_Bip_L_LowerLeg", "footL": "J_Bip_L_Foot",
         "upperLegR": "J_Bip_R_UpperLeg", "lowerLegR": "J_Bip_R_LowerLeg", "footR": "J_Bip_R_Foot"}


# ============================================================================ the clips
# Each clip: duration (s), loop / hold flags, and channels -> [(t 0..1, value)]. Loops get their t=1 key from t=0.
RELAX = ((0.22, -0.97, 0.06), (0.12, -0.92, 0.3))
RELAX2 = ((0.2, -0.97, 0.12), (0.1, -0.86, 0.45))
UP = ((0.35, 0.93, 0.05), (0.2, 0.98, 0.0))
SIT_HANDS = ((0.3, -0.9, 0.3), (0.1, -0.6, 0.8))
GROOVE = ((0.42, -0.82, 0.38), (0.15, 0.25, 0.95))


def sym(ch, part, keys):
    """The same keys on both sides (the right side mirrors itself when keyed)."""
    ch[part + "L"] = keys
    ch[part + "R"] = list(keys)
    return ch


def spine3(ch, keys):
    """A whole-spine bend split over spine / chest / upper chest like the runtime does (0.4, 0.35, 0.25)."""
    for part, w in (("spine", 0.4), ("chest", 0.35), ("upperChest", 0.25)):
        ch[part] = [(t, tuple(c * w for c in v)) for t, v in keys]
    return ch


def neckhead(ch, keys, lag=0.03):
    """Neck leads, the head follows ``lag`` later (overlapping action); the totals are what's exported."""
    ch["neck"] = [(t, tuple(c * 0.4 for c in v)) for t, v in keys]
    ch["head"] = [(min(1.0, t + lag) if 0 < t < 1 else t, tuple(c * 0.6 for c in v)) for t, v in keys]
    return ch


def legs(ch, keys_l, keys_r=None):
    """keys: [(t, (upper_pitch, lower_pitch))] like clips.py legs."""
    for side, keys in (("L", keys_l), ("R", keys_r or keys_l)):
        ch["upperLeg" + side] = [(t, (u, 0, 0)) for t, (u, _l) in keys]
        ch["lowerLeg" + side] = [(t, (lo, 0, 0)) for t, (_u, lo) in keys]
    return ch


def clip(dur, loop=False, hold=False, **ch):
    return {"duration": dur, "loop": loop, "hold": hold, "ch": ch}


def _idle_breathe():
    ch = {"hips": [(0, (0, 0, -1.5)), (0.5, (0, 0, 1.5))]}
    spine3(ch, [(0, (0, 0, 1.0)), (0.3, (-2.5, 0, 0)), (0.55, (-1.0, 0, -1.0)), (0.8, (0.5, 0, 0))])
    neckhead(ch, [(0, (1, 2, 0)), (0.35, (-1.5, 4, -1)), (0.65, (1.5, -1, 1)), (0.85, (0.5, 0, 0))], lag=0.06)
    sym(ch, "shoulder", [(0, (0, 0, 0)), (0.32, (0, 0, 2.5)), (0.6, (0, 0, 0))])
    sym(ch, "arm", [(0, RELAX), (0.4, ((0.23, -0.96, 0.1), (0.13, -0.88, 0.38))), (0.7, RELAX2)])
    return clip(4.0, loop=True, **ch)


def _wave():
    ch = {"armL": [(0, RELAX), (0.3, RELAX2), (0.85, RELAX2), (1, RELAX)]}
    ch["armR"] = [(0, RELAX), (0.1, ((0.3, -0.94, -0.12), (0.15, -0.95, 0.1))),                  # anticipation
                  (0.26, ((0.8, 0.3, 0.4), (0.2, 1.0, 0.3))), (0.32, ((0.75, 0.25, 0.35), (0.05, 1.0, 0.25))),
                  (0.4, ((0.75, 0.27, 0.35), (0.5, 0.88, 0.2))), (0.5, ((0.74, 0.24, 0.36), (-0.3, 0.95, 0.2))),
                  (0.6, ((0.75, 0.27, 0.35), (0.48, 0.88, 0.2))), (0.7, ((0.74, 0.24, 0.36), (-0.25, 0.95, 0.2))),
                  (0.78, ((0.75, 0.25, 0.35), (0.15, 1.0, 0.25))), (0.9, ((0.35, -0.9, 0.2), (0.3, -0.7, 0.6))),
                  (1.0, RELAX)]
    ch["shoulderR"] = [(0, (0, 0, 0)), (0.1, (0, 0, -2)), (0.3, (0, 0, 5)), (0.78, (0, 0, 4)), (1, (0, 0, 0))]
    spine3(ch, [(0, (0, 0, 0)), (0.12, (2, 0, -1)), (0.32, (-2, -4, 4)), (0.78, (-1, -3, 3)), (1, (0, 0, 0))])
    neckhead(ch, [(0, (0, 0, 0)), (0.14, (3, 0, 0)), (0.34, (-5, -6, 7)), (0.55, (-3, -4, 5)), (0.8, (-4, -5, 6)),
                  (1, (0, 0, 0))], lag=0.05)
    ch["hips"] = [(0, (0, 0, 0)), (0.3, (0, 0, -2.5)), (0.8, (0, 0, -2)), (1, (0, 0, 0))]
    return clip(1.8,  # as long as the procedural wave (compose timings)
                **ch)


SIT_UP, SIT_LO = -80.0, 85.0                   # must match clips.SIT_LEGS (the base pose she keeps while sitting)


def _sit():
    ch = legs({}, [(0, (0, 0)), (0.3, (-30, 40)), (0.7, (-86, 92)), (0.85, (-79, 84)), (1, (SIT_UP, SIT_LO))])
    spine3(ch, [(0, (0, 0, 0)), (0.35, (12, 0, 0)), (0.75, (2, 0, 0)), (1, (4, 0, 0))])
    neckhead(ch, [(0, (0, 0, 0)), (0.3, (8, 0, 0)), (0.75, (-3, 0, 0)), (1, (2, 0, 0))], lag=0.06)
    sym(ch, "arm", [(0, RELAX), (0.35, ((0.32, -0.88, -0.35), (0.2, -0.9, 0.2))),               # hands back to sit
                    (0.75, ((0.32, -0.9, 0.25), (0.1, -0.6, 0.82))), (1, SIT_HANDS)])
    return clip(0.8, hold=True, **ch)


def _sit_swing():
    lo = lambda a: (SIT_UP, SIT_LO + a)
    ch = legs({}, [(0, lo(-10)), (0.25, lo(22)), (0.5, lo(-10)), (0.75, lo(22))],
              [(0, lo(18)), (0.27, lo(-12)), (0.52, lo(18)), (0.77, lo(-12))])
    ch["upperLegL"] = [(0, (SIT_UP, 0, 0)), (0.25, (SIT_UP - 3, 0, 0)), (0.5, (SIT_UP, 0, 0)), (0.75, (SIT_UP - 3, 0, 0))]
    spine3(ch, [(0, (4, 0, -1.5)), (0.25, (5, 2, 0)), (0.5, (4, 0, 1.5)), (0.75, (5, -2, 0))])
    neckhead(ch, [(0, (6, -8, 3)), (0.25, (8, 0, 0)), (0.5, (6, 8, -3)), (0.75, (8, 0, 0))], lag=0.07)
    sym(ch, "arm", [(0, SIT_HANDS), (0.5, ((0.3, -0.9, 0.33), (0.1, -0.62, 0.78)))])
    return clip(2.4, loop=True, **ch)


def _walk():
    l_up = [(0, -25), (0.12, -18), (0.25, 0), (0.5, 20), (0.62, 12), (0.75, -12), (0.9, -27)]
    l_lo = [(0, 5), (0.12, 16), (0.25, 8), (0.5, 18), (0.6, 45), (0.75, 55), (0.9, 18)]
    ch = {"upperLegL": [(t, (v, 0, 0)) for t, v in l_up], "lowerLegL": [(t, (v, 0, 0)) for t, v in l_lo],
          "upperLegR": [((t + 0.5) % 1, (v, 0, 0)) for t, v in l_up], "lowerLegR": [((t + 0.5) % 1, (v, 0, 0)) for t, v in l_lo]}
    for k in ("upperLegR", "lowerLegR"):
        ch[k].sort()
    swing = lambda z: ((0.22, -0.95, z), (0.12, -0.86, 0.35 + max(0.0, z)))
    ch["armL"] = [(0.05, swing(-0.3)), (0.55, swing(0.32))]        # opposite to the left leg, a little late
    ch["armR"] = [(0.05, swing(0.32)), (0.55, swing(-0.3))]
    ch["hips"] = [(0, (0, 0, 0)), (0.12, (0, 0, -2.5)), (0.5, (0, 0, 0)), (0.62, (0, 0, 2.5))]
    spine3(ch, [(0, (4, -4, 0)), (0.12, (5, -3, 1)), (0.5, (4, 4, 0)), (0.62, (5, 3, -1))])
    neckhead(ch, [(0, (1, 3, 0)), (0.14, (3, 2, -1)), (0.5, (1, -3, 0)), (0.64, (3, -2, 1))], lag=0.04)
    ch["hop"] = [(0, 0.0), (0.12, 0.0), (0.27, 0.12), (0.5, 0.0), (0.62, 0.0), (0.77, 0.12)]
    return clip(1.0, loop=True, **ch)


def _dance():
    # 120 BPM: four beats in 2 s, knees dip on every beat, hips sway, each arm takes a turn pointing up
    dip, rise = (-14, 28), (-3, 6)
    ch = legs({}, [(i / 8, dip if i % 2 == 0 else rise) for i in range(8)])
    ch["hips"] = [(0, (0, 0, -6)), (0.25, (0, 0, 6)), (0.5, (0, 0, -6)), (0.75, (0, 0, 6))]
    spine3(ch, [(0.03, (4, 6, 3)), (0.28, (2, -2, -3)), (0.53, (4, -6, 3)), (0.78, (2, 2, -3))])
    neckhead(ch, [(i / 8, ((6 if i % 2 == 0 else -2), (4 if i < 4 else -4), (-7 if i % 4 < 2 else 7))) for i in range(8)],
             lag=0.04)
    point = ((0.6, 0.78, 0.2), (0.45, 0.88, 0.1))
    ch["armL"] = [(0, GROOVE), (0.07, point), (0.2, point), (0.32, GROOVE), (0.5, ((0.5, -0.75, 0.42), (0.35, 0.35, 0.87))),
                  (0.75, GROOVE)]
    ch["armR"] = [(0, ((0.5, -0.75, 0.42), (0.35, 0.35, 0.87))), (0.25, GROOVE), (0.5, GROOVE), (0.57, point),
                  (0.7, point), (0.82, GROOVE)]
    sym(ch, "shoulder", [(i / 8, (0, 0, 0 if i % 2 == 0 else 4)) for i in range(8)])
    ch["hop"] = [(i / 8, 0.0 if i % 2 == 0 else 0.08) for i in range(8)]
    return clip(2.0, loop=True, **ch)


def _bob():
    ch = legs({}, [(0, (-2, 4)), (0.25, (-16, 30)), (0.5, (-2, 4)), (0.75, (-16, 30))])
    ch["hips"] = [(0, (0, 0, -4)), (0.25, (0, 0, -5)), (0.5, (0, 0, 4)), (0.75, (0, 0, 5))]
    spine3(ch, [(0.04, (2, 0, 2)), (0.29, (5, 0, 2)), (0.54, (2, 0, -2)), (0.79, (5, 0, -2))])
    neckhead(ch, [(0, (0, 0, -5)), (0.25, (7, 0, -6)), (0.5, (0, 0, 5)), (0.75, (7, 0, 6))], lag=0.05)
    ch["armL"] = [(0.05, ((0.45, -0.75, 0.45), (0.2, 0.9, 0.4))), (0.3, ((0.45, -0.78, 0.42), (0.25, 0.55, 0.8))),
                  (0.55, ((0.45, -0.75, 0.45), (0.2, 0.9, 0.4))), (0.8, ((0.45, -0.78, 0.42), (0.25, 0.55, 0.8)))]
    ch["armR"] = [(0.05, ((0.45, -0.78, 0.42), (0.25, 0.55, 0.8))), (0.3, ((0.45, -0.75, 0.45), (0.2, 0.9, 0.4))),
                  (0.55, ((0.45, -0.78, 0.42), (0.25, 0.55, 0.8))), (0.8, ((0.45, -0.75, 0.45), (0.2, 0.9, 0.4)))]
    return clip(1.0, loop=True, **ch)


def _pop_in():
    ch = legs({}, [(0, (-45, 75)), (0.35, (-4, 8)), (0.55, (-8, 12)), (0.75, (-32, 50)), (1, (0, 0))])
    spine3(ch, [(0, (18, 0, 0)), (0.35, (-6, 0, 0)), (0.75, (8, 0, -2)), (1, (0, 0, -3))])
    neckhead(ch, [(0, (10, 0, 0)), (0.35, (-8, 0, 0)), (0.75, (4, 0, 4)), (1, (-2, 6, 8))], lag=0.05)
    ch["armL"] = [(0, ((0.3, -0.85, -0.42), (0.2, -0.8, -0.3))), (0.35, UP), (0.75, ((0.9, -0.3, 0.3), (0.85, 0.1, 0.5))),
                  (1, ((0.78, 0.3, 0.45), (0.1, 0.98, 0.2)))]                          # ends with a little "hi!"
    ch["armR"] = [(0, ((0.3, -0.85, -0.42), (0.2, -0.8, -0.3))), (0.35, UP), (0.75, ((0.9, -0.3, 0.3), (0.85, 0.1, 0.5))),
                  (1, ((0.35, -0.9, 0.2), (-0.4, -0.3, 0.86)))]                         # hand on her hip
    ch["hop"] = [(0, 0.0), (0.5, 0.5), (0.75, 0.1), (1, 0.0)]
    ch["scale"] = [(0, 0.5), (0.5, 1.15), (0.75, 0.95), (1, 1.0)]
    return clip(0.7, **ch)


EAR = ((0.6, -0.5, 0.48), (-0.45, 0.88, -0.12))


def _listen():
    ch = {"armR": [(0, RELAX), (0.25, ((0.4, -0.85, 0.3), (0.3, -0.2, 0.93))), (0.6, ((0.62, -0.48, 0.5), (-0.5, 0.86, -0.08))),
                   (1, EAR)],
          "armL": [(0, RELAX), (0.5, ((0.15, -0.9, 0.4), (-0.4, -0.2, 0.9))), (1, ((0.15, -0.9, 0.4), (-0.45, -0.15, 0.88)))]}
    spine3(ch, [(0, (0, 0, 0)), (0.2, (-2, 0, 0)), (0.7, (8, 3, 3)), (1, (6, 3, 2))])
    neckhead(ch, [(0, (0, 0, 0)), (0.15, (-4, 0, 0)), (0.65, (6, 12, 11)), (1, (4, 10, 9))], lag=0.06)
    ch["hips"] = [(0, (0, 0, 0)), (0.6, (0, 0, -3)), (1, (0, 0, -2.5))]
    return clip(1.0, hold=True, **ch)


def _think():
    chin = ((0.2, -0.75, 0.62), (-0.35, 0.86, 0.38))
    support = ((0.15, -0.88, 0.45), (-0.6, 0.1, 0.8))
    ch = {"armR": [(0, RELAX), (0.18, ((0.25, -0.85, 0.45), (0.0, 0.3, 0.95))), (0.34, ((0.2, -0.73, 0.64), (-0.38, 0.88, 0.3))),
                   (0.42, chin), (1, chin)],
          "armL": [(0, RELAX), (0.32, support), (1, support)]}
    neckhead(ch, [(0, (0, 0, 0)), (0.2, (2, -6, 0)), (0.42, (-9, -16, -7)), (0.62, (-7, -12, -4)), (0.8, (-10, -17, -8)),
                  (1, (-8, -14, -6))], lag=0.05)
    spine3(ch, [(0, (0, 0, 0)), (0.4, (-2, -4, -2)), (1, (-1, -3, -2))])
    ch["hips"] = [(0, (0, 0, 0)), (0.45, (0, 0, 2.5)), (1, (0, 0, 2))]
    return clip(2.0, **ch)


def _shrug():
    palms = ((0.32, -0.9, 0.28), (0.5, 0.05, 0.86))
    ch = {}
    sym(ch, "shoulder", [(0, (0, 0, 0)), (0.12, (0, 0, -3)), (0.36, (0, 0, 15)), (0.5, (0, 0, 12)), (0.72, (0, 0, 2)),
                         (1, (0, 0, 0))])
    sym(ch, "arm", [(0, RELAX), (0.12, ((0.25, -0.96, 0.1), (0.15, -0.9, 0.35))), (0.38, palms),
                    (0.55, ((0.32, -0.9, 0.29), (0.52, 0.0, 0.85))), (0.85, RELAX2), (1, RELAX)])
    neckhead(ch, [(0, (0, 0, 0)), (0.12, (3, 0, 0)), (0.38, (-5, 3, 9)), (0.6, (-3, 2, 7)), (1, (0, 0, 0))], lag=0.05)
    spine3(ch, [(0, (0, 0, 0)), (0.38, (-3, 0, 0)), (1, (0, 0, 0))])
    return clip(1.2, **ch)


def _nod():
    ch = neckhead({}, [(0, (0, 0, 0)), (0.12, (-3, 0, 0)), (0.36, (15, 0, 1)), (0.55, (-2, 0, 0)), (0.72, (6, 0, 0)),
                       (1, (0, 0, 0))], lag=0.04)
    spine3(ch, [(0, (0, 0, 0)), (0.4, (2, 0, 0)), (1, (0, 0, 0))])
    return clip(0.9, **ch)


def _stretch():
    ch = {}
    sym(ch, "arm", [(0, RELAX), (0.12, ((0.3, -0.9, 0.3), (-0.3, -0.5, 0.8))), (0.42, UP),
                    (0.62, ((0.3, 0.94, 0.1), (0.15, 0.99, 0.02))), (0.82, ((0.9, 0.1, 0.2), (0.8, -0.3, 0.3))), (1, RELAX)])
    spine3(ch, [(0, (0, 0, 0)), (0.12, (5, 0, 0)), (0.42, (-9, 0, 0)), (0.55, (-6, 0, 9)), (0.7, (-6, 0, -8)),
                (0.85, (-2, 0, 0)), (1, (0, 0, 0))])
    neckhead(ch, [(0, (0, 0, 0)), (0.12, (6, 0, 0)), (0.42, (-15, 0, 0)), (0.58, (-12, 0, 6)), (0.72, (-12, 0, -6)),
                  (0.85, (2, 0, 0)), (1, (0, 0, 0))], lag=0.05)
    sym(ch, "shoulder", [(0, (0, 0, 0)), (0.42, (0, 0, 10)), (0.75, (0, 0, 8)), (0.9, (0, 0, 0))])
    ch["hips"] = [(0, (0, 0, 0)), (0.55, (0, 0, -4)), (0.7, (0, 0, 4)), (0.9, (0, 0, 0))]
    ch["hop"] = [(0, 0.0), (0.42, 0.06), (0.75, 0.04), (0.9, 0.0)]                             # up on her toes
    return clip(2.6, **ch)


def _yawn():
    mouth = ((0.2, -0.6, 0.75), (-0.2, 0.9, 0.4))
    ch = {"armR": [(0, RELAX), (0.25, ((0.25, -0.65, 0.7), (-0.15, 0.85, 0.5))), (0.32, mouth), (0.72, mouth),
                   (0.88, RELAX2), (1, RELAX)],
          "armL": [(0, RELAX), (0.35, ((0.45, -0.85, -0.25), (0.35, -0.9, -0.2))), (0.75, ((0.45, -0.85, -0.25), (0.35, -0.9, -0.2))),
                   (1, RELAX)]}
    neckhead(ch, [(0, (0, 0, 0)), (0.15, (3, 0, 0)), (0.4, (-14, 0, 3)), (0.65, (-12, 2, 6)), (0.85, (4, 0, 0)), (1, (0, 0, 0))],
             lag=0.06)
    spine3(ch, [(0, (0, 0, 0)), (0.4, (-5, 0, 0)), (0.7, (-4, 0, 2)), (1, (0, 0, 0))])
    sym(ch, "shoulder", [(0, (0, 0, 0)), (0.4, (0, 0, 7)), (0.7, (0, 0, 5)), (0.9, (0, 0, 0))])
    return clip(2.2, **ch)


def _look_around():
    ch = neckhead({}, [(0, (0, 0, 0)), (0.08, (1, -3, 0)), (0.26, (-4, 28, 4)), (0.42, (-2, 26, 3)), (0.52, (4, 2, 0)),
                       (0.72, (-4, -28, -4)), (0.86, (-2, -25, -3)), (1, (0, 0, 0))], lag=0.05)
    spine3(ch, [(0, (0, 0, 0)), (0.3, (0, 8, 0)), (0.45, (0, 7, 0)), (0.55, (1, 0, 0)), (0.76, (0, -8, 0)),
                (0.88, (0, -7, 0)), (1, (0, 0, 0))])
    ch["hips"] = [(0, (0, 0, 0)), (0.3, (0, 0, 2.5)), (0.55, (0, 0, 0)), (0.76, (0, 0, -2.5)), (1, (0, 0, 0))]
    return clip(3.2, **ch)


CLIPS = {"idle-breathe": _idle_breathe(), "wave": _wave(), "sit": _sit(), "sit-swing": _sit_swing(), "walk": _walk(),
         "dance": _dance(), "bob": _bob(), "pop-in": _pop_in(), "listen": _listen(), "think": _think(),
         "shrug": _shrug(), "nod": _nod(), "stretch": _stretch(), "yawn": _yawn(), "look-around": _look_around()}



# ============================================================================ maths
def _m(v):
    return Vector(v).normalized()


def euler_m(v):
    """Model-space euler degrees (y * x * z) -> 3x3 rotation in model axes."""
    return Euler([math.radians(c) for c in v], "ZXY").to_matrix()


def to_bone(arm, bone, rot_model):
    """A parent-relative rotation in model axes -> the pose bone's rotation_quaternion (rest frames from the rig)."""
    rc = arm.data.bones[bone].matrix_local.to_3x3()
    return (rc.inverted() @ C.transposed() @ rot_model @ C @ rc).to_quaternion()


def _between(a, b):
    return _m(a).rotation_difference(_m(b)).to_matrix()


def arm_rots(side, upper, lower):
    """Arm directions (model, shoulder frame; right side given as its left mirror) -> upper/lower arm rotations."""
    if side == "R":
        upper, lower = (-upper[0], *upper[1:]), (-lower[0], *lower[1:])
    rest = Vector((1, 0, 0) if side == "L" else (-1, 0, 0))
    mu = _between(rest, upper)
    return mu, _between(rest, mu.transposed() @ _m(lower))


def mirror_euler(v):
    return (v[0], -v[1], -v[2])


# ============================================================================ building actions in Blender
def armature():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def import_rig():
    w = bpy.context.window_manager.windows[0]
    area = max(w.screen.areas, key=lambda a: a.width * a.height)
    with bpy.context.temp_override(window=w, screen=w.screen, area=area):
        bpy.ops.import_scene.vrm(filepath=str(VRM))
    return armature()


def _keyed(arm, name, spec):
    """(Re)make Action saint:<name> from a CLIPS spec."""
    old = bpy.data.actions.get("saint:" + name)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new("saint:" + name)
    act.use_fake_user = True
    act["saint"] = json.dumps({"duration": spec["duration"], "loop": spec["loop"], "hold": spec["hold"]})
    arm.animation_data_create().action = act
    frames = spec["duration"] * FPS
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for ch, keys in spec["ch"].items():
        keys = sorted(keys, key=lambda k: k[0])
        if spec["loop"]:
            keys = [k for k in keys if k[0] < 1.0]
            keys = keys + [(keys[0][0] + 1.0, keys[0][1])]      # one period; the Cycles modifier repeats it
        for t, v in keys:
            f = 1 + t * frames
            if ch in ("hop", "scale"):
                arm[ch] = float(v)
                arm.keyframe_insert(f'["{ch}"]', frame=f, group="window")
            elif ch.startswith("arm"):
                side = ch[-1]
                mu, ml = arm_rots(side, *v)
                for part, rot in (("upperArm", mu), ("lowerArm", ml)):
                    _key_bone(arm, BONES[part + side], rot, f)
            else:
                _key_bone(arm, BONES[ch], euler_m(mirror_euler(v) if ch.endswith("R") else v), f)
    from bpy_extras import anim_utils
    bag = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot)
    for fc in bag.fcurves:
        if spec["loop"]:
            fc.modifiers.new("CYCLES")
        fc.update()
    act.use_frame_range = True
    act.frame_start, act.frame_end = 1, 1 + frames
    return act


def _key_bone(arm, bone, rot_model, frame):
    pb = arm.pose.bones[bone]
    q = to_bone(arm, bone, rot_model)
    prev = pb.get("_last_q")
    if prev is not None and Quaternion(prev).dot(q) < 0:          # keep quaternion signs continuous
        q.negate()
    pb.rotation_quaternion = q
    pb["_last_q"] = list(q)
    pb.keyframe_insert("rotation_quaternion", frame=frame, group=bone)


def build(save=True):
    """Empty file -> rig + every Action; saved to SAINT_3D/source/SAINT_clips.blend."""
    arm = armature() if any(o.type == "ARMATURE" for o in bpy.data.objects) else import_rig()
    bpy.context.scene.render.fps = FPS
    for name, spec in CLIPS.items():
        for pb in arm.pose.bones:
            pb.pop("_last_q", None)
        _keyed(arm, name, spec)
    for pb in arm.pose.bones:
        pb.pop("_last_q", None)
    arm.animation_data.action = bpy.data.actions["saint:wave"]
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=str(REPO / "SAINT_3D" / "source" / "SAINT_clips.blend"), compress=True)
    return sorted(CLIPS)


# ============================================================================ export
def _delta(arm, bone):
    """The bone's evaluated rotation relative to its rest, in model axes (armature space, the object is identity)."""
    pb = arm.pose.bones[bone]
    d = pb.matrix.to_3x3().normalized() @ arm.data.bones[bone].matrix_local.to_3x3().normalized().inverted()
    return C @ d @ C.transposed()


def _eul(m):
    e = m.to_euler("ZXY")
    return [math.degrees(e.x), math.degrees(e.y), math.degrees(e.z)]


def _pos(arm, bone):
    return C @ arm.pose.bones[bone].head


def _pitch(d):
    return math.degrees(math.atan2(-d.z, -d.y))


def pose_now(arm, parts):
    """The evaluated pose as a clips.py pose, for the given parts."""
    out = {}
    dh = _delta(arm, BONES["hips"])
    duc = _delta(arm, BONES["upperChest"])
    hz = _eul(dh)[2]
    if "hips_z" in parts:
        out["hips_z"] = hz
    if "spine" in parts:
        sx, sy, sz = _eul(dh.transposed() @ duc)
        out["spine"] = [sx, sy, sz + 0.6 * hz]                     # the runtime counter-rolls the spine by 0.6 hips_z
    if "head" in parts:
        out["head"] = _eul(duc.transposed() @ _delta(arm, BONES["head"]))
    if "shoulders" in parts:
        zl, zr = (_eul(duc.transposed() @ _delta(arm, BONES["shoulder" + s]))[2] for s in "LR")
        out["shoulders"] = (zl - zr) / 2                       # one shrug value for both (the right one mirrored)
    for side in ("L", "R"):
        if side in parts:
            f = _delta(arm, BONES["shoulder" + side]).transposed()
            ua, la, hand = (_pos(arm, BONES[p + side]) for p in ("upperArm", "lowerArm", "hand"))
            out[side] = {"upper": list(_m(f @ (la - ua))), "lower": list(_m(f @ (hand - la)))}
    if "legs" in parts:
        hf = dh.transposed()
        out["legs"] = {}
        for side in ("L", "R"):
            ul, ll, ft = (_pos(arm, BONES[p + side]) for p in ("upperLeg", "lowerLeg", "foot"))
            pu, ps = _pitch(_m(hf @ (ll - ul))), _pitch(_m(hf @ (ft - ll)))
            out["legs"][side] = [pu - _REST_LEG[side][0], ps - pu - _REST_LEG[side][1]]
    for k in ("hop", "scale"):
        if k in parts:
            out[k] = float(arm[k])
    return out


_REST_LEG = {}


def _rest_leg_pitches(arm):
    bones = arm.data.bones
    for side in ("L", "R"):
        ul, ll, ft = (C @ bones[BONES[p + side]].head_local for p in ("upperLeg", "lowerLeg", "foot"))
        pu, ps = _pitch(_m(ll - ul)), _pitch(_m(ft - ll))
        _REST_LEG[side] = (pu, ps - pu)


def parts_of(arm, act):
    """Which clips.py pose parts an action animates (only those are exported: the rest stays the state pose's)."""
    from bpy_extras import anim_utils
    bag = anim_utils.action_get_channelbag_for_slot(act, act.slots[0])
    inv = {v: k for k, v in BONES.items()}
    found = set()
    for fc in bag.fcurves:
        if fc.data_path in ('["hop"]', '["scale"]'):
            found.add(fc.data_path[2:-2])
            continue
        ch = inv.get(fc.data_path.split('"')[1], "") if '"' in fc.data_path else ""
        if ch == "hips":
            found.add("hips_z")                     # never hips_y: that's the way she faces, set by ui/avatar
        elif ch in ("spine", "chest", "upperChest"):
            found.add("spine")
        elif ch in ("neck", "head"):
            found.add("head")
        elif ch.startswith("shoulder"):
            found.add("shoulders")
        elif ch[:-1] in ("upperArm", "lowerArm", "hand"):
            found.add(ch[-1])
        elif ch[:-1] in ("upperLeg", "lowerLeg", "foot"):
            found.add("legs")
    return found


def _round(v, digits=2):
    """Degrees to 2 decimals, arm directions (and hop / scale) to 4: small files, no visible loss."""
    if isinstance(v, dict):
        return {k: _round(x, 4 if k in ("upper", "lower", "hop", "scale") else digits) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x, digits) for x in v]
    r = round(float(v), digits)
    return 0.0 if r == 0 else r


def export_action(arm, act):
    meta = json.loads(act["saint"])
    name = act.name.split(":", 1)[1]
    arm.animation_data.action = act
    scene = bpy.context.scene
    parts = parts_of(arm, act)
    frames = meta["duration"] * FPS
    n = max(4, min(63, round(meta["duration"] * SAMPLES_PER_S)))
    keys = []
    for i in range(n + 1):
        t = i / n
        f = 1 + t * frames
        scene.frame_set(int(f), subframe=f - int(f))
        keys.append({"t": round(t, 4), "pose": _round(pose_now(arm, parts))})
    if meta["loop"]:
        keys[-1]["pose"] = keys[0]["pose"]          # the cycle closes exactly
    return {"name": name, "duration": meta["duration"], "loop": meta["loop"], "hold": meta["hold"], "linear": True,
            "source": "SAINT_3D/source/SAINT_clips.blend", "keys": keys}


def export(out=OUT):
    arm = armature()
    _rest_leg_pitches(arm)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for act in sorted((a for a in bpy.data.actions if a.name.startswith("saint:")), key=lambda a: a.name):
        data = export_action(arm, act)
        (out / f"{data['name']}.json").write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
        written.append(data["name"])
    return written


# ============================================================================ checking: pose the rig the way the app does
def apply_runtime(arm, rotations):
    """Pose the rig from core/avatar/body.rotations output ({bone: (w, x, y, z)} parent-frame, model axes)."""
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
    for bone, q in rotations.items():
        if bone in arm.pose.bones:
            arm.pose.bones[bone].rotation_quaternion = to_bone(arm, bone, Quaternion(q).to_matrix())
    bpy.context.view_layer.update()


def render_runtime_poses(poses_json, out_dir):
    """Render each pose of tools/dev/clip_poses.py's output (the app's own bone rotations, computed with the
    app's Python since Blender has no PySide6) to <out_dir>/clip_<name>.png."""
    arm = armature()
    if arm.animation_data:
        arm.animation_data.action = None
    setup_render()
    done = []
    for name, rot in json.loads(Path(poses_json).read_text(encoding="utf-8")).items():
        apply_runtime(arm, rot)
        render(Path(out_dir) / f"clip_{name}.png")
        done.append(name)
    return done


def setup_render(res=(480, 640)):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.color = (0.06, 0.06, 0.08)
    cam = bpy.data.objects.get("ClipCam")
    if cam is None:
        cam = bpy.data.objects.new("ClipCam", bpy.data.cameras.new("ClipCam"))
        scene.collection.objects.link(cam)
    cam.data.lens = 70
    cam.location = (2.2, -3.4, 1.0)
    d = Vector((0, 0, 0.78)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam


def render(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
