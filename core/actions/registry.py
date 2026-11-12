"""
core/actions/registry.py

The typed OS action registry. HalOS Settings, HalOS Files and SAINT all call
the same actions: the LLM (or a button) only *picks* an action id and its
parameters; the code here validates them and deterministic code runs them.

An ``Action`` declares:

    id          dotted, category first: "settings.display.scale"
    title       short human name: "Change display scale"
    category    first segment of the id ("settings") - trust is set per category
    risk        "safe" | "risky" | "destructive", or a function of the params
    params      {name: Param} - typed, validated before anything runs
    preview     (params) -> str, what will happen, in plain words
    run         (params) -> ActionResult | dict | str | None
    undo        optional (token) -> ActionResult | str | None; ``token`` is the
                JSON dict the run returned as ``ActionResult.undo``
    platforms   ("linux", "windows")

Run an action through ``core.actions.executor.execute`` - never call
``Action.run`` directly, or trust, confirmation and the log are skipped.
"""

from __future__ import annotations

import re
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

SAFE, RISKY, DESTRUCTIVE = "safe", "risky", "destructive"
RISKS = (SAFE, RISKY, DESTRUCTIVE)
PLATFORMS = ("linux", "windows")

_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_TYPES = ("string", "integer", "number", "boolean", "array", "object")
_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


def platform_name() -> str:
    """"linux" or "windows" (tests patch this to exercise the other platform)."""
    return "windows" if sys.platform.startswith("win") else "linux"


class ActionError(Exception):
    """Raised by action code with a clean, user-facing message."""

    def __init__(self, message: str, code: str = "FAILED"):
        super().__init__(message)
        self.code = code


@dataclass
class Param:
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    default: Any = None
    secret: bool = False              # never logged, never shown in a preview
    pattern: Optional[str] = None     # strings: must fully match

    def __post_init__(self):
        if self.type not in _TYPES:
            raise ValueError(f"unknown parameter type {self.type!r}")

    def coerce(self, name: str, value: Any) -> Any:
        t = self.type
        if t == "string":
            if isinstance(value, (dict, list, tuple)):
                raise ActionError(f"'{name}' must be text", "INVALID_PARAMS")
            value = str(value)
            if "\x00" in value:
                raise ActionError(f"'{name}' contains an invalid character", "INVALID_PARAMS")
            if self.pattern and not re.fullmatch(self.pattern, value):
                raise ActionError(f"'{name}' isn't valid: {value!r}", "INVALID_PARAMS")
        elif t in ("integer", "number"):
            if isinstance(value, bool):
                raise ActionError(f"'{name}' must be a number", "INVALID_PARAMS")
            try:
                number = float(value)
                if number != number or number in (float("inf"), float("-inf")):
                    raise ValueError
            except (TypeError, ValueError):
                raise ActionError(f"'{name}' must be a number", "INVALID_PARAMS")
            if t == "integer":
                if number != int(number):
                    raise ActionError(f"'{name}' must be a whole number", "INVALID_PARAMS")
                value = int(number)
            else:
                value = number
            if self.minimum is not None and value < self.minimum:
                raise ActionError(f"'{name}' must be at least {self.minimum:g}", "INVALID_PARAMS")
            if self.maximum is not None and value > self.maximum:
                raise ActionError(f"'{name}' must be at most {self.maximum:g}", "INVALID_PARAMS")
        elif t == "boolean":
            if isinstance(value, str):
                low = value.strip().lower()
                if low not in _TRUE | _FALSE:
                    raise ActionError(f"'{name}' must be true or false", "INVALID_PARAMS")
                value = low in _TRUE
            elif isinstance(value, (bool, int)):
                value = bool(value)
            else:
                raise ActionError(f"'{name}' must be true or false", "INVALID_PARAMS")
        elif t == "array":
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, (list, tuple)) or not all(isinstance(v, (str, int, float)) for v in value):
                raise ActionError(f"'{name}' must be a list", "INVALID_PARAMS")
            value = [str(v) for v in value]
        elif t == "object":
            if not isinstance(value, dict):
                raise ActionError(f"'{name}' must be an object", "INVALID_PARAMS")
        if self.enum is not None and value not in self.enum:
            raise ActionError(f"'{name}' must be one of: {', '.join(map(str, self.enum))}", "INVALID_PARAMS")
        return value


def P(type: str = "string", description: str = "", required: bool = True, **kw) -> Param:
    """Shorthand: ``P("integer", "0-100", minimum=0, maximum=100)``."""
    return Param(type, description, required, **kw)


@dataclass
class ActionResult:
    ok: bool
    message: str = ""                 # plain sentence for the user ("Volume is 40%.")
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    code: str = ""                    # INVALID_PARAMS, UNKNOWN_ACTION, UNAVAILABLE, DENIED,
    #                                   CONFIRM_REQUIRED, DECLINED, FAILED, ...
    undo: Optional[Dict[str, Any]] = None     # JSON token handed to Action.undo later
    action: str = ""
    entry_id: str = ""                # action-log id (empty when nothing ran)
    preview: str = ""
    risk: str = ""

    @property
    def needs_confirmation(self) -> bool:
        return self.code == "CONFIRM_REQUIRED"

    @property
    def text(self) -> str:
        return self.message if self.ok else (self.error or self.message)

    def to_dict(self) -> Dict[str, Any]:
        out = {"ok": self.ok, "action": self.action}
        for key in ("message", "error", "code", "preview", "entry_id"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        if self.data:
            out["data"] = self.data
        if self.undo is not None:
            out["can_undo"] = True
        return out


RiskSpec = Union[str, Callable[[Dict[str, Any]], str]]


@dataclass
class Action:
    id: str
    title: str
    run: Callable[[Dict[str, Any]], Any]
    params: Dict[str, Param] = field(default_factory=dict)
    risk: RiskSpec = SAFE
    preview: Optional[Callable[[Dict[str, Any]], str]] = None
    undo: Optional[Callable[[Dict[str, Any]], Any]] = None
    platforms: Tuple[str, ...] = PLATFORMS
    keywords: str = ""                # extra search words ("louder quieter sound")
    llm: bool = True                  # exported by to_tool_specs()
    category: str = ""

    def __post_init__(self):
        if not _ID.match(self.id):
            raise ValueError(f"bad action id {self.id!r} (want 'category.thing.verb')")
        first = self.id.split(".", 1)[0]
        if self.category and self.category != first:
            raise ValueError(f"{self.id}: category must be the first part of the id ({first!r})")
        self.category = first
        if isinstance(self.risk, str) and self.risk not in RISKS:
            raise ValueError(f"{self.id}: unknown risk {self.risk!r}")
        self.platforms = tuple(self.platforms)
        if not self.platforms or any(p not in PLATFORMS for p in self.platforms):
            raise ValueError(f"{self.id}: platforms must be from {PLATFORMS}")
        for name, spec in self.params.items():
            if not isinstance(spec, Param):
                raise ValueError(f"{self.id}: parameter {name!r} must be a Param")

    # ------------------------------------------------------------------ #
    def available(self, platform: Optional[str] = None) -> bool:
        return (platform or platform_name()) in self.platforms

    def validate(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Coerced, complete parameters. Raises ActionError(INVALID_PARAMS)."""
        params = dict(params or {})
        if not isinstance(params, dict):
            raise ActionError("parameters must be an object", "INVALID_PARAMS")
        unknown = sorted(set(params) - set(self.params))
        if unknown:
            raise ActionError(f"unknown parameter(s): {', '.join(unknown)}", "INVALID_PARAMS")
        out: Dict[str, Any] = {}
        for name, spec in self.params.items():
            value = params.get(name)
            if value is None or (value == "" and spec.type != "string"):
                if spec.default is not None:
                    out[name] = spec.default
                elif spec.required:
                    raise ActionError(f"missing '{name}'", "INVALID_PARAMS")
                continue
            if value == "" and spec.required:
                raise ActionError(f"missing '{name}'", "INVALID_PARAMS")
            out[name] = spec.coerce(name, value)
        return out

    def risk_for(self, params: Dict[str, Any]) -> str:
        """The risk of this call. A risk function that fails or answers
        nonsense counts as destructive - never as safe."""
        if isinstance(self.risk, str):
            return self.risk
        try:
            risk = self.risk(params)
        except Exception:
            return DESTRUCTIVE
        return risk if risk in RISKS else DESTRUCTIVE

    @property
    def max_risk(self) -> str:
        return self.risk if isinstance(self.risk, str) else RISKY

    def describe(self, params: Dict[str, Any]) -> str:
        """Human preview of this call (secrets never appear)."""
        if self.preview is not None:
            try:
                text = self.preview(params)
                if text:
                    return str(text)
            except Exception:
                pass
        shown = {k: ("***" if self.params[k].secret else v) for k, v in params.items() if k in self.params}
        args = ", ".join(f"{k}={v}" for k, v in shown.items())
        return f"{self.title} ({args})" if args else self.title

    def redact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return redact(params, {k for k, s in self.params.items() if s.secret})

    def to_tool_spec(self) -> Dict[str, Any]:
        """A compact tool definition: no empty fields, no prose beyond the title."""
        props, required = {}, []
        for name, spec in self.params.items():
            prop: Dict[str, Any] = {"type": spec.type}
            if spec.description:
                prop["description"] = spec.description
            if spec.enum is not None:
                prop["enum"] = list(spec.enum)
            if spec.minimum is not None:
                prop["minimum"] = spec.minimum
            if spec.maximum is not None:
                prop["maximum"] = spec.maximum
            if spec.type == "array":
                prop["items"] = {"type": "string"}
            props[name] = prop
            if spec.required and spec.default is None:
                required.append(name)
        out: Dict[str, Any] = {"name": self.id, "description": self.title}
        if props:
            out["parameters"] = {"type": "object", "properties": props, "required": required}
        if self.max_risk != SAFE:
            out["risk"] = self.max_risk
        return out


_SECRET_NAME = re.compile(r"pass(word|phrase)?|secret|token|api[_-]?key|psk|credential", re.I)


def redact(params: Dict[str, Any], secret_names=()) -> Dict[str, Any]:
    """``params`` safe to log: secret values replaced, long text shortened."""
    out: Dict[str, Any] = {}
    for key, value in (params or {}).items():
        if key in secret_names or _SECRET_NAME.search(str(key)):
            out[key] = "***"
        elif isinstance(value, dict):
            out[key] = redact(value)
        elif isinstance(value, str) and len(value) > 500:
            out[key] = value[:497] + "..."
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------- #
# Registry
# ---------------------------------------------------------------------- #
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "my", "to", "of", "on", "in", "for", "and", "or", "it", "is", "me", "please", "this",
         "that", "set", "change", "make", "turn", "switch"}


def _words(text: str) -> List[str]:
    out = []
    for w in _WORD.findall((text or "").lower().replace("-", " ").replace("_", " ")):
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


class Registry:
    def __init__(self):
        self._actions: Dict[str, Action] = {}
        self._lock = threading.Lock()

    def register(self, action: Action, replace: bool = False) -> Action:
        with self._lock:
            if action.id in self._actions and not replace:
                raise ValueError(f"action {action.id} is already registered")
            self._actions[action.id] = action
        return action

    def unregister(self, action_id: str) -> bool:
        with self._lock:
            return self._actions.pop(action_id, None) is not None

    def get(self, action_id: str) -> Optional[Action]:
        with self._lock:
            return self._actions.get(action_id)

    def list(self, category: Optional[str] = None, platform: Optional[str] = "current") -> List[Action]:
        """Actions sorted by id. ``platform``: "current" (default), "linux",
        "windows", or None for every platform."""
        if platform == "current":
            platform = platform_name()
        with self._lock:
            actions = list(self._actions.values())
        return sorted((a for a in actions if (category is None or a.category == category)
                       and (platform is None or platform in a.platforms)), key=lambda a: a.id)

    def categories(self, platform: Optional[str] = "current") -> List[str]:
        return sorted({a.category for a in self.list(platform=platform)})

    def search(self, query: str, limit: int = 8, category: Optional[str] = None,
               platform: Optional[str] = "current") -> List[Action]:
        """Best matches for free words ("make text bigger", "wifi off").
        Words match the id, title and keywords; whole-word hits beat prefixes. A keyword matches a longer word only
        when it is most of it ("bright" for "brighter", but not "blue" for "bluetooth")."""
        words = [w for w in _words(query) if w not in _STOP] or _words(query)
        if not words:
            return []
        scored = []
        for a in self.list(category, platform):
            ids, title, keys = set(_words(a.id)), set(_words(a.title)), set(_words(a.keywords))
            everything = ids | title | keys
            score, hits = 0.0, 0
            for w in words:
                if w in ids:
                    s = 3.0
                elif w in title:
                    s = 2.5
                elif w in keys:
                    s = 2.0
                elif len(w) >= 3 and any(t.startswith(w) or (len(t) >= max(4, len(w) - 3) and w.startswith(t)) for t in everything):
                    s = 1.0
                else:
                    s = 0.0
                score += s
                hits += bool(s)
            if hits:
                scored.append((-(score + 2.0 * (hits == len(words))), a.id, a))
        scored.sort(key=lambda row: row[:2])
        return [row[2] for row in scored[:max(1, int(limit))]]

    def to_tool_specs(self, category: Optional[str] = None, ids: Optional[List[str]] = None,
                      platform: Optional[str] = "current") -> List[Dict[str, Any]]:
        """Compact JSON tool definitions for an LLM. Pass ``ids`` (e.g. from
        ``search``) to send only the handful that fit the request."""
        actions = self.list(category, platform)
        if ids is not None:
            wanted = set(ids)
            actions = [a for a in actions if a.id in wanted]
        return [a.to_tool_spec() for a in actions if a.llm]


registry = Registry()
