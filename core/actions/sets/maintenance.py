"""
core/actions/sets/maintenance.py

Keeping the PC working: fix the sound (audio.repair).
"""

from __future__ import annotations

from ..registry import SAFE, Action, ActionResult


def _audio_repair(_p):
    from core import audio_doctor
    r = audio_doctor.repair()
    return ActionResult(r["ok"], r["message"], data={"did": r["did"], "problems": r["problems"]})


def register(registry):
    registry.register(Action(
        "audio.repair", "Fix the sound", _audio_repair, risk=SAFE, platforms=("linux",),
        keywords="no sound audio broken dummy output speakers microphone mic muted fix repair",
        preview=lambda _p: "Check the sound and fix what's wrong (restart PipeWire, pick a real output, unmute)."),
        replace=True)
