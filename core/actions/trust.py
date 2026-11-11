"""
core/actions/trust.py

Trust levels, per action category, saved in the normal config
(``actions.trust``; ``actions.default_trust`` for categories never set):

    ask        ask every time
    ask_risky  (default) run safe actions, ask for risky and destructive ones
    trusted    run safe and risky actions; destructive ones STILL ask

A destructive action always shows its preview and asks, whatever the level.

This sits on top of core/permissions.py rather than replacing it:

* a "deny" override in Settings > Permissions on the action id or its
  category blocks the action; a "confirm" override always asks;
* ids in permissions.ALWAYS_CONFIRM always ask;
* in the "safe" automation mode SAINT and agents may only run safe actions
  (the user's own clicks in a HalOS app are not blocked by it).
"""

from __future__ import annotations

from typing import Dict

from core.config import config
from core.permissions import ALWAYS_CONFIRM, permission_manager

from .registry import DESTRUCTIVE, SAFE, Action

ASK, ASK_RISKY, TRUSTED = "ask", "ask_risky", "trusted"
LEVELS = (ASK, ASK_RISKY, TRUSTED)
LEVEL_LABELS = {ASK: "Ask every time", ASK_RISKY: "Ask for risky", TRUSTED: "Trusted"}

ALLOW, CONFIRM, DENY = "allow", "confirm", "deny"
SOURCES = ("gui", "saint", "agent")


def default_level() -> str:
    level = config.get("actions.default_trust", ASK_RISKY)
    return level if level in LEVELS else ASK_RISKY


def get_level(category: str) -> str:
    level = (config.get("actions.trust", {}) or {}).get(category)
    return level if level in LEVELS else default_level()


def set_level(category: str, level: str, persist: bool = True):
    if level not in LEVELS:
        raise ValueError(f"unknown trust level {level!r} (want one of {', '.join(LEVELS)})")
    levels = dict(config.get("actions.trust", {}) or {})
    levels[category] = level
    config.set("actions.trust", levels, persist=persist)


def reset_level(category: str, persist: bool = True):
    levels = dict(config.get("actions.trust", {}) or {})
    levels.pop(category, None)
    config.set("actions.trust", levels, persist=persist)


def levels() -> Dict[str, str]:
    """category -> level for every registered category (for a Settings page)."""
    from .registry import registry
    return {c: get_level(c) for c in registry.categories(platform=None)}


def decide(action: Action, risk: str, source: str = "gui") -> str:
    """"allow", "confirm" or "deny" for one call of ``action`` at ``risk``."""
    override = permission_manager.get_policy(action.id, default="")
    if override == DENY:
        return DENY
    if source != "gui" and risk != SAFE and config.get("automation.permission_mode", "confirm") == "safe":
        return DENY
    if risk == DESTRUCTIVE or override == CONFIRM or action.id in ALWAYS_CONFIRM:
        return CONFIRM
    level = get_level(action.category)
    if level == ASK:
        return CONFIRM
    if level == TRUSTED:
        return ALLOW
    return ALLOW if risk == SAFE else CONFIRM
