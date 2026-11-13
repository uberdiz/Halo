"""
core/actions - the typed OS action registry (see docs/ACTIONS.md).

    from core.actions import execute, registry, Plan, undo_last

    execute("settings.sound.volume", {"percent": 40}, source="gui", confirm=ask)

The GUI, SAINT and agents all go through ``execute``; nothing else may call
an action's ``run`` directly.
"""

from __future__ import annotations

import importlib
import logging
import threading

from .registry import (DESTRUCTIVE, RISKS, RISKY, SAFE, Action, ActionError, ActionResult, P, Param, Registry,
                       platform_name, registry)
from .trust import ASK, ASK_RISKY, LEVELS, TRUSTED, get_level, set_level
from .log import ActionLog, action_log, undo, undo_last
from .executor import ConfirmRequest, Plan, PlanStep, execute, preview, progress

__all__ = ["Action", "ActionError", "ActionLog", "ActionResult", "ConfirmRequest", "P", "Param", "Plan",
           "PlanStep", "Registry", "SAFE", "RISKY", "DESTRUCTIVE", "RISKS", "ASK", "ASK_RISKY", "TRUSTED",
           "LEVELS", "action_log", "execute", "get_level", "load_builtin", "platform_name", "preview",
           "progress", "registry", "set_level", "undo", "undo_last"]

_log = logging.getLogger("saint.actions")
_SETS = ("settings", "network", "files", "packages", "services", "power", "windows", "shell", "halos_apps",
         "background", "wallpaper", "maintenance")
_loaded = False
_load_lock = threading.Lock()


def load_builtin():
    """Register the built-in action sets once (cheap to call again)."""
    global _loaded
    if _loaded:
        return
    with _load_lock:
        if _loaded:
            return
        for name in _SETS:
            try:
                importlib.import_module(f"{__name__}.sets.{name}").register(registry)
            except Exception:  # pragma: no cover - one broken set must not hide the others
                _log.exception("actions.set_failed %s", name)
        _loaded = True
