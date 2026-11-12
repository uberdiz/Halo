"""
core/actions/log.py

The append-only action log: one JSON line per action that ran (or was refused
or failed), under the app data dir (``actions/log.jsonl``). Nothing is ever
rewritten - an undo appends its own line that points at the entry it undid.

    {"id", "time", "source", "action", "title", "category", "risk",
     "params" (secrets redacted), "ok", "message", "error", "code",
     "undo" (token or null), "plan"}
    {"type": "undo", "id", "time", "of", "ok", "message"}
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import ActionResult

log = logging.getLogger("saint.actions")


class ActionLog:
    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        if self._path is None:
            from core.paths import data_path
            self._path = data_path("actions", "log.jsonl")
        return self._path

    # ------------------------------------------------------------------ #
    def _append(self, row: Dict[str, Any]):
        line = json.dumps(row, ensure_ascii=False, default=str)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def record(self, action, params: Dict[str, Any], result: ActionResult, source: str, risk: str,
               plan_id: str = "") -> str:
        """Append one action entry; returns its id. ``params`` are redacted here."""
        entry_id = uuid.uuid4().hex[:12]
        self._append({"id": entry_id, "time": time.time(), "source": source, "action": action.id,
                      "title": action.title, "category": action.category, "risk": risk,
                      "params": action.redact(params), "ok": result.ok, "message": result.message,
                      "error": result.error, "code": result.code,
                      "undo": result.undo if (result.ok and action.undo is not None) else None,
                      "plan": plan_id})
        return entry_id

    def _rows(self) -> List[Dict[str, Any]]:
        try:
            with self._lock, open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []
        rows = []
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue                     # a torn last line never hides the rest
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def entries(self, limit: int = 100, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Newest first. Each has ``undone`` and ``can_undo``."""
        rows = self._rows()
        undone = {r.get("of") for r in rows if r.get("type") == "undo" and r.get("ok")}
        out = []
        for row in reversed(rows):
            if row.get("type") == "undo" or (source and row.get("source") != source):
                continue
            row["undone"] = row["id"] in undone
            row["can_undo"] = bool(row.get("ok")) and row.get("undo") is not None and not row["undone"]
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        return next((e for e in self.entries(limit=10 ** 9) if e["id"] == entry_id), None)

    # ------------------------------------------------------------------ #
    def undo(self, entry_id: str) -> ActionResult:
        """Undo one logged action, if it can be undone."""
        from .registry import ActionError, registry
        entry = self.get(entry_id)
        if entry is None:
            return ActionResult(False, error="I can't find that action in the log.", code="NOT_FOUND")
        name = entry.get("title") or entry.get("action")
        if entry["undone"]:
            return ActionResult(False, error=f"“{name}” was already undone.", code="ALREADY_UNDONE",
                                action=entry["action"], entry_id=entry_id)
        action = registry.get(entry["action"])
        if not entry["can_undo"] or action is None or action.undo is None:
            return ActionResult(False, error=f"“{name}” can't be undone.", code="NO_UNDO",
                                action=entry["action"], entry_id=entry_id)
        from core.events import EventType, event_bus
        try:
            out = action.undo(entry["undo"])
            result = out if isinstance(out, ActionResult) else ActionResult(
                True, message=out if isinstance(out, str) and out else f"Undid “{name}”.")
        except ActionError as e:
            result = ActionResult(False, error=str(e), code=e.code)
        except Exception as e:
            log.exception("action.undo_error %s", entry["action"])
            result = ActionResult(False, error=f"Undoing “{name}” failed: {e}", code="ERROR")
        result.action, result.entry_id = entry["action"], entry_id
        self._append({"type": "undo", "id": uuid.uuid4().hex[:12], "time": time.time(), "of": entry_id,
                      "ok": result.ok, "message": result.text})
        event_bus.emit_event(EventType.ACTION_UNDONE, {"entry_id": entry_id, "action": entry["action"],
                                                       "title": name, "ok": result.ok, "message": result.text})
        return result

    def undo_last(self, source: Optional[str] = None) -> ActionResult:
        """Undo the newest action that can still be undone."""
        for entry in self.entries(limit=10 ** 9, source=source):
            if entry["can_undo"]:
                return self.undo(entry["id"])
        return ActionResult(False, error="There's nothing to undo.", code="NOTHING_TO_UNDO")


action_log = ActionLog()


def undo(entry_id: str) -> ActionResult:
    return action_log.undo(entry_id)


def undo_last(source: Optional[str] = None) -> ActionResult:
    return action_log.undo_last(source)
