"""
core/actions/proc.py

The single subprocess helper every action uses: argument lists only (never a
shell string), a timeout, and clean user-facing errors.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional, Sequence

from .registry import ActionError

DEFAULT_TIMEOUT = 15


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def qdbus() -> str:
    """Plasma 6 ships qdbus6; some installs only have qdbus."""
    return "qdbus6" if have("qdbus6") or not have("qdbus") else "qdbus"


def run(argv: Sequence[str], timeout: float = DEFAULT_TIMEOUT, check: bool = True,
        input: Optional[str] = None, cwd: Optional[str] = None) -> str:
    """Run ``argv`` and return its stdout (stripped). Raises ActionError when
    the tool is missing, times out, or (with ``check``) exits non-zero."""
    if isinstance(argv, (str, bytes)) or not argv or not all(isinstance(a, str) for a in argv):
        raise ActionError("internal error: a command must be a list of strings", "INVALID")
    if any("\x00" in a for a in argv):
        raise ActionError("internal error: a command argument has an invalid character", "INVALID")
    argv = list(argv)
    env = dict(os.environ, LC_ALL="C")
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, input=input, cwd=cwd,
                           env=env, shell=False)
    except FileNotFoundError:
        raise ActionError(f"{argv[0]} isn't installed on this system.", "MISSING_TOOL")
    except subprocess.TimeoutExpired:
        raise ActionError(f"{argv[0]} didn't answer within {timeout:g} seconds.", "TIMEOUT")
    except OSError as e:
        raise ActionError(f"I couldn't run {argv[0]}: {e}", "FAILED")
    out = (r.stdout or "").strip()
    if check and r.returncode != 0:
        lines = [ln.strip() for ln in ((r.stderr or "") + "\n" + out).splitlines() if ln.strip()]
        why = lines[0] if lines else f"exit code {r.returncode}"
        raise ActionError(f"{argv[0]} failed: {why[:300]}", "FAILED")
    return out


def try_run(argv: List[str], default: str = "", timeout: float = DEFAULT_TIMEOUT) -> str:
    """``run`` for best-effort reads and reload nudges: any failure gives ``default``."""
    try:
        return run(argv, timeout=timeout)
    except ActionError:
        return default
