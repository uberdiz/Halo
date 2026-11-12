"""core/avatar/body.py: full-body poses for the VRoid SAINT, as maths (no GPU)."""
import math

from core.avatar import AvatarState, settings
from core.avatar.body import RELAXED, BodyDriver, pose, q_mul, q_rotate, rotations


def arm_dirs(rot, side):
    rest = (1, 0, 0) if side == "L" else (-1, 0, 0)
    qu, ql = rot[f"J_Bip_{side}_UpperArm"], rot[f"J_Bip_{side}_LowerArm"]
    return q_rotate(qu, rest), q_rotate(q_mul(qu, ql), rest)


def close(a, b, tol=0.03):
    n = math.sqrt(sum(c * c for c in b))
    return all(abs(x - y / n) < tol for x, y in zip(a, b))


def test_arms_point_where_the_pose_says():
    for state in AvatarState:
        p = pose(state, 1.3, 0.4)
        r = rotations(p, 1.3)
        for side in ("L", "R"):
            up, low = arm_dirs(r, side)
            assert close(up, p[side]["upper"]) and close(low, p[side]["lower"]), (state, side)


def test_idle_arms_hang_and_mirror():
    up_l, _ = arm_dirs(rotations(pose(AvatarState.IDLE, 0, 0), 0), "L")
    up_r, _ = arm_dirs(rotations(pose(AvatarState.IDLE, 0, 0), 0), "R")
    assert up_l[1] < -0.9 and abs(up_l[0] + up_r[0]) < 1e-6        # down, and left/right mirrored


def test_states_differ_where_it_matters():
    up = lambda s, side: arm_dirs(rotations(pose(s, 0.5, 0), 0.5), side)[0]
    assert up(AvatarState.SUCCESS, "R")[1] > 0                      # waving: right arm raised
    assert up(AvatarState.WORKING, "L")[2] > 0.4                    # typing: arms forward
    assert pose(AvatarState.OFFLINE, 0, 0)["head"][0] > 15          # resting: head down


def test_driver_eases_and_reduce_motion_holds_still():
    d = BodyDriver()
    a = d.step(AvatarState.IDLE, 0.0, 0, 1 / 30)
    b = d.step(AvatarState.SUCCESS, 1 / 30, 0, 1 / 30)
    assert b["J_Bip_R_UpperArm"] != a["J_Bip_R_UpperArm"]           # moving towards the wave
    still = rotations(pose(AvatarState.IDLE, 2.0, 0), 2.0, intensity=0.0)
    assert still["J_Bip_C_Head"] == (1.0, 0.0, 0.0, 0.0)


def test_view_props_motion_settings():
    s = settings({"avatar": {}})
    assert s["view"] == "full" and s["props"] is True and s["motion"] == 1.0
    s = settings({"avatar": {"view": "x", "motion": "lots"}})
    assert s["view"] == "full" and s["motion"] == 1.0
    assert settings({"avatar": {"motion": 9}})["motion"] == 1.5
