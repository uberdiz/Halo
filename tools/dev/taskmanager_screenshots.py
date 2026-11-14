"""
tools/dev/taskmanager_screenshots.py — screenshots of every Task Manager page, offscreen, from made-up data
(no process, user or host name from this PC ends up in docs/screenshots).

    python tools/dev/taskmanager_screenshots.py [out_dir]     # writes taskmanager_<page>.png (default docs/screenshots)
"""

import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_DATA = Path(tempfile.mkdtemp(prefix="saint-taskmgr-shots-"))   # default settings, not this PC's
(_DATA / "config.json").write_text(json.dumps({"appearance": {
    "theme": "Dark", "accent": "#feaa34", "font_family": "Segoe UI" if os.name == "nt" else "Noto Sans", "font_size": 13}}))
os.environ.setdefault("SAINT_DATA_DIR", str(_DATA))
if os.name == "nt":                                   # the offscreen platform finds no fonts on Windows by itself
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

NOW = time.time()


def _p(pid, name, user="alex", cpu=0.0, mem=0, cmd="", app=False, critical=False, threads=4):
    return {"pid": pid, "name": name, "user": user, "status": "running" if cpu else "sleeping", "cpu": cpu,
            "memory": mem, "threads": threads, "ppid": 1, "started": NOW - pid * 60, "command": cmd or f"/usr/bin/{name}",
            "disk_read": 0, "disk_write": cpu * 40000, "critical": critical, "app": app}


MB = 2 ** 20
PROCS = [_p(2101, "firefox", cpu=14.0, mem=1100 * MB, app=True, threads=88), _p(2210, "konsole", cpu=0.4, mem=90 * MB, app=True),
         _p(2302, "dolphin", cpu=0.0, mem=140 * MB, app=True), _p(2420, "steam", cpu=3.1, mem=620 * MB, app=True),
         _p(1301, "baloo_file", cpu=0.2, mem=48 * MB), _p(1402, "kdeconnectd", mem=36 * MB),
         _p(1510, "python", cpu=2.4, mem=380 * MB, cmd="python /opt/saint/app/app.py"),
         _p(1620, "ollama", cpu=0.6, mem=2300 * MB, user="ollama"),
         _p(901, "kwin_wayland", cpu=4.2, mem=210 * MB, critical=True), _p(902, "plasmashell", cpu=1.3, mem=410 * MB, critical=True),
         _p(1, "systemd", user="root", mem=14 * MB, critical=True), _p(450, "NetworkManager", user="root", mem=22 * MB),
         _p(512, "pipewire", cpu=0.8, mem=18 * MB)]
HISTORY = [{"name": "firefox", "cpu_seconds": 4210.0, "processes": 11, "since": NOW - 9 * 3600},
           {"name": "kwin_wayland", "cpu_seconds": 1830.5, "processes": 1, "since": NOW - 26 * 3600},
           {"name": "plasmashell", "cpu_seconds": 640.2, "processes": 1, "since": NOW - 26 * 3600},
           {"name": "steam", "cpu_seconds": 512.0, "processes": 6, "since": NOW - 3 * 3600},
           {"name": "python", "cpu_seconds": 301.7, "processes": 2, "since": NOW - 26 * 3600},
           {"name": "ollama", "cpu_seconds": 95.4, "processes": 1, "since": NOW - 26 * 3600},
           {"name": "konsole", "cpu_seconds": 12.3, "processes": 1, "since": NOW - 2 * 3600},
           {"name": "dolphin", "cpu_seconds": 3.9, "processes": 1, "since": NOW - 1800}]
USERS = [{"name": "alex", "sessions": 2, "since": NOW - 26 * 3600, "processes": 142, "cpu": 31.0, "memory": 5200 * MB},
         {"name": "root", "sessions": 0, "since": None, "processes": 96, "cpu": 2.0, "memory": 410 * MB},
         {"name": "ollama", "sessions": 0, "since": None, "processes": 1, "cpu": 0.6, "memory": 2300 * MB}]
STARTUP = [{"file": "saint.desktop", "name": "SAINT", "command": "/opt/saint/saint", "enabled": True, "scope": "system",
            "path": "/etc/xdg/autostart/saint.desktop"},
           {"file": "steam.desktop", "name": "Steam", "command": "steam -silent", "enabled": True, "scope": "user",
            "path": "~/.config/autostart/steam.desktop"},
           {"file": "org.kde.kdeconnect.daemon.desktop", "name": "KDE Connect", "command": "kdeconnectd",
            "enabled": False, "scope": "system+user", "path": "~/.config/autostart/org.kde.kdeconnect.daemon.desktop"},
           {"file": "baloo_file.desktop", "name": "File Indexer", "command": "baloo_file", "enabled": True,
            "scope": "system", "path": "/etc/xdg/autostart/baloo_file.desktop"}]
SERVICES = [{"name": n, "load": "loaded", "active": a, "sub": s, "description": d, "enabled": e} for n, a, s, d, e in [
    ("bluetooth.service", "active", "running", "Bluetooth service", "enabled"),
    ("cups.service", "inactive", "dead", "CUPS Scheduler", "disabled"),
    ("NetworkManager.service", "active", "running", "Network Manager", "enabled"),
    ("ollama.service", "active", "running", "Ollama Service", "enabled"),
    ("reflector.service", "inactive", "dead", "Refresh Pacman mirrorlist with Reflector", "disabled"),
    ("sddm.service", "active", "running", "Simple Desktop Display Manager", "enabled"),
    ("systemd-tmpfiles-setup.service", "active", "exited", "Create System Files and Directories", "static"),
    ("tlp.service", "failed", "failed", "TLP system startup/shutdown", "enabled")]]
SYSTEM = {"os": "HalOS 2.2", "kernel": "6.12.4-arch1-1", "hostname": "halos-desktop", "boot_time": NOW - 26 * 3600,
          "uptime_s": 26 * 3600, "machine": "Example Systems Tower 7", "board": "X670E", "bios": "1.42", "arch": "x86_64"}
GPUS = [{"vendor": "NVIDIA", "name": "GeForce RTX 4070", "driver": "565.77", "percent": 23.0, "memory_used": 3100 * MB,
         "memory_total": 12282 * MB, "temp_c": 51}]


def window(set_=setattr):
    """A TaskManager filled from the data above. Tests pass monkeypatch.setattr as ``set_`` so it's all undone."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from core import sysinfo
    from ui import taskmanager as tm
    for name, fake in {"app_history": lambda procs: list(HISTORY), "users": lambda procs: [dict(u) for u in USERS],
                       "autostart_entries": lambda *a, **k: [dict(e) for e in STARTUP],
                       "services": lambda user=False, run=None: [] if user else [dict(s) for s in SERVICES],
                       "system": lambda *a, **k: dict(SYSTEM),
                       "failed_units": lambda *a, **k: [{"name": "tlp.service", "user": False, "description": ""}],
                       "gpus": lambda *a, **k: [dict(g) for g in GPUS], "nvidia_detail": lambda *a, **k: [],
                       "gpu_processes": lambda *a, **k: [], "disk_health": lambda name: "PASSED (SMART)",
                       "battery": lambda: None}.items():
        set_(sysinfo, name, fake)
    set_(sysinfo.ProcessSampler, "sample", lambda self: list(PROCS))
    set_(tm.TaskManager, "showEvent", lambda self, e: None)
    set_(tm.TaskManager, "_me", lambda self: "alex")
    tm.apply_style(app)
    w = tm.TaskManager()
    w.procs = list(PROCS)
    w._refresh_processes()
    for i in range(tm.HISTORY):                       # two minutes of graph
        w._refresh_performance(visible=False)
        w.devices["cpu"]["values"][-1] = 22 + 14 * math.sin(i / 6) + 6 * math.sin(i / 1.7)
        w.devices["mem"]["values"][-1] = 48 + 3 * math.sin(i / 11)
    return app, w


def shoot(out: Path, set_=setattr):
    from ui import taskmanager as tm
    app, w = window(set_)
    w.resize(1160, 740)
    w.show()
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i, page in enumerate(tm.PAGES):
        w.nav.setCurrentRow(i)
        end = time.monotonic() + 0.4                  # the page's fade-in
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)
        f = out / f"taskmanager_{page.lower().replace(' ', '_')}.png"
        w.grab().save(str(f))
        files.append(f)
    w.close()
    return files


if __name__ == "__main__":
    for f in shoot(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "screenshots"):
        print(f)
