"""
core/actions/sets/shell.py

"Run a Linux command" for SAINT. Always at least risky, and destructive (always asks, whatever the trust
level) when the command can lose data or change the system. The preview is the exact command, nothing else.
It runs as the current user with a timeout; sudo is never given a password here.
"""

from __future__ import annotations

import re

from .. import proc
from ..registry import DESTRUCTIVE, RISKY, Action, ActionError, ActionResult, P, platform_name

_DANGER = [re.compile(rx, re.I) for rx in (
    r"\brm\b", r"\bdd\b", r"\bmkfs", r"\bsudo\b", r"\bsu\b", r"\bpkexec\b", r"\bdoas\b", r"\bshred\b",
    r"\bwipefs\b", r"\bparted\b", r"\b[sc]?fdisk\b", r"\bsgdisk\b", r"\bmkswap\b", r"\bchmod\b", r"\bchown\b",
    r"\b(shutdown|reboot|poweroff|halt)\b", r"\bkill(all)?\b", r"\bpkill\b", r"\bsystemctl\b",
    r"\b(pacman|paru|yay|flatpak)\b", r"\btruncate\b", r"\bmv\b", r"\bcrontab\b", r"\beval\b", r"\bxargs\b",
    r"\|\s*(ba|z|da|fi)?sh\b", r"\b(curl|wget)\b.*\|", r">", r":\(\)\s*\{", r"\bfind\b.*-(delete|exec)",
    r"\bgit\b.*\b(reset\s+--hard|clean|push\b.*--force)", r"`", r"\$\(",
    r"\b(del|rmdir|rd|format|diskpart|reg|bcdedit|Remove-Item|Stop-Process|Set-ExecutionPolicy)\b",
)]


def classify(command: str) -> str:
    """"destructive" when the command matches the danger list, else "risky"."""
    return DESTRUCTIVE if any(rx.search(command) for rx in _DANGER) else RISKY


def _run(p):
    command = p["command"].strip()
    if not command:
        raise ActionError("there's no command to run", "INVALID_PARAMS")
    if platform_name() == "linux":
        argv = ["bash", "-c", command]
    else:
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    out = proc.run(argv, timeout=p.get("timeout") or 60, check=False, cwd=p.get("cwd") or None)
    return ActionResult(True, out[-4000:] or "Done (no output).", data={"output": out[-20000:]})


def register(registry):
    registry.register(Action(
        "shell.run", "Run a command", _run,
        {"command": P("string", "the exact command line"),
         "cwd": P("string", "folder to run it in", required=False),
         "timeout": P("integer", "seconds", required=False, minimum=1, maximum=600)},
        risk=lambda p: classify(p["command"]), keywords="terminal bash linux command line console",
        preview=lambda p: f"Run this command: {p['command']}"), replace=True)
