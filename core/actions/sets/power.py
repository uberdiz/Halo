"""
core/actions/sets/power.py

Lock, sleep, restart, shut down. Restart and shut down are destructive (unsaved work), so they always ask.
"""

from __future__ import annotations

from .. import proc
from ..registry import DESTRUCTIVE, SAFE, Action, platform_name

_LINUX = {"lock": ["loginctl", "lock-session"], "sleep": ["systemctl", "suspend"],
          "restart": ["systemctl", "reboot"], "shutdown": ["systemctl", "poweroff"]}

_ACTIONS = [
    ("lock", "Lock the screen", SAFE, "Lock the screen.", "lock away leaving"),
    ("sleep", "Put the PC to sleep", SAFE, "Put the PC to sleep.", "suspend standby nap"),
    ("restart", "Restart the PC", DESTRUCTIVE, "Restart the PC now. Unsaved work in open apps is lost.",
     "reboot"),
    ("shutdown", "Shut down the PC", DESTRUCTIVE, "Shut the PC down now. Unsaved work in open apps is lost.",
     "power off turn off"),
]


def _do(what: str, title: str) -> str:
    if platform_name() == "windows":
        from modules.desktop import system_controls
        if what == "lock":
            system_controls.lock()
        else:
            system_controls.power(what)
    else:
        proc.run(_LINUX[what])
    return f"{title}: done."


def register(registry):
    for what, title, risk, text, words in _ACTIONS:
        registry.register(Action(f"power.{what}", title, (lambda _p, w=what, t=title: _do(w, t)), risk=risk,
                                 keywords=words, preview=(lambda _p, t=text: t)), replace=True)
