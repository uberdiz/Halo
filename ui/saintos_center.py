"""
ui/saintos_center.py

The one settings window: one left rail with two labelled groups, so each setting has one place.

    HalOS (the operating system)
        Welcome       what HalOS is and what to do first (until you say you're done)
        ...           the pages in ui/settings_pages (Desktop, Startup apps, Drives & OS, ...)
        Apps          points at SAINT Store, the one place to get apps
        Plasma settings  KDE's own pages and a link to KDE System Settings, which stays KDE's
        Updates, Recovery
    SAINT (the assistant)
        General, AI, Voice, Wake Word, Spotify, ...  the config-bound pages of ui/settings_ui.py, sharing one Save bar
        Permissions   Safe / Confirm / Autonomous (core/permissions.py — the same gate SAINT uses)
        Capabilities  what this desktop lets SAINT do and how to fix what's missing (core/platform_caps.py)
        Data          where SAINT keeps settings, memory and models; open the folder
        Evolve        change the desktop with an AI agent (core/evolve.py)
        Service       SAINT's user service: status, start / stop / restart, start at login, recent log
        Diagnostics   SAINT's self-test and a full read-only diagnostics folder

SAINT's Settings and HalOS sidebar items show this window's panel (ui/pages/halo_os.py), and `saintos-control` opens it
there too.    python -m ui.saintos_center [--welcome] [--page NAME] runs it alone.

Every button does what it says through SAINT's own modules (core.config, core.permissions,
modules.ai.providers, core.platform_caps) or systemctl --user; nothing here needs root.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("saint.control_center")

SERVICE = "saint.service"
BUILD_INFO = Path("/usr/share/saintos/build-info.json")
HALO_BUILD_INFO = Path("/usr/share/halo/build-info.json")
OS_RELEASE = Path("/etc/os-release")


# --------------------------------------------------------------------------- #
# Logic (no Qt) — unit-tested in tests/test_saintos_center.py
# --------------------------------------------------------------------------- #
def _run(args: List[str], timeout: float = 15) -> Tuple[int, str]:
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return 127, f"{args[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, f"{' '.join(args)} timed out"
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def systemd_user_available() -> bool:
    return os.name != "nt" and shutil.which("systemctl") is not None


def service_status(run: Callable = _run) -> Dict[str, str]:
    """{"active": "active|inactive|failed|...", "enabled": "enabled|disabled|...", "available": "yes|no"}"""
    if not systemd_user_available() and run is _run:
        return {"active": "unavailable", "enabled": "unavailable", "available": "no"}
    _, active = run(["systemctl", "--user", "is-active", SERVICE])
    _, enabled = run(["systemctl", "--user", "is-enabled", SERVICE])
    return {"active": active.strip().splitlines()[0] if active.strip() else "unknown",
            "enabled": enabled.strip().splitlines()[0] if enabled.strip() else "unknown", "available": "yes"}


_SERVICE_ACTIONS = {
    "start": ["start"], "stop": ["stop"], "restart": ["restart"],
    "enable": ["enable", "--now"], "disable": ["disable", "--now"],
}


def service_action(action: str, run: Callable = _run) -> Tuple[bool, str]:
    if action not in _SERVICE_ACTIONS:
        raise ValueError(f"unknown service action {action!r}")
    code, out = run(["systemctl", "--user", *_SERVICE_ACTIONS[action], SERVICE], timeout=30)
    return code == 0, out.strip() or f"systemctl --user {action} {SERVICE}: done"


def service_log(lines: int = 200, run: Callable = _run) -> str:
    _, out = run(["journalctl", "--user", "-u", SERVICE, "-n", str(int(lines)), "--no-pager", "-o", "short-iso"])
    return out


PERMISSION_MODES = [
    ("safe", "Safe", "Only low-risk actions (open apps, read, play music). Anything else is refused."),
    ("confirm", "Confirm", "Low-risk actions run. One “go ahead?” for a plan with medium steps; "
                           "high-risk steps always ask. (Default)"),
    ("autonomous", "Autonomous", "Low and medium actions run without asking. High-risk steps still ask "
                                 "unless you turned that off in SAINT's settings."),
]


def set_permission_mode(mode: str):
    from core.config import config
    if mode not in {m for m, _, _ in PERMISSION_MODES}:
        raise ValueError(f"unknown permission mode {mode!r}")
    config.set("automation.permission_mode", mode, persist=True)


def detect_ollama(base_url: str) -> Dict:
    """{"running": bool, "models": [names], "error": str} from Ollama's own API — nothing is downloaded."""
    from modules.ai.providers import OllamaProvider
    p = OllamaProvider()
    try:
        status = p.test_connection(base_url, timeout=3)
    except Exception as e:
        return {"running": False, "models": [], "error": str(e), "installed": bool(shutil.which("ollama"))}
    if not status.get("connected"):
        return {"running": False, "models": [], "error": status.get("error", "not reachable"),
                "installed": bool(shutil.which("ollama"))}
    try:
        models = [m.get("name", "") for m in p.list_models(base_url, timeout=5)]
    except Exception as e:
        return {"running": True, "models": [], "error": f"listing models failed: {e}", "installed": True}
    return {"running": True, "models": [m for m in models if m], "error": "", "installed": True}


def save_ai(provider: str, model: str, base_url: str):
    from core.config import config
    if provider not in ("ollama", "openai", "anthropic"):
        raise ValueError("provider must be ollama, openai or anthropic")
    if not model.strip():
        raise ValueError("choose a model")
    config.set("ai.provider", provider, persist=False)
    config.set("ai.model", model.strip(), persist=False)
    config.set("ai.base_url", base_url.strip() or "http://localhost:11434", persist=True)


def data_locations() -> Dict[str, str]:
    from core import paths
    return {"Settings, memory, history": str(paths.data_dir()), "Models": str(paths.models_dir()),
            "Logs": str(paths.data_dir() / "logs"), "SAINT program": str(paths.PROJECT_ROOT)}


def build_info() -> Dict:
    for path in (HALO_BUILD_INFO, BUILD_INFO):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


def is_halo() -> bool:
    """Halo (Arch Linux based) rather than SAINTOS (Fedora based)?"""
    try:
        return any(line.strip() == "ID=halo" for line in OS_RELEASE.read_text(encoding="utf-8").splitlines())
    except OSError:
        return False


def product() -> str:
    return "HalOS" if is_halo() else "SAINTOS"


def update_command() -> List[str]:
    """What "Update now" runs, in a terminal so prompts and progress are visible."""
    if is_halo():
        upd = "paru -Syu" if shutil.which("paru") else "sudo pacman -Syu"
    else:
        upd = "sudo dnf upgrade --refresh"
    return ["konsole", "-e", "bash", "-c", f"{upd}; echo; read -rp 'Done. Press Enter to close.'"]


def os_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    import platform
    return f"{platform.system()} {platform.release()}"


def open_path(path: str) -> bool:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return True
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", path], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    return False


def launch_saint(*args: str) -> bool:
    exe = "/usr/bin/saint"
    if os.path.exists(exe):
        subprocess.Popen([exe, *args], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    root = Path(__file__).resolve().parent.parent
    subprocess.Popen([sys.executable, str(root / "app.py"), *args], cwd=str(root), start_new_session=True)
    return True


def open_store() -> object:
    """SAINT Store is its own app."""
    from core.store import open_store_app
    return open_store_app()


def run_selftest() -> Dict:
    """SAINT's offline self-test (no voice models, no network) in a throwaway data folder."""
    import tempfile
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="saintos-selftest-") as tmp:
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SAINT_DATA_DIR=tmp, SAINT_SELFTEST_NO_VOICE="1")
        report = Path(tmp) / "report.json"
        try:
            subprocess.run([sys.executable, str(root / "app.py"), "--selftest", str(report)], cwd=str(root),
                           env=env, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            return {"passed": False, "checks": [{"name": "selftest", "ok": False, "detail": "timed out"}]}
        try:
            return json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return {"passed": False, "checks": [{"name": "selftest", "ok": False, "detail": f"no report: {e}"}]}


# --------------------------------------------------------------------------- #
# Window
# --------------------------------------------------------------------------- #
PAGES = ["Welcome", "Apps", "Service", "Permissions", "Capabilities", "Data", "Diagnostics",
         "Plasma settings", "Evolve", "Recovery", "Updates"]
# Icons in the left rail (ui/icons.py names): the pages above and ui/settings_ui.py's categories.
PAGE_ICONS = {"Welcome": "home", "Apps": "download", "Service": "power",
              "Permissions": "check-circle", "Capabilities": "zap", "Data": "drive", "Diagnostics": "activity",
              "Plasma settings": "layout", "Evolve": "command", "Recovery": "refresh", "Updates": "arrow-up",
              "General": "settings", "AI": "sparkles", "Voice": "mic", "Wake Word": "radio", "Spotify": "music",
              "Memory": "memory", "Automation": "clock", "Desktop Control": "cursor", "Gaming Mode": "play",
              "MCP": "link", "Appearance": "widget", "Advanced": "list"}
HALOS = "HalOS"                                      # the group's key; its heading is product()
SAINT = "SAINT"
# The rail: HalOS is Welcome, then ui/settings_pages' pages, then these. A settings_pages module may set GROUP = "SAINT".
HALOS_AFTER_EXTRAS = ["Apps", "Plasma settings", "Updates", "Recovery"]
SAINT_PAGES = ["General", "AI", "Voice", "Wake Word", "Permissions", "Capabilities", "Automation", "Desktop Control",
               "Memory", "Data", "Spotify", "Gaming Mode", "MCP", "Appearance", "Evolve", "Service", "Diagnostics",
               "Advanced"]
LINUX_ONLY_SAINT = {"Evolve", "Service"}             # systemd, pacman and snapshots
OLD_PAGE_NAMES = {"desktop & devices": "plasma settings"}


def welcome_done_mark() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "saintos" / "welcome-done"


def rail_rows(extra_pages, os_pages: bool = True) -> List[Tuple[str, str]]:
    """(name, icon) of every row in the rail, in order; a group heading has no icon. ``os_pages``: False where the
    operating system's pages don't apply (SAINT on Windows)."""
    extras = {HALOS: [], SAINT: []}
    for mod in extra_pages:
        extras[SAINT if getattr(mod, "GROUP", HALOS) == SAINT else HALOS].append((mod.TITLE, mod.ICON))
    icon = lambda names: [(n, PAGE_ICONS[n]) for n in names]
    if not os_pages:
        return [(SAINT, "")] + icon(n for n in SAINT_PAGES if n not in LINUX_ONLY_SAINT) + extras[SAINT]
    return ([(product(), "")] + icon(["Welcome"]) + extras[HALOS] + icon(HALOS_AFTER_EXTRAS)
            + [(SAINT, "")] + icon(SAINT_PAGES) + extras[SAINT])


def group_of(name: str, rows: List[Tuple[str, str]]) -> str:
    """HALOS or SAINT for a page name in ``rail_rows``' answer."""
    group = HALOS
    for row, icon_name in rows:
        if not icon_name:
            group = SAINT if row == SAINT else HALOS
        elif row.lower() == name.lower():
            return group
    return SAINT

# Plasma's own settings pages (kcmshell6 <module>), the ones people change most.
KCMS = [("Wi-Fi & network", "kcm_networkmanagement"), ("Bluetooth", "kcm_bluetooth"), ("Displays", "kcm_kscreen"),
        ("Sound", "kcm_pulseaudio"), ("Notifications", "kcm_notifications"), ("Power", "kcm_powerdevilprofilesconfig"),
        ("Keyboard shortcuts", "kcm_keys"), ("Users", "kcm_users"), ("Region & language", "kcm_regionandlang"),
        ("Colours & theme", "kcm_lookandfeel"), ("Window effects", "kcm_kwin_effects"), ("Virtual desktops", "kcm_kwin_virtualdesktops"),
        ("Default apps", "kcm_componentchooser"), ("Date & time", "kcm_clock"),
        ("Phone (KDE Connect)", "kcm_kdeconnect"), ("Remote desktop", "kcm_krdpserver"), ("All settings", "")]


def open_kcm(kcm: str) -> str:
    """Open one of Plasma's settings pages ("" = all of System Settings). Returns an error message or ""."""
    cmd = ["kcmshell6", kcm] if kcm else ["systemsettings"]
    if not shutil.which(cmd[0]):
        return "Plasma's settings aren't installed here."
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ""


def build_window(start_page: str = "Welcome", os_pages: bool = True, on_appearance_changed: Optional[Callable] = None,
                 on_group_changed: Optional[Callable[[str], None]] = None):
    """The settings window (SAINT's own window takes its central widget). ``win._open(name)`` shows a page by name,
    ``win._open_group(group)`` makes sure one of HALOS / SAINT is showing, ``win._settings`` is the SettingsUI.
    Rail rows and ``win._stack`` line up one to one (a heading has an empty page), so a row is ``page_names.index(name)``."""
    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QCheckBox, QComboBox, QFormLayout, QGroupBox,
                                   QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QPlainTextEdit,
                                   QPushButton, QRadioButton, QStackedWidget, QTableWidget, QTableWidgetItem,
                                   QVBoxLayout, QWidget)
    from core.config import config

    class _Bridge(QObject):
        done = Signal(object, object)            # (callback, result) back on the GUI thread
        line = Signal(object, str)               # (callback, text) for streamed command output

    bridge = _Bridge()
    bridge.done.connect(lambda cb, result: cb(result))
    bridge.line.connect(lambda cb, text: cb(text))

    def in_background(fn, then):
        """Run ``fn`` off the GUI thread (systemctl, Ollama, the self-test) and hand the result to ``then``."""
        def work():
            try:
                result = fn()
            except Exception as e:
                result = e
            bridge.done.emit(then, result)
        threading.Thread(target=work, daemon=True).start()

    def heading(text, sub=""):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 8)
        t = QLabel(text)
        t.setObjectName("PageTitle")
        v.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setObjectName("PageSubtitle")
            s.setWordWrap(True)
            v.addWidget(s)
        return box

    def page(title, sub=""):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(32, 26, 32, 26)
        v.setSpacing(12)
        v.addWidget(heading(title, sub))
        return w, v

    win = QMainWindow()
    win.setWindowTitle(f"{product()} Settings")
    from ui import icons
    icons.set_window_icon(win, QIcon(str(Path(__file__).parent.parent / "data" / "brand" / "halos-256.png")))
    win.resize(1040, 680)
    root = QWidget()
    h = QHBoxLayout(root)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    from ui.components.side_rail import SideRail
    from ui import settings_pages
    from ui.settings_ui import SettingsUI
    extra_pages = settings_pages.discover()
    rows = rail_rows(extra_pages, os_pages)
    page_names = [name for name, _ in rows]
    rail = SideRail(product() if os_pages else SAINT, "Settings", rows, search=True)
    nav = rail.nav
    pages_stack = QStackedWidget()
    settings = SettingsUI(on_appearance_changed=on_appearance_changed)   # its own widget is the Save bar
    right = QVBoxLayout()
    right.setContentsMargins(0, 0, 0, 0)
    right.setSpacing(0)
    right.addWidget(pages_stack, 1)
    right.addWidget(settings)
    h.addWidget(rail)
    h.addLayout(right, 1)
    win.setCentralWidget(root)

    class _Pages:
        """Each page below calls stack.addWidget in the order of PAGES + extra pages; the rail's order comes after."""
        def __init__(self):
            self.built = []

        def addWidget(self, widget):
            self.built.append(widget)
    stack = _Pages()

    # ---------------- Welcome
    halo = is_halo()
    w, v = page(f"Welcome to {product()}", f"{os_name()} — KDE Plasma with SAINT built in.")
    info = QLabel(
        f"{product()} is a normal {'Arch Linux' if halo else 'Fedora'} KDE desktop: everything works without "
        "SAINT, without a network and without an AI model.\n\nTo get SAINT talking:\n"
        "  1. AI — " + ("Ollama is built in. Once you're online, HalOS picks models for this PC and downloads them in "
                       "the background, with CUDA on NVIDIA graphics (AI page: see it, change it, add a Claude key)"
                       if halo else
                       "install Ollama and pull one model you choose") + ", or point SAINT at a provider you "
        "already use.\n"
        "  2. Voice — pick your microphone" + (". The speech model downloads with the AI.\n" if halo else
                                               ". SAINT's speech models download the first time you start it.\n") +
        "  3. Service — start SAINT now, and turn on “start at login” if you want it always there.\n\n"
        + ("HalOS is built from Arch Linux packages; it isn't an official Arch Linux product." if halo else
           "SAINTOS is a Fedora Remix: built from Fedora Linux packages, not an official Fedora product."))
    info.setWordWrap(True)
    v.addWidget(info)
    wrow = QHBoxLayout()
    open_btn = QPushButton("Open SAINT")
    open_btn.clicked.connect(lambda: launch_saint())
    apps_btn = QPushButton("Install my apps…")
    apps_btn.clicked.connect(lambda: nav.setCurrentRow(page_names.index("Apps")))
    new_btn = QPushButton("What's new")                # the highlights tour (ui/whats_new.py)
    def whats_new():
        from core import actions
        actions.execute("whatsnew.show", {})
    new_btn.clicked.connect(whats_new)
    wrow.addWidget(open_btn)
    wrow.addWidget(apps_btn)
    wrow.addWidget(new_btn)
    from core import windows_migration
    if "Migrate from Windows" in page_names and windows_migration.should_offer():    # offered once
        windows_migration.mark_offered()
        migrate_btn = QPushButton("Bring my files and apps from Windows…")
        migrate_btn.clicked.connect(lambda: nav.setCurrentRow(page_names.index("Migrate from Windows")))
        wrow.addWidget(migrate_btn)
    wrow.addStretch(1)
    v.addLayout(wrow)
    done_btn = QPushButton("Done, hide this page")
    done_btn.setObjectName("Ghost")
    v.addWidget(done_btn, 0, Qt.AlignLeft)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Apps: SAINT Store is the one place for them
    w, v = page("Apps", "Installing, removing and finding apps all happen in SAINT Store: Flathub, Arch, the AUR and "
                        "Windows apps, with SAINT's picks up front.")
    store_btn = QPushButton("Open SAINT Store")
    store_btn.setObjectName("Primary")
    store_btn.clicked.connect(lambda: open_store())
    v.addWidget(store_btn, 0, Qt.AlignLeft)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Service
    w, v = page("SAINT service", "SAINT runs as your user (systemd --user): no root, logs in the journal.")
    status_lbl = QLabel("Checking…")
    v.addWidget(status_lbl)
    row = QHBoxLayout()
    log_view = QPlainTextEdit()
    log_view.setReadOnly(True)

    def refresh_service():
        def show(st):
            if isinstance(st, Exception):
                status_lbl.setText(f"Couldn't read the service: {st}")
                return
            if st["available"] != "yes":
                status_lbl.setText("systemd user services aren't available here (this page works on SAINTOS).")
                return
            status_lbl.setText(f"Running: <b>{st['active']}</b> &nbsp;·&nbsp; Start at login: <b>{st['enabled']}</b>")
        in_background(service_status, show)
        in_background(service_log, lambda out: log_view.setPlainText(out if isinstance(out, str) else str(out)))

    for label, action in (("Start", "start"), ("Stop", "stop"), ("Restart", "restart"),
                          ("Start at login", "enable"), ("Don't start at login", "disable")):
        b = QPushButton(label)
        b.clicked.connect(lambda _=False, a=action: in_background(
            lambda: service_action(a), lambda res: (status_lbl.setText(
                res[1] if not isinstance(res, Exception) else str(res)), refresh_service())))
        row.addWidget(b)
    row.addStretch(1)
    v.addLayout(row)
    v.addWidget(QLabel("Recent log"))
    v.addWidget(log_view, 1)
    stack.addWidget(w)

    # ---------------- Permissions
    w, v = page("Permissions", "Every action SAINT takes has a risk level; this decides which ones ask first.")
    group = QButtonGroup(w)
    current = config.get("automation.permission_mode", "confirm")
    pmsg = QLabel("")
    for key, name, desc in PERMISSION_MODES:
        rb = QRadioButton(name)
        rb.setChecked(key == current)
        rb.toggled.connect(lambda on, k=key: on and (set_permission_mode(k), pmsg.setText(f"Mode: {k}. Saved.")))
        group.addButton(rb)
        v.addWidget(rb)
        about = QLabel(desc)
        about.setObjectName("Muted")
        about.setWordWrap(True)
        v.addWidget(about)
    v.addWidget(pmsg)
    ask_high = QCheckBox("Always ask before high-risk actions")
    ask_high.setChecked(bool(config.get("automation.confirm_dangerous", True)))
    ask_high.toggled.connect(lambda on: (config.set("automation.confirm_dangerous", on), pmsg.setText("Saved.")))
    v.addWidget(ask_high)
    always = QLabel("Moving files to the trash, uninstalling, power and force-quit always ask, in every mode. "
                    "Per-tool access is under Desktop Control.")
    always.setWordWrap(True)
    v.addWidget(always)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Capabilities
    w, v = page("Capabilities", "What this desktop lets SAINT do. Missing pieces say which package adds them.")
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Capability", "Status", "Provider / how to enable"])
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)

    def fill_caps():
        from core.platform_caps import capabilities
        caps = capabilities()
        table.setRowCount(len(caps))
        for i, c in enumerate(caps):
            table.setItem(i, 0, QTableWidgetItem(c.name.replace("_", " ")))
            table.setItem(i, 1, QTableWidgetItem("available" if c.available else "missing"))
            table.setItem(i, 2, QTableWidgetItem(c.provider if c.available else c.hint))
        table.resizeColumnsToContents()
    fill_caps()
    v.addWidget(table, 1)
    re_btn = QPushButton("Check again")
    re_btn.clicked.connect(fill_caps)
    v.addWidget(re_btn, 0, Qt.AlignLeft)
    stack.addWidget(w)

    # ---------------- Data
    w, v = page("Data", "Everything SAINT knows about you stays in these folders on this machine.")
    form = QFormLayout()
    for label, path in data_locations().items():
        rowb = QHBoxLayout()
        rowb.addWidget(QLabel(path), 1)
        b = QPushButton("Open")
        b.clicked.connect(lambda _=False, p=path: open_path(p) if os.path.exists(p) else None)
        rowb.addWidget(b)
        holder = QWidget()
        holder.setLayout(rowb)
        form.addRow(label, holder)
    v.addLayout(form)
    secrets_note = QLabel("Secrets (Spotify login, Link key, API keys) are kept in KWallet through the Secret Service.")
    secrets_note.setWordWrap(True)
    v.addWidget(secrets_note)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Diagnostics
    w, v = page("Diagnostics", "Read-only checks. The report folder contains no secrets or memory contents.")
    out = QPlainTextEdit()
    out.setReadOnly(True)
    drow = QHBoxLayout()
    st_btn = QPushButton("Run SAINT self-test")
    dg_btn = QPushButton("Collect diagnostics folder")

    def show_selftest(rep):
        if isinstance(rep, Exception):
            out.setPlainText(f"Self-test failed to run: {rep}")
            return
        lines = [f"Self-test: {'PASSED' if rep.get('passed') else 'FAILED'}"]
        for c in rep.get("checks", []):
            lines.append(f"  {'ok  ' if c.get('ok') else 'FAIL'}  {c.get('name')}: {str(c.get('detail'))[:200]}")
        out.setPlainText("\n".join(lines))
    st_btn.clicked.connect(lambda: (out.setPlainText("Running (up to a minute)…"),
                                    in_background(run_selftest, show_selftest)))

    def collect():
        exe = shutil.which("saintos-diagnose")
        if not exe:
            return "saintos-diagnose isn't installed (it ships with SAINTOS)."
        code, text = _run([exe], timeout=300)
        return text.strip()
    dg_btn.clicked.connect(lambda: (out.setPlainText("Collecting…"),
                                    in_background(collect, lambda r: out.setPlainText(
                                        f"Diagnostics written to:\n{r}" if isinstance(r, str) else str(r)))))
    drow.addWidget(st_btn)
    drow.addWidget(dg_btn)
    drow.addStretch(1)
    v.addLayout(drow)
    v.addWidget(out, 1)
    stack.addWidget(w)

    # ---------------- Plasma settings: the everyday settings, each opening KDE's own page for it
    w, v = page("Plasma settings", "The settings people change most. Each opens Plasma's own settings page; "
                                   "everything else is in KDE System Settings.")
    grid = QWidget()
    from PySide6.QtWidgets import QGridLayout
    g = QGridLayout(grid)
    g.setSpacing(8)
    kmsg = QLabel("")
    for n, (label, kcm) in enumerate(KCMS):
        b = QPushButton(label)
        b.clicked.connect(lambda _=False, k=kcm, t=label: kmsg.setText(open_kcm(k) or f"{t} opened."))
        g.addWidget(b, n // 3, n % 3)
    v.addWidget(grid)
    v.addWidget(kmsg)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Evolve: change HalOS with an AI agent (core/evolve.py)
    from core import evolve
    w, v = page("Evolve", "Describe a change to your desktop and let Claude (or another AI agent) build it. You see "
                          "exactly what changes before anything is applied, and every change can be undone.")
    ask_box = QLineEdit()
    ask_box.setPlaceholderText("e.g. make window animations slower · a widget with my GPU temperature · "
                               "pause Spotify when my headphones disconnect")
    v.addWidget(ask_box)
    erow = QHBoxLayout()
    mode_pick = QComboBox()
    mode_pick.addItems(["Your desktop", "SAINT / HalOS itself (source code)"])
    erow.addWidget(QLabel("Change:"))
    erow.addWidget(mode_pick)
    agent_pick = QComboBox()
    agent_pick.addItems(list(evolve.agents()))
    erow.addWidget(QLabel("Agent:"))
    erow.addWidget(agent_pick)
    build_btn = QPushButton("Build it")
    erow.addWidget(build_btn)
    erow.addStretch(1)
    v.addLayout(erow)
    elog = QPlainTextEdit()
    elog.setReadOnly(True)
    elog.setMaximumHeight(130)
    v.addWidget(elog)
    eview = QLabel("")
    eview.setWordWrap(True)
    v.addWidget(eview)
    ediff = QPlainTextEdit()
    ediff.setReadOnly(True)
    ediff.hide()
    v.addWidget(ediff, 1)
    arow = QHBoxLayout()
    apply_btn = QPushButton("Apply")
    discard_btn = QPushButton("Discard")
    for b_ in (apply_btn, discard_btn):
        b_.setEnabled(False)
        arow.addWidget(b_)
    # Source mode (OS Expansion Agent): plan -> approve -> snapshot + apply + tests -> keep / roll back
    approve_btn = QPushButton("Approve plan and build")
    keep_btn = QPushButton("Keep")
    rollback_btn = QPushButton("Roll back")
    src_btns = (approve_btn, keep_btn, rollback_btn)
    for b_ in src_btns:
        b_.setEnabled(False)
        b_.hide()
        arow.addWidget(b_)
    arow.addStretch(1)
    v.addLayout(arow)
    hist = QListWidget()
    hist.setMaximumHeight(110)
    v.addWidget(QLabel("Changes so far (select one to undo it):"))
    v.addWidget(hist)
    undo_btn = QPushButton("Undo the selected change")
    v.addWidget(undo_btn, 0, Qt.AlignLeft)
    estate = {"ws": None, "rv": None, "hist": []}

    def fill_hist():
        estate["hist"] = evolve.history()
        hist.clear()
        for hh in estate["hist"][:30]:
            hist.addItem(f"{hh['id']}  [{hh['status']}]  {hh['request'][:90]}")

    def built(code):
        build_btn.setEnabled(True)
        if isinstance(code, Exception):
            eview.setText(f"Stopped: {code}")
            return
        rv = evolve.review(estate["ws"])
        estate["rv"] = rv
        parts = [rv.summary or "The agent finished."]
        if rv.home:
            parts.append("In your home folder: " + ", ".join(rv.home))
        if rv.touches_system:
            parts.append("System (asks for your password; snapshots before and after): "
                         + ", ".join(rv.system + rv.packages))
        if rv.refused:
            parts.append("Refused (outside what Evolve may change): " + ", ".join(rv.refused))
        parts.append("Takes effect: " + ("after a restart" if rv.restart else "right away"
                                          + (f" ({', '.join(rv.live)})" if rv.live else "")))
        eview.setText("\n".join(parts))
        ediff.setPlainText(rv.diff)
        ediff.show()
        nothing = not (rv.home or rv.touches_system)
        apply_btn.setEnabled(not nothing)
        discard_btn.setEnabled(True)
        if nothing:
            eview.setText(eview.text() + "\nNothing to apply.")

    def source_mode():
        return mode_pick.currentIndex() == 1

    def mode_changed(_=0):
        src = source_mode()
        agent_pick.setEnabled(not src)
        for b_ in (apply_btn, discard_btn):
            b_.setVisible(not src)
        for b_ in src_btns:
            b_.setVisible(src)
            b_.setEnabled(False)
        if src:
            st = evolve.claude_status()
            eview.setText(("Claude Code: " + st.message) if st.ok else f"{st.message}\nHow to fix: {st.fix}")

    def stream(t):
        bridge.line.emit(elog.appendPlainText, t)

    def src_build():
        st = evolve.claude_status()
        if not st.ok:
            eview.setText(f"{st.message}\nHow to fix: {st.fix}")
            return
        repo = evolve.default_repo()
        if repo is None:
            eview.setText("No SAINT source checkout found. Clone the HalOS repository and set evolve.repo in "
                          "SAINT's config to its folder.")
            return
        build_btn.setEnabled(False)
        elog.clear()
        ediff.hide()
        eview.setText("Indexing the source and asking Claude Code for a plan (read-only)…")

        def work():
            ix = evolve.build_index(repo)
            reg = evolve.skill_registry(ix)
            ch = evolve.start_source_change(repo, ask_box.text())
            estate.update(ch=ch, ix=ix, reg=reg)
            stream(f"Index: {len(ix.files)} files ({ix.reused} from cache). Worktree: {ch.worktree}")
            return evolve.plan_source_change(ch, ix, reg, on_line=stream)

        def planned(r):
            build_btn.setEnabled(True)
            if isinstance(r, Exception):
                eview.setText(f"Stopped: {r}")
                return
            eview.setText("Plan ready. Nothing has changed yet. Approve it to snapshot, build and test it.")
            ediff.setPlainText(r)
            ediff.show()
            approve_btn.setEnabled(True)
            rollback_btn.setEnabled(True)
        in_background(work, planned)

    def src_approve():
        ch = estate["ch"]
        approve_btn.setEnabled(False)
        eview.setText("Snapshot (asks for your password), then Claude Code builds it in its own worktree…")

        def work():
            evolve.approve(ch)
            d = evolve.apply_source_change(ch, estate["ix"], estate["reg"], on_line=stream)
            return d, evolve.test_source_change(ch)

        def tested(r):
            if isinstance(r, Exception):
                eview.setText(f"Didn't build: {r}")
                return
            d, t = r
            ediff.setPlainText(d + "\n\n--- tests ---\n" + t["output"])
            snap = ch.snapshot or {}
            snap_txt = (f"snapshot {snap.get('number') or snap.get('path')}" if snap.get("kind")
                        else snap.get("reason", "no snapshot"))
            if t["passed"]:
                eview.setText(f"Built and the tests passed ({', '.join(t['targets'])}; {snap_txt}). Keep it?")
                keep_btn.setEnabled(True)
            else:
                eview.setText(f"The tests failed ({', '.join(t['targets'])}), so it's being rolled back.")
                in_background(lambda: evolve.rollback(ch), lambda x: eview.setText(
                    "Tests failed; rolled back: " + ("; ".join(x) if isinstance(x, list) else str(x))))
                keep_btn.setEnabled(False)
                rollback_btn.setEnabled(False)
        in_background(work, tested)

    def src_finish(keep_it):
        ch = estate.get("ch")
        if ch is None:
            return
        for b_ in src_btns:
            b_.setEnabled(False)
        fn = (lambda: evolve.keep(ch)) if keep_it else (lambda: "Rolled back: " + "; ".join(evolve.rollback(ch)))
        in_background(fn, lambda r: eview.setText(str(r)))

    def do_build():
        if source_mode():
            return src_build()
        try:
            estate["ws"] = evolve.new_change(ask_box.text())
        except ValueError as e:
            eview.setText(str(e))
            return
        build_btn.setEnabled(False)
        apply_btn.setEnabled(False)
        elog.clear()
        ediff.hide()
        eview.setText(f"{agent_pick.currentText()} is working on it…")
        in_background(lambda: evolve.run_agent(estate["ws"], agent_pick.currentText(),
                                               on_line=lambda t: bridge.line.emit(elog.appendPlainText, t)), built)

    def do_apply():
        apply_btn.setEnabled(False)
        in_background(lambda: evolve.apply(estate["ws"], estate["rv"]),
                      lambda r: (eview.setText(("Applied: " + ", ".join(r)) if isinstance(r, list) else f"Didn't apply: {r}"),
                                 fill_hist()))

    def do_discard():
        apply_btn.setEnabled(False)
        discard_btn.setEnabled(False)
        ediff.hide()
        eview.setText("Discarded; nothing was changed.")

    def do_undo():
        row = hist.currentRow()
        if row < 0 or estate["hist"][row]["status"] != "applied":
            eview.setText("Select an applied change to undo.")
            return
        ws_ = Path(estate["hist"][row]["path"])
        in_background(lambda: evolve.undo(ws_), lambda r: (eview.setText("Undone: " + (", ".join(r) if isinstance(r, list)
                                                                                         else str(r))), fill_hist()))
    build_btn.clicked.connect(do_build)
    ask_box.returnPressed.connect(do_build)
    apply_btn.clicked.connect(do_apply)
    discard_btn.clicked.connect(do_discard)
    undo_btn.clicked.connect(do_undo)
    mode_pick.currentIndexChanged.connect(mode_changed)
    approve_btn.clicked.connect(src_approve)
    keep_btn.clicked.connect(lambda: src_finish(True))
    rollback_btn.clicked.connect(lambda: src_finish(False))
    fill_hist()
    stack.addWidget(w)

    # ---------------- Recovery
    from core import recovery
    w, v = page("Recovery", "Get into your PC's firmware settings, start Windows once, or go back to a snapshot.")
    rmsg = QLabel("")
    rmsg.setWordWrap(True)

    rstate = {"last": None, "log": ""}
    retry_btn = QPushButton("Retry")
    copy_btn = QPushButton("Copy log")
    copy_btn.setObjectName("Ghost")
    for b in (retry_btn, copy_btn):
        b.hide()

    def restart_result(res):
        """A restart that didn't happen: the plain reason, with Retry and Copy log."""
        res = res if isinstance(res, dict) else {"ok": False, "reason": recovery.explain(str(res)), "log": str(res)}
        rmsg.setText(res["reason"])
        rstate["log"] = res.get("log", "")
        retry_btn.setVisible(not res["ok"])
        copy_btn.setVisible(not res["ok"])

    def do_restart(entry=None):
        """Restart now (into ``entry`` once): works offline with what the image has, nothing to install first."""
        rstate["last"] = entry
        rmsg.setText("Restarting…")
        retry_btn.hide()
        copy_btn.hide()
        in_background(lambda: recovery.restart(entry), restart_result)

    def run_cmds(cmds, done_text):
        def work():
            log = []
            for c in cmds:
                res = subprocess.run(c, capture_output=True, text=True)
                log.append(f"$ {' '.join(c)}\nexit {res.returncode}\n{(res.stderr or res.stdout).strip()}")
                if res.returncode != 0:
                    return {"ok": False, "reason": recovery.explain(log[-1]), "log": "\n".join(log)}
            return {"ok": True, "reason": done_text, "log": "\n".join(log)}
        rstate["last"] = cmds
        in_background(work, restart_result)

    retry_btn.clicked.connect(lambda: run_cmds(rstate["last"], "Done.") if isinstance(rstate["last"], list)
                              else do_restart(rstate["last"]))
    copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(f"{rmsg.text()}\n\n{rstate['log']}"))
    now = QPushButton("Restart now")
    now.setObjectName("Primary")
    now.clicked.connect(lambda: do_restart())
    v.addWidget(now, 0, Qt.AlignLeft)
    fw = QPushButton("Restart into UEFI firmware settings")
    if not recovery.firmware_setup_supported():
        fw.setEnabled(False)
        fw.setToolTip("This PC's firmware doesn't support it (or it started in legacy BIOS mode).")
    fw.clicked.connect(lambda: run_cmds([recovery.firmware_argv()], "Restarting into the firmware settings…"))
    v.addWidget(fw, 0, Qt.AlignLeft)
    v.addWidget(QLabel("Start from another device once: a USB stick, another disk, the network or another system "
                       "(the normal start order comes back after that). The GRUB menu has the same list under "
                       "“Start from another device”."))
    boot_box = QVBoxLayout()
    v.addLayout(boot_box)
    kind_icon = {"windows": "windows", "usb": "usb", "network": "globe", "halo": "halo", "linux": "power",
                 "shell": "settings", "disk": "drive"}
    kind_word = {"windows": "Windows", "usb": "USB / removable", "network": "Network (PXE)", "halo": "HalOS",
                 "linux": "Linux", "shell": "Firmware tool", "disk": "Disk"}

    def fill_boot(entries):
        from ui import icons
        from ui.theme import current_palette
        color = current_palette().text
        for e in entries if isinstance(entries, list) else []:
            b = QPushButton(f"{e.label} (running now)" if e.current else f"Restart into {e.label}")
            b.setIcon(icons.icon(kind_icon.get(e.kind, "drive"), color, 18))
            b.setToolTip(f"{kind_word.get(e.kind, 'Disk')} · boot entry {e.num}" + ("" if e.active else
                                                                                       " · switched off in the start order"))
            b.setEnabled(not e.current)
            b.clicked.connect(lambda _=False, ent=e: do_restart(ent))
            boot_box.addWidget(b, 0, Qt.AlignLeft)
        if not boot_box.count():
            boot_box.addWidget(QLabel("No boot devices found (this PC started in legacy BIOS mode, or its firmware "
                                      "didn't list any)."))
    in_background(recovery.boot_entries, fill_boot)
    snap_note = QLabel("Snapshots (taken before every app install and update; start an older one from the "
                       "GRUB menu's “HalOS snapshots” if an update goes wrong):")
    snap_note.setWordWrap(True)
    v.addWidget(snap_note)
    snap_list = QListWidget()
    snap_list.setMaximumHeight(160)
    v.addWidget(snap_list)

    def fill_snaps(snaps):
        snap_list.clear()
        if not isinstance(snaps, list):
            snap_list.addItem("Snapshots aren't set up on this system (they need HalOS installed on Btrfs).")
            return
        for s in snaps[:50]:
            snap_list.addItem(f"#{s.number}  {s.date}  {s.description}")
    in_background(recovery.snapshots, fill_snaps)
    take = QPushButton("Take a snapshot now")
    take.clicked.connect(lambda: (run_cmds([recovery.snapshot_now("Taken in SAINT")], "Snapshot taken."),
                                  in_background(recovery.snapshots, fill_snaps)))
    v.addWidget(take, 0, Qt.AlignLeft)
    v.addWidget(rmsg)
    rrow = QHBoxLayout()
    rrow.addWidget(retry_btn)
    rrow.addWidget(copy_btn)
    rrow.addStretch(1)
    v.addLayout(rrow)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Updates
    w, v = page("Updates", "HalOS updates come from Arch Linux's repositories and the AUR (pacman / paru)."
                if is_halo() else "SAINTOS updates come from Fedora's repositories (dnf / Discover).")
    bi = build_info()
    txt = QLabel("\n".join(f"{k}: {bi[k]}" for k in ("halo_version", "arch_snapshot", "saintos_version",
                                                     "fedora_release", "source_commit", "built_at") if k in bi)
                 or f"No {product()} build information (running from a source checkout).")
    v.addWidget(txt)
    ubtn = QPushButton("Update the system now (opens a terminal)")
    umsg = QLabel("")

    def run_update():
        cmd = update_command()
        if not shutil.which(cmd[0]):
            umsg.setText(f"Konsole isn't installed; run `{cmd[-1].split(';')[0]}` in a terminal.")
            return
        subprocess.Popen(cmd, start_new_session=True)
        umsg.setText("Updating in the terminal window.")
    ubtn.clicked.connect(run_update)
    v.addWidget(ubtn, 0, Qt.AlignLeft)
    v.addWidget(umsg)
    # SAINT itself, in place (core/updater.py; the root half is /usr/lib/halo/halo-update).
    from core import updater
    s_head = QLabel("<b>SAINT</b><br>SAINT updates itself from HalOS's GitHub, separately from the system. The "
                    "version before an update is kept, so you can go back in one click.")
    s_head.setWordWrap(True)
    v.addSpacing(12)
    v.addWidget(s_head)
    s_form = QFormLayout()
    s_channel = QComboBox()
    for key, label in (("stable", "Stable (releases)"), ("beta", "Beta (pre-releases too)"),
                       ("dev", "Development (newest commit)")):
        s_channel.addItem(label, key)
    s_channel.setCurrentIndex(max(0, s_channel.findData(config.get("updates.channel", "stable"))))
    s_channel.currentIndexChanged.connect(lambda _i: config.set("updates.channel", s_channel.currentData()))
    s_form.addRow("Channel", s_channel)
    s_auto = QCheckBox("Check once a day and tell me when there's a new SAINT")
    s_auto.setChecked(bool(config.get("updates.auto_check", True)))
    s_auto.toggled.connect(lambda on: config.set("updates.auto_check", bool(on)))
    s_form.addRow("", s_auto)
    v.addLayout(s_form)
    cur = updater.installed()
    s_msg = QLabel("")
    s_msg.setWordWrap(True)
    last = config.get("updates.last_result", {}) or {}
    s_msg.setText(f"This is SAINT {cur['version'] or '?'}" + (f" ({cur['sha'][:7]})" if cur["sha"] else "") + "."
                  + (f" Last check: {last.get('message')}" if last.get("message") else ""))
    s_found = {}
    s_row = QHBoxLayout()
    s_check = QPushButton("Check now")
    s_install = QPushButton("Install the update")
    s_install.setObjectName("Primary")
    s_install.hide()
    s_back = QPushButton("Go back to the previous SAINT")
    s_back.setObjectName("Ghost")
    s_back.setVisible(updater.can_rollback())
    for b_ in (s_check, s_install, s_back):
        s_row.addWidget(b_)
    s_row.addStretch(1)
    v.addLayout(s_row)
    v.addWidget(s_msg)

    def s_checked(r):
        r = r if isinstance(r, dict) else {"ok": False, "message": str(r)}
        s_found.clear()
        s_found.update(r)
        s_msg.setText(r["message"] + (f"\n\n{r['notes'][:600]}" if r.get("available") and r.get("notes") else ""))
        s_install.setVisible(bool(r.get("available")))
        s_check.setEnabled(True)

    def s_do_check():
        s_check.setEnabled(False)
        s_msg.setText("Checking…")
        in_background(updater.check, s_checked)

    def s_finished(res):
        res = res if isinstance(res, dict) else {"ok": False, "message": str(res)}
        s_msg.setText(res["message"])
        for b_ in (s_check, s_install, s_back):
            b_.setEnabled(True)
        if res["ok"]:
            updater.restart_now()

    def s_run(fn, text):
        for b_ in (s_check, s_install, s_back):
            b_.setEnabled(False)
        s_msg.setText(text)
        in_background(fn, s_finished)
    s_check.clicked.connect(s_do_check)
    s_install.clicked.connect(lambda: s_run(lambda: updater.install(dict(s_found)), "Downloading and installing…"))
    s_back.clicked.connect(lambda: s_run(updater.rollback, "Going back…"))
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Pages in their own files (ui/settings_pages)
    for mod in extra_pages:
        try:
            stack.addWidget(mod.build())
        except Exception as e:
            log.exception("settings page %s failed to build", mod.TITLE)
            w, v = page(mod.TITLE)
            v.addWidget(QLabel(f"This page couldn't open: {e}"))
            v.addStretch(1)
            stack.addWidget(w)

    # ---------------- The rail's order: every row a page, SAINT's categories with their heading
    built = dict(zip(PAGES + [m.TITLE for m in extra_pages], stack.built))
    headings = {name for name, icon_name in rows if not icon_name}
    category_subtitles = {"AI": "The language model, how SAINT uses it, vision and web search.",
                          "Voice": "Wake word, speech recognition and the voice all run on this machine."}
    for name in page_names:
        if name in headings:
            pages_stack.addWidget(QWidget())
        elif name in settings.category_pages:
            w, v = page(name, category_subtitles.get(name, ""))
            v.setContentsMargins(32, 26, 20, 8)
            v.addWidget(settings.category_pages[name], 1)
            pages_stack.addWidget(w)
        else:
            pages_stack.addWidget(built.pop(name))
    for unused in built.values():                # the OS pages where they don't apply
        unused.deleteLater()

    def is_heading(row):
        return page_names[row] in headings

    def row_changed(i):
        if i < 0:
            return
        if is_heading(i):                        # a heading is never a destination
            nav.setCurrentRow(i + 1)
            return
        pages_stack.setCurrentIndex(i)
        settings.setVisible(page_names[i] in settings.category_pages)
        if page_names[i] == "Service":
            refresh_service()
        if on_group_changed:
            on_group_changed(group_of(page_names[i], rows))
    nav.currentRowChanged.connect(row_changed)

    by_lower = {name.lower(): i for i, name in enumerate(page_names) if name not in headings}

    def open_page(name: str) -> bool:
        low = (name or "").lower()
        row = by_lower.get(OLD_PAGE_NAMES.get(low, low))
        if row is None:
            return False
        rail.search.clear()
        nav.item(row).setHidden(False)           # also Welcome, once it's been asked for by name
        nav.setCurrentRow(row)
        return True

    def open_group(group: str):
        """Keep the current page when it's in ``group``; else that group's first page that's showing."""
        current = nav.currentRow()
        if current >= 0 and not is_heading(current) and group_of(page_names[current], rows) == group:
            return
        for row, name in enumerate(page_names):
            if name not in headings and not nav.item(row).isHidden() and group_of(name, rows) == group:
                nav.setCurrentRow(row)
                return

    # Search: everything a page says, including pages from other files, no list to keep up to date.
    def page_text(widget) -> str:
        parts = [o.text() for o in widget.findChildren(QLabel) + widget.findChildren(QAbstractButton)]
        parts += [o.title() for o in widget.findChildren(QGroupBox)]
        parts += [o.placeholderText() for o in widget.findChildren(QLineEdit)]
        return " ".join(parts).lower()
    index = {row: f"{page_names[row]} {page_text(pages_stack.widget(row))}".lower()
             for row in range(len(page_names)) if not is_heading(row)}

    def welcome_hidden():
        return "Welcome" in page_names and welcome_done_mark().exists()

    def filter_rows(text: str):
        q = text.strip().lower()
        first = None
        heading_row = None
        any_in_group = False

        def close_group():
            if heading_row is not None:
                nav.item(heading_row).setHidden(not any_in_group)
        for row, name in enumerate(page_names):
            if is_heading(row):
                close_group()
                heading_row, any_in_group = row, False
                continue
            match = (q in index[row]) if q else not (name == "Welcome" and welcome_hidden())
            nav.item(row).setHidden(not match)
            if match:
                any_in_group = True
                if first is None:
                    first = row
        close_group()
        if q and first is not None:
            nav.setCurrentRow(first)
    rail.search.textChanged.connect(filter_rows)

    if "Welcome" in page_names:
        def welcome_done():
            mark = welcome_done_mark()
            mark.parent.mkdir(parents=True, exist_ok=True)
            mark.touch()
            nav.item(page_names.index("Welcome")).setHidden(True)
            nav.setCurrentRow(next(r for r, n in enumerate(page_names)
                                   if n not in headings and n != "Welcome" and group_of(n, rows) == HALOS))
        done_btn.clicked.connect(welcome_done)
        nav.item(page_names.index("Welcome")).setHidden(welcome_hidden())
    settings.hide()
    if not open_page(start_page):
        open_group(HALOS if os_pages else SAINT)
    if nav.currentRow() < 0:
        open_group(SAINT)
    win._stack, win._nav, win._rail, win._settings = pages_stack, nav, rail, settings
    win._open, win._open_group, win._page_names = open_page, open_group, page_names
    return win


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="HalOS settings")
    ap.add_argument("--welcome", action="store_true", help="open on the Welcome page (first login)")
    ap.add_argument("--page", default="", help=f"open on one page: {', '.join(PAGES)}")
    args = ap.parse_args(argv)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(f"{product()} Settings")
    app.setDesktopFileName("saintos-control")
    try:
        from core.config import config
        from ui.theme import build_stylesheet
        a = config.get("appearance", {}) or {}
        font = "Inter" if os.name != "nt" else "Segoe UI"       # HalOS' interface font (etc/xdg/kdeglobals)
        app.setStyleSheet(build_stylesheet(a.get("theme", "Dark"), a.get("accent", "#feaa34"), font))
    except Exception as e:                          # the window still works with Plasma's own style
        print(f"saintos-control: SAINT's theme didn't load ({e}); using the system style", file=sys.stderr)
    win = build_window("Welcome" if args.welcome else (args.page or "Welcome"))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
