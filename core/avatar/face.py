"""
core/avatar/face.py

Face-key weights for a 3D avatar that has ARKit face units and Meta visemes (the default SAINT does).
Pure and deterministic, so it is tested without a GPU: the UI calls ``FaceDriver.step`` every frame and
writes the weights into the model's MorphTargets.

    idle      blinks every 2.5–6 s, faint resting smile
    listening a little wider eyes, inner brows up
    thinking  gaze drifts up and to the side, brows a touch raised
    planning/working  focused: slight squint, lips pressed
    speaking  jaw + visemes follow the TTS level (amplitude only; there is no phoneme data)
    success   smile · warning: brows down · error: concerned (inner brows up, slight frown)
    offline   eyes closed, relaxed
"""

from __future__ import annotations

import math
import random
from typing import Dict, Optional

from core.avatar import AvatarState

EXPRESSIONS: Dict[AvatarState, Dict[str, float]] = {
    AvatarState.IDLE: {"mouthSmileLeft": 0.08, "mouthSmileRight": 0.08},
    AvatarState.LISTENING: {"eyeWideLeft": 0.15, "eyeWideRight": 0.15, "browInnerUp": 0.15,
                            "mouthSmileLeft": 0.1, "mouthSmileRight": 0.1},
    AvatarState.THINKING: {"browInnerUp": 0.2, "eyeLookUpLeft": 0.3, "eyeLookUpRight": 0.3,
                           "eyeLookOutLeft": 0.2, "eyeLookInRight": 0.2, "mouthPressLeft": 0.15,
                           "mouthPressRight": 0.15},
    AvatarState.PLANNING: {"eyeSquintLeft": 0.2, "eyeSquintRight": 0.2, "browDownLeft": 0.1,
                           "browDownRight": 0.1, "mouthPressLeft": 0.2, "mouthPressRight": 0.2},
    AvatarState.WORKING: {"eyeSquintLeft": 0.15, "eyeSquintRight": 0.15, "eyeLookDownLeft": 0.15,
                          "eyeLookDownRight": 0.15, "mouthPressLeft": 0.15, "mouthPressRight": 0.15},
    AvatarState.SPEAKING: {"mouthSmileLeft": 0.12, "mouthSmileRight": 0.12},
    AvatarState.SUCCESS: {"mouthSmileLeft": 0.65, "mouthSmileRight": 0.65, "cheekSquintLeft": 0.3,
                          "cheekSquintRight": 0.3, "eyeSquintLeft": 0.15, "eyeSquintRight": 0.15},
    AvatarState.WARNING: {"browDownLeft": 0.35, "browDownRight": 0.35, "mouthPressLeft": 0.25,
                          "mouthPressRight": 0.25},
    AvatarState.ERROR: {"browInnerUp": 0.55, "mouthFrownLeft": 0.3, "mouthFrownRight": 0.3,
                        "mouthStretchLeft": 0.1, "mouthStretchRight": 0.1},
    AvatarState.OFFLINE: {"eyeBlinkLeft": 0.92, "eyeBlinkRight": 0.92},
}
VISEMES = ("viseme_aa", "viseme_E", "viseme_O", "viseme_I", "viseme_U")
BLINK_SEC = 0.16


class FaceDriver:
    """Smoothly moves the face towards the current state's expression, with blinks and speech."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.weights: Dict[str, float] = {}
        self._next_blink = 2.0
        self._blink_start: Optional[float] = None
        self._viseme = VISEMES[0]
        self._viseme_until = 0.0

    def _blink(self, t: float) -> float:
        if self._blink_start is None and t >= self._next_blink:
            self._blink_start = t
        if self._blink_start is None:
            return 0.0
        p = (t - self._blink_start) / BLINK_SEC
        if p >= 1:
            self._blink_start = None
            self._next_blink = t + self.rng.uniform(2.5, 6.0)
            return 0.0
        return math.sin(p * math.pi)                     # close and open again

    def target(self, state: AvatarState, t: float, level: float) -> Dict[str, float]:
        want = dict(EXPRESSIONS.get(state, {}))
        if state != AvatarState.OFFLINE:
            b = self._blink(t)
            if b:
                for k in ("eyeBlinkLeft", "eyeBlinkRight"):
                    want[k] = max(want.get(k, 0.0), b)
        if state == AvatarState.SPEAKING and level > 0.03:
            if t >= self._viseme_until:                  # a new mouth shape every ~90-160 ms, like syllables
                self._viseme = self.rng.choice(VISEMES)
                self._viseme_until = t + self.rng.uniform(0.09, 0.16)
            want["jawOpen"] = min(0.45, level * 0.6)
            want[self._viseme] = min(0.9, 0.35 + level)
        return want

    def step(self, state: AvatarState, t: float, level: float, dt: float) -> Dict[str, float]:
        """Weights for this frame. Blinks and visemes snap; expressions ease in over ~0.25 s."""
        want = self.target(state, t, level)
        k = 1 - math.exp(-dt / 0.08)
        for name in set(self.weights) | set(want):
            goal = want.get(name, 0.0)
            fast = name.startswith(("eyeBlink", "viseme_", "jawOpen"))
            cur = self.weights.get(name, 0.0)
            cur = goal if fast else cur + (goal - cur) * k
            if cur < 0.002 and goal == 0:
                self.weights.pop(name, None)
                continue
            self.weights[name] = cur
        return dict(self.weights)


# VRoid models (the shipped SAINT is one) name their face shapes Fcl_*: map the ARKit/viseme weights onto them.
# VRoid's "Joy" eye shape closes the eyes, so smiles use only the mouth and brows.
VROID = {
    "eyeBlinkLeft": [("Fcl_EYE_Close_L", 1.0)], "eyeBlinkRight": [("Fcl_EYE_Close_R", 1.0)],
    "viseme_aa": [("Fcl_MTH_A", 1.0)], "viseme_E": [("Fcl_MTH_E", 1.0)], "viseme_I": [("Fcl_MTH_I", 1.0)],
    "viseme_O": [("Fcl_MTH_O", 1.0)], "viseme_U": [("Fcl_MTH_U", 1.0)], "jawOpen": [("Fcl_MTH_A", 0.6)],
    "mouthSmileLeft": [("Fcl_MTH_Joy", 0.6), ("Fcl_BRW_Joy", 0.4)],
    "mouthSmileRight": [("Fcl_MTH_Joy", 0.6), ("Fcl_BRW_Joy", 0.4)],
    "browInnerUp": [("Fcl_BRW_Sorrow", 0.9)], "mouthFrownLeft": [("Fcl_MTH_Sorrow", 0.8)],
    "mouthFrownRight": [("Fcl_MTH_Sorrow", 0.8)], "browDownLeft": [("Fcl_BRW_Angry", 0.9)],
    "browDownRight": [("Fcl_BRW_Angry", 0.9)], "eyeWideLeft": [("Fcl_EYE_Surprised", 0.8)],
    "eyeWideRight": [("Fcl_EYE_Surprised", 0.8)], "mouthPressLeft": [("Fcl_MTH_Close", 0.6)],
    "mouthPressRight": [("Fcl_MTH_Close", 0.6)], "eyeSquintLeft": [("Fcl_EYE_Joy_L", 0.35)],
    "eyeSquintRight": [("Fcl_EYE_Joy_R", 0.35)],
}


def to_vroid(weights: Dict[str, float]) -> Dict[str, float]:
    """ARKit/viseme weights -> VRoid Fcl_* weights (each target takes the strongest contribution, max 1)."""
    out: Dict[str, float] = {}
    for name, w in weights.items():
        for target, k in VROID.get(name, ()):
            out[target] = min(1.0, max(out.get(target, 0.0), w * k))
    return out
