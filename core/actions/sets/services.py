"""
core/actions/sets/services.py

Start, stop, enable or disable a user service (systemctl --user). Only services on the allow-list in
config ``actions.user_services`` can be touched; system services are out of reach on purpose.
"""

from __future__ import annotations

from core.config import config

from .. import proc
from ..registry import RISKY, Action, ActionError, ActionResult, P

_OPPOSITE = {"start": "stop", "stop": "start", "enable": "disable", "disable": "enable", "restart": ""}


def _unit(name: str) -> str:
    unit = name if "." in name else f"{name}.service"
    if unit not in (config.get("actions.user_services", []) or []):
        raise ActionError(f"{unit} isn't on the list of services I'm allowed to change", "DENIED")
    return unit


def _service(p):
    unit = _unit(p["service"])
    proc.run(["systemctl", "--user", p["do"], unit], timeout=30)
    back = _OPPOSITE[p["do"]]
    return ActionResult(True, f"{unit}: {p['do']} done.", undo={"service": unit, "do": back} if back else None)


def _undo(t):
    proc.run(["systemctl", "--user", t["do"], _unit(t["service"])], timeout=30)
    return f"{t['service']}: {t['do']} done."


def register(registry):
    registry.register(Action(
        "services.user.control", "Start or stop a background service", _service,
        {"service": P("string", pattern=r"[A-Za-z0-9@_.-]{1,80}"), "do": P("string", enum=sorted(_OPPOSITE))},
        risk=RISKY, undo=_undo, platforms=("linux",), keywords="daemon systemd restart enable disable",
        preview=lambda p: f"Run “systemctl --user {p['do']} {p['service']}”."), replace=True)
