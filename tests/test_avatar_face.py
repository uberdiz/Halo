"""core/avatar/face.py: deterministic face weights for the 3D SAINT (blink, speech, state expressions)."""
import random

from core.avatar import AvatarState
from core.avatar.face import EXPRESSIONS, FaceDriver


def run(d, state, secs, level=0.0, dt=1 / 30):
    t, w = getattr(d, "_t", 0.0), {}
    for _ in range(int(secs / dt)):
        t += dt
        w = d.step(state, t, level, dt)
    d._t = t
    return w


def test_blinks_happen_and_reopen():
    d, seen = FaceDriver(random.Random(1)), []
    t = 0.0
    for _ in range(30 * 8):
        t += 1 / 30
        seen.append(d.step(AvatarState.IDLE, t, 0, 1 / 30).get("eyeBlinkLeft", 0))
    assert max(seen) > 0.8 and seen[-1] < 0.5          # closed at least once, open most of the time
    assert sum(v > 0.5 for v in seen) < len(seen) * 0.1


def test_states_ease_to_their_expression():
    d = FaceDriver(random.Random(2))
    w = run(d, AvatarState.SUCCESS, 1.0)
    assert abs(w["mouthSmileLeft"] - EXPRESSIONS[AvatarState.SUCCESS]["mouthSmileLeft"]) < 0.02
    w = run(d, AvatarState.ERROR, 1.0)
    assert w["browInnerUp"] > 0.5 and w.get("mouthSmileLeft", 0) < 0.02
    w = run(d, AvatarState.OFFLINE, 1.0)
    assert w["eyeBlinkLeft"] > 0.9


def test_speech_moves_mouth_only_with_sound():
    d = FaceDriver(random.Random(3))
    assert run(d, AvatarState.SPEAKING, 0.5, level=0.0).get("jawOpen", 0) == 0
    w = run(d, AvatarState.SPEAKING, 0.5, level=0.5)
    assert w["jawOpen"] > 0.2 and any(k.startswith("viseme_") for k in w)
