"""
tools/dev/clip_poses.py

The app's own bone rotations (core/avatar/body.py) for a key pose of each authored clip, as JSON for
SAINT_3D/source/scripts/saint_clips.py's render_runtime_poses (Blender has no PySide6 to run body.py itself).
"name-procedural" entries are the built-in procedural clip, for comparison.

    python tools/dev/clip_poses.py <out.json> [name ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.avatar import AvatarState, body, clips  # noqa: E402

KEY_T = {"idle-breathe": 0.3, "wave": 0.5, "sit": 1.0, "sit-swing": 0.25, "walk": 0.0, "dance": 0.06, "bob": 0.25,
         "pop-in": 1.0, "listen": 1.0, "think": 0.6, "shrug": 0.42, "nod": 0.36, "stretch": 0.45, "yawn": 0.5,
         "look-around": 0.3}
SITTING = ("sit", "sit-swing")


def rotations(clip: dict, t: float, name: str) -> dict:
    base = clips.SIT_POSE if name in SITTING else None
    over = clips.sample(clip, min(t, 0.9999) * clip["duration"])
    p = body.overlay(body.overlay(body.pose(AvatarState.IDLE, 0.0, 0.0), base), over)
    return {b: list(q) for b, q in body.rotations(p, 0.0).items()}


def main(out: str, names) -> int:
    poses = {}
    for name in names or sorted(clips.authored()):
        t = KEY_T.get(name, 0.5)
        poses[name] = rotations(clips.get(name), t, name)
        if name in clips.PROCEDURAL:
            poses[name + "-procedural"] = rotations(clips.validate(clips.PROCEDURAL[name]), t, name)
    Path(out).write_text(json.dumps(poses), encoding="utf-8")
    print(f"{len(poses)} poses -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2:]))
