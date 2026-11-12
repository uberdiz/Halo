"""
core/actions/sets/packages.py

Install and remove apps through the SAINT Store backend (core/store.py picks the source and builds the
argument lists; core/saintos_apps.run_plan runs them). Linux only: the Store is a HalOS feature.
"""

from __future__ import annotations

from ..executor import progress
from ..registry import RISKY, Action, ActionError, ActionResult, P

LINUX = ("linux",)
_NAME = r"[^\x00-\x1f]{1,80}"


def _find(name: str):
    from core import store
    hits = store.search(name, limit=5)
    if not hits:
        raise ActionError(f"I couldn't find an app called {name}", "NOT_FOUND")
    return hits[0]


def _run_steps(steps) -> str:
    """Run the steps; '' when every one worked, else the reason the first failure gave."""
    from core import saintos_apps as sa
    errors = {}

    def on_step(index, total, step, status, percent):
        progress(step.label, percent if status == "progress" else None)

    result = sa.run_plan(steps, on_line=lambda _line: None, on_step=on_step, errors=errors)
    failed = [app for app, ok in result.items() if not ok]
    return "" if not failed else (errors.get(failed[0]) or f"{failed[0]} didn't install")


def _install(p):
    from core import store
    hit = _find(p["name"])
    why = _run_steps(store.plan(hit))
    if why:
        raise ActionError(why, "FAILED")
    return ActionResult(True, f"Installed {hit.name} ({hit.label}).", data={"id": hit.id, "source": hit.source},
                        undo={"name": hit.name})


def _remove(p):
    from core import store
    hit = _find(p["name"])
    if not store.can_uninstall(hit):
        raise ActionError(f"{hit.name} is part of the system, so the Store doesn't remove it", "PROTECTED")
    why = _run_steps(store.uninstall_plan(hit))
    if why:
        raise ActionError(why, "FAILED")
    return ActionResult(True, f"Removed {hit.name}.", data={"id": hit.id, "source": hit.source})


def register(registry):
    name = P("string", "app name", pattern=_NAME)
    registry.register(Action("packages.install", "Install an app", _install, {"name": name}, risk=RISKY,
                             undo=_remove, platforms=LINUX, keywords="download get add app program store",
                             preview=lambda p: f"Install {p['name']} from the SAINT Store."), replace=True)
    registry.register(Action("packages.remove", "Remove an app", _remove, {"name": name}, risk=RISKY,
                             platforms=LINUX, keywords="uninstall delete app program",
                             preview=lambda p: f"Uninstall {p['name']}."), replace=True)
