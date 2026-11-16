"""
modules/remote_desktop/teamviewer.py

"Let me in from my phone" with TeamViewer (plan.md §10): start the TeamViewer service (password prompt, once —
it stays enabled), open TeamViewer so the portal can share the screen, and read this PC's TeamViewer ID so it can
be shown and sent to the phone. Halo Remote (host.py) stays the built-in path; this is for the TeamViewer app.

    status() -> {"installed", "running", "id"}
    start()  -> status after starting (raises RuntimeError with what to do)
"""

import re
import shutil
import subprocess
import time

_ID = re.compile(r"TeamViewer ID:\s*([\d ]{6,})")


def parse_id(text: str) -> str:
    m = _ID.search(text or "")
    return m.group(1).replace(" ", "") if m else ""


def _run(argv, timeout=15):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def status() -> dict:
    if not shutil.which("teamviewer"):
        return {"installed": False, "running": False, "id": ""}
    r = _run(["systemctl", "is-active", "teamviewerd"], 5)
    running = bool(r and r.stdout.strip() == "active")
    info = _run(["teamviewer", "info"]) if running else None
    return {"installed": True, "running": running, "id": parse_id(info.stdout if info else "")}


def start(wait: float = 20.0) -> dict:
    st = status()
    if not st["installed"]:
        raise RuntimeError("TeamViewer isn't installed. Get it from SAINT Store (search “TeamViewer”).")
    if not st["running"]:
        r = _run(["pkexec", "systemctl", "enable", "--now", "teamviewerd"], 120)
        if r is None or r.returncode != 0:
            raise RuntimeError("The TeamViewer service didn't start (the password prompt was dismissed?).")
    # The GUI must run in your session: on Wayland it asks the portal to share the screen (approve once).
    subprocess.Popen(["teamviewer"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.monotonic() + wait
    while time.monotonic() < end:                     # the ID appears once the daemon has registered
        st = status()
        if st["id"]:
            return st
        time.sleep(1)
    return status()


if __name__ == "__main__":
    assert parse_id("TeamViewer ID:      1 234 567 890 \n") == "1234567890"
    assert parse_id("nothing") == ""
    print(status())
