"""
core/claude_chat.py

Chat replies from a small, fast Claude model through Claude Code, with the person's own Claude subscription (no API
key, the same environment as core/claude_agent.py):

    claude -p --model haiku --output-format stream-json --include-partial-messages --system-prompt <SAINT> --tools ""
    (the conversation goes in on stdin, so it is never "no input" and never too long for the command line)

    available()                      Claude Code installed and signed in (checked once per 10 minutes)
    stream(messages, on_token, ...)  stream a reply; raises ChatUnavailable before the first word if Claude can't
                                     answer (not signed in, offline, too slow), so the caller falls back to the
                                     local model

Only plain chat comes here. Commands never do: the router and the action registry run those, deterministically.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from core import claude_agent

log = logging.getLogger("saint.claude_chat")

DEFAULT_MODEL = "haiku"          # Claude Code's alias for its newest Haiku; ai.claude_chat_model overrides it
CHECK_TTL = 600.0
FIRST_TOKEN_SEC = 12.0           # Claude Code's start-up plus the first word; slower than this, the local model answers
TOTAL_SEC = 45.0
HISTORY_MESSAGES = 8


class ChatUnavailable(Exception):
    """Claude can't answer this turn (the caller uses the local model instead)."""


_state = {"at": 0.0, "ok": False}
_lock = threading.Lock()


def _cfg(key: str, default):
    try:
        from core.config import config
        return config.get(key, default)
    except Exception:
        return default


def available(now: Optional[float] = None, which: Callable = shutil.which, signed: Callable = None) -> bool:
    """Claude Code is installed and signed in, and chat through it is on (ai.claude_chat)."""
    if not _cfg("ai.claude_chat", True):
        return False
    now = time.time() if now is None else now
    with _lock:
        if _state["at"] and now - _state["at"] < CHECK_TTL:
            return bool(_state["ok"])
    exe = claude_agent.claude_path(which)
    ok = bool(exe) and bool((signed or claude_agent.signed_in)(exe=exe))
    with _lock:
        _state.update(at=now, ok=ok)
    return ok


def _mark_unavailable():
    with _lock:
        _state.update(at=time.time(), ok=False)


def build_argv(system: str, model: str = "", exe: str = "claude") -> List[str]:
    return [exe, "-p", "--model", model or DEFAULT_MODEL, "--output-format", "stream-json", "--verbose",
            "--include-partial-messages", "--system-prompt", system, "--tools", "", "--no-session-persistence",
            "--strict-mcp-config"]


def split(messages: List[Dict[str, str]], keep: int = HISTORY_MESSAGES) -> Tuple[str, str]:
    """SAINT's chat messages -> (system prompt, what goes on stdin): the recent turns as a short transcript, then
    the user's new message."""
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system" and m.get("content"))
    turns = [m for m in messages if m.get("role") in ("user", "assistant") and m.get("content")]
    if not turns:
        return system, ""
    *earlier, last = turns
    lines = [f"{'User' if m['role'] == 'user' else 'SAINT'}: {m['content']}" for m in earlier[-keep:]]
    prompt = last["content"] if not lines else (
        "Earlier in this conversation:\n" + "\n".join(lines) + "\n\nThe user now says: " + last["content"])
    return system, prompt


def _text_of(ev: Dict) -> str:
    """The new words in one stream-json line ("" for everything else)."""
    if ev.get("type") != "stream_event":
        return ""
    e = ev.get("event") or {}
    d = e.get("delta") or {}
    return str(d.get("text") or "") if e.get("type") == "content_block_delta" and d.get("type") == "text_delta" else ""


def stream(messages: List[Dict[str, str]], on_token: Callable[[str], None], cancel_flag=None,
           first_token_sec: float = FIRST_TOKEN_SEC, total_sec: float = TOTAL_SEC,
           popen: Callable = subprocess.Popen, exe: str = "") -> str:
    """Stream Claude's reply through on_token and return it. Raises ChatUnavailable when nothing was said."""
    system, prompt = split(messages)
    if not prompt.strip():
        raise ChatUnavailable("nothing to answer")
    exe = exe or claude_agent.claude_path()
    if not exe:
        raise ChatUnavailable("Claude Code isn't installed")
    argv = build_argv(system, str(_cfg("ai.claude_chat_model", "") or DEFAULT_MODEL), exe)
    try:
        proc = popen(argv, cwd=tempfile.gettempdir(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                     env=claude_agent.subscription_env(),
                     **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    except OSError as e:
        raise ChatUnavailable(f"Claude Code couldn't start: {e}")
    said: List[str] = []
    started = time.monotonic()
    why = {"text": ""}

    def watchdog():
        # Kill a stuck run: no first word in time, too long overall, or the user interrupted.
        while proc.poll() is None:
            waited = time.monotonic() - started
            if cancel_flag is not None and cancel_flag.is_set():
                why["text"] = "cancelled"
            elif not said and waited > first_token_sec:
                why["text"] = f"no reply within {first_token_sec:.0f} s"
            elif waited > total_sec:
                why["text"] = "took too long"
            if why["text"]:
                proc.kill()
                return
            time.sleep(0.1)
    threading.Thread(target=watchdog, daemon=True, name="claude-chat-watchdog").start()
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except (OSError, ValueError):
        pass
    result, failed = "", ""
    for line in proc.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        tok = _text_of(ev)
        if tok:
            said.append(tok)
            on_token(tok)
        elif ev.get("type") == "result":
            if ev.get("is_error") or ev.get("subtype") != "success":
                failed = str(ev.get("result") or ev.get("subtype") or "error")
            else:
                result = str(ev.get("result") or "")
    proc.wait()
    if not said and result and not failed:          # an older Claude Code without partial messages
        said.append(result)
        on_token(result)
    if not said:
        reason = why["text"] or failed or claude_agent._explain(proc.stderr.read() if proc.stderr else "",
                                                                proc.returncode)
        low = reason.lower()
        if any(w in low for w in ("logged in", "login", "sign in", "signed in", "authenticat")):
            _mark_unavailable()                      # don't try again until the next check
        log.info("claude_chat.unavailable %s", reason[:160])
        raise ChatUnavailable(reason)
    log.info("claude_chat.reply %d chars in %.1f s", sum(map(len, said)), time.monotonic() - started)
    return "".join(said)
