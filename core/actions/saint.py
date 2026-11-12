"""
core/actions/saint.py

The thin bridge between SAINT's agent and the action registry. Two tools are added to SAINT's existing tool
registry (modules/automation/tools.py), so the router and the LLM reach every OS action without knowing each
one:

    os.find_action   words -> the few matching actions and their parameters (cheap, no LLM)
    os.run_action    action id + parameters -> validated, trust-gated, logged, undoable

and ``os.undo`` takes back the last thing SAINT did. Confirmation uses SAINT's own spoken yes/no flow
(modules/agent/confirm.py) with the action's preview as the question.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from . import execute, load_builtin, registry, undo_last


def find(query: str, limit: int = 5) -> Dict[str, Any]:
    load_builtin()
    return {"actions": [a.to_tool_spec() for a in registry.search(query, limit=limit)]}


def run(action: str, params: Optional[Dict[str, Any]] = None, _confirmed: bool = False) -> Dict[str, Any]:
    """Run one action for SAINT. Needing a yes parks it with SAINT's confirmation manager."""
    from modules.automation.tools import ToolError
    result = execute(action, params or {}, source="saint", confirmed=_confirmed)
    if result.needs_confirmation:
        from modules.agent.confirm import PendingAction, confirmations

        def approved() -> str:
            return execute(action, params or {}, source="saint", confirmed=True).text

        confirmations.ask(PendingAction(description=result.preview, run=approved, tool=action))
        return {"needs_confirmation": True, "message": f"{result.preview} OK?"}
    if not result.ok:
        raise ToolError(result.text, result.code or "FAILED")
    return result.to_dict()


def undo() -> Dict[str, Any]:
    from modules.automation.tools import ToolError
    result = undo_last(source="saint")
    if not result.ok:
        raise ToolError(result.text, result.code or "FAILED")
    return result.to_dict()


def register_action_tools(tool_registry):
    from modules.automation.tools import P, PermissionLevel, Tool
    # LOW here: the real gate is the action's own risk and the user's trust level, inside execute().
    tool_registry.register(Tool(
        "os.find_action", "Find OS actions (settings, files, apps, power, network, windows, shell) by words",
        {"query": "string"}, PermissionLevel.LOW, find,
        parameters={"query": P("string", "what the user wants, e.g. 'make text bigger'")}, category="system", llm_exposed=True))
    tool_registry.register(Tool(
        "os.run_action", "Run one OS action by id with its parameters (asks first when it is risky)",
        {"action": "string", "params": "object"}, PermissionLevel.LOW, run,
        parameters={"action": P("string", "id from os.find_action"),
                    "params": P("object", "the action's parameters", required=False)}, category="system",
        llm_exposed=True))
    tool_registry.register(Tool("os.undo", "Undo the last OS action SAINT ran", {}, PermissionLevel.LOW, undo,
                                category="system"))
