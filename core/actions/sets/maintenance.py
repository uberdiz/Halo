"""
core/actions/sets/maintenance.py

Keeping the PC working: fix the sound (audio.repair), start from another device or the firmware settings
(recovery.*; restarts, so they always ask).
"""

from __future__ import annotations

from .. import proc
from ..registry import DESTRUCTIVE, SAFE, Action, ActionError, ActionResult, P


def _audio_repair(_p):
    from core import audio_doctor
    r = audio_doctor.repair()
    return ActionResult(r["ok"], r["message"], data={"did": r["did"], "problems": r["problems"]})


def _entry(device: str):
    from core import recovery
    entries = recovery.boot_entries()
    hit = recovery.find_entry(entries, device)
    if hit is None:
        raise ActionError(f"I can't tell which device “{device}” is. This PC can start: "
                          f"{', '.join(e.label for e in entries) or 'nothing I can read'}.", "NOT_FOUND")
    if hit.current:
        raise ActionError(f"{hit.label} is what's running now.", "INVALID")
    return hit


def _boot_device(p):
    from core import recovery
    hit = _entry(p["device"])
    res = recovery.restart(hit)
    return ActionResult(res["ok"], res["reason"], data={"entry": hit.num, "label": hit.label})


def _firmware(_p):
    from core import recovery
    if not recovery.firmware_setup_supported():
        raise ActionError("This PC's firmware can't be asked to open its settings (or it started in legacy BIOS "
                          "mode). Press its setup key (often Del, F2 or F10) while it starts.", "UNSUPPORTED")
    proc.run(recovery.firmware_argv(), timeout=60)
    return "Restarting into the firmware settings…"


def register(registry):
    registry.register(Action(
        "audio.repair", "Fix the sound", _audio_repair, risk=SAFE, platforms=("linux",),
        keywords="no sound audio broken dummy output speakers microphone mic muted fix repair",
        preview=lambda _p: "Check the sound and fix what's wrong (restart PipeWire, pick a real output, unmute)."),
        replace=True)
    registry.register(Action(
        "recovery.boot_device", "Restart from another device", _boot_device,
        {"device": P("string", "a boot entry's name or number, or usb / windows / network",
                     pattern=r"[^\r\n]{1,120}")},
        risk=DESTRUCTIVE, platforms=("linux",),
        keywords="boot from usb stick drive disk windows network pxe restart into start from another device once",
        preview=lambda p: f"Restart the PC now and start “{p['device']}” once. Unsaved work in open apps is lost."),
        replace=True)
    registry.register(Action(
        "recovery.firmware_settings", "Restart into the UEFI firmware settings", _firmware,
        risk=DESTRUCTIVE, platforms=("linux",), keywords="bios uefi setup firmware settings restart",
        preview=lambda _p: "Restart the PC now into its UEFI firmware settings. Unsaved work in open apps is lost."),
        replace=True)
