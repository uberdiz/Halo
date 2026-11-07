"""
ui/saintos_center.py

SAINTOS Control Center: one window for the parts of SAINT that belong to the operating system.

    Welcome       what SAINTOS is and the three things to do first
    Apps          points at SAINT Store, the one place to get apps
    Service       SAINT's user service: status, start / stop / restart, start at login, recent log
    AI            provider, model and address; detects a local Ollama and lists its models
    Voice         microphone, wake word, speech recognition / voice backends
    Permissions   Safe / Confirm / Autonomous (core/permissions.py — the same gate SAINT uses)
    Capabilities  what this desktop lets SAINT do and how to fix what's missing (core/platform_caps.py)
    Data          where SAINT keeps settings, memory and models; open the folder
    Diagnostics   SAINT's self-test and a full read-only diagnostics folder
    Updates       Fedora updates through Discover; the SAINTOS build this system came from

    python -m ui.saintos_center [--welcome] [--page NAME]

Every button does what it says through SAINT's own modules (core.config, core.permissions,
modules.ai.providers, core.platform_caps) or systemctl --user; nothing here needs root.
Settings it writes are the same keys SAINT's own Settings page edits.
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
    if provider not in ("ollama", "openai"):
        raise ValueError("provider must be ollama or openai")
    if not model.strip():
        raise ValueError("choose a model")
    config.set("ai.provider", provider, persist=False)
    config.set("ai.model", model.strip(), persist=False)
    config.set("ai.base_url", base_url.strip() or "http://localhost:11434", persist=True)


def microphones() -> List[str]:
    try:
        import sounddevice as sd
        return sorted({d["name"] for d in sd.query_devices() if d.get("max_input_channels", 0) > 0})
    except Exception:
        return []


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
PAGES = ["Welcome", "Apps", "Service", "AI", "Voice", "Permissions", "Capabilities", "Data", "Diagnostics",
         "Desktop & devices", "Evolve", "Recovery", "Updates"]
# Icons in the left rail (ui/icons.py names), one per page above.
PAGE_ICONS = {"Welcome": "home", "Apps": "download", "Service": "power", "AI": "sparkles", "Voice": "mic",
              "Permissions": "check-circle", "Capabilities": "zap", "Data": "drive", "Diagnostics": "activity",
              "Desktop & devices": "smartphone", "Evolve": "command", "Recovery": "refresh", "Updates": "arrow-up"}

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


def build_window(start_page: str = "Welcome"):
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QListWidget, QMainWindow, QPlainTextEdit, QPushButton, QRadioButton,
                                   QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
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
    win.setWindowTitle(product())
    win.setWindowIcon(QIcon(str(Path(__file__).parent.parent / "data" / "brand" / "halos-256.png")))
    win.resize(980, 640)
    root = QWidget()
    h = QHBoxLayout(root)
    h.setContentsMargins(0, 0, 0, 0)
    from ui.components.side_rail import SideRail
    from ui import settings_pages
    extra_pages = settings_pages.discover()
    page_names = PAGES + [m.TITLE for m in extra_pages]
    rail = SideRail("SAINT", "Control Center" if not is_halo() else "HalOS",
                    [(p, PAGE_ICONS[p]) for p in PAGES] + [(m.TITLE, m.ICON) for m in extra_pages])
    nav = rail.nav
    stack = QStackedWidget()
    h.addWidget(rail)
    h.addWidget(stack, 1)
    win.setCentralWidget(root)

    # ---------------- Welcome
    halo = is_halo()
    w, v = page(f"Welcome to {product()}", f"{os_name()} — KDE Plasma with SAINT built in.")
    info = QLabel(
        f"{product()} is a normal {'Arch Linux' if halo else 'Fedora'} KDE desktop: everything works without "
        "SAINT, without a network and without an AI model.\n\nTo get SAINT talking:\n"
        "  1. AI — " + ("Ollama is built in and downloads its default model (about 5 GB) in the background once you're "
                       "online (AI page: see it, change it, test a reply)" if halo else
                       "install Ollama and pull one model you choose") + ", or point SAINT at a provider you "
        "already use.\n"
        "  2. Voice — pick your microphone. SAINT's speech models download the first time you start it.\n"
        "  3. Service — start SAINT now, and turn on “start at login” if you want it always there.\n\n"
        + ("Halo is built from Arch Linux packages; it isn't an official Arch Linux product." if halo else
           "SAINTOS is a Fedora Remix: built from Fedora Linux packages, not an official Fedora product."))
    info.setWordWrap(True)
    v.addWidget(info)
    wrow = QHBoxLayout()
    open_btn = QPushButton("Open SAINT")
    open_btn.clicked.connect(lambda: launch_saint())
    apps_btn = QPushButton("Install my apps…")
    apps_btn.clicked.connect(lambda: nav.setCurrentRow(PAGES.index("Apps")))
    wrow.addWidget(open_btn)
    wrow.addWidget(apps_btn)
    from core import windows_migration
    if "Migrate from Windows" in page_names and windows_migration.should_offer():    # offered once
        windows_migration.mark_offered()
        migrate_btn = QPushButton("Bring my files and apps from Windows…")
        migrate_btn.clicked.connect(lambda: nav.setCurrentRow(page_names.index("Migrate from Windows")))
        wrow.addWidget(migrate_btn)
    wrow.addStretch(1)
    v.addLayout(wrow)
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

    # ---------------- AI
    w, v = page("AI", "Local first: Ollama on this machine. Hosted providers are optional.")
    form = QFormLayout()
    provider = QComboBox()
    provider.addItems(["ollama", "openai"])
    provider.setCurrentText(config.get("ai.provider", "ollama") if config.get("ai.provider") in ("ollama", "openai")
                            else "ollama")
    model = QComboBox()
    model.setEditable(True)
    model.setCurrentText(config.get("ai.model", ""))
    base = QLineEdit(config.get("ai.base_url", "http://localhost:11434"))
    form.addRow("Provider", provider)
    form.addRow("Model", model)
    form.addRow("Address", base)
    v.addLayout(form)
    ai_status = QLabel("")
    ai_status.setWordWrap(True)
    v.addWidget(ai_status)
    note = QLabel("Hosted providers (OpenAI-compatible): the API key is still entered in SAINT's own Settings and "
                  "kept in KWallet (Secret Service), never in the config file. Spending limits are planned "
                  "(HALOS_ROADMAP.md).")
    note.setWordWrap(True)
    note.setObjectName("Muted")
    v.addWidget(note)
    btns = QHBoxLayout()
    detect = QPushButton("Detect local models")
    save = QPushButton("Save")

    def show_ollama(res):
        if isinstance(res, Exception):
            ai_status.setText(f"Detection failed: {res}")
            return
        if res["running"]:
            current = model.currentText()
            model.clear()
            model.addItems(res["models"])
            model.setCurrentText(current or (res["models"][0] if res["models"] else ""))
            ai_status.setText(f"Ollama is running with {len(res['models'])} model(s)." if res["models"] else
                              "Ollama is running but has no models. Pull one you choose, e.g. "
                              "`ollama pull llama3.1:8b` (about 4.9 GB), or Download model below.")
        elif res["installed"]:
            ai_status.setText(f"Ollama is installed but not answering ({res['error']}). Start it: "
                              "`systemctl start ollama` or `ollama serve`.")
        else:
            ai_status.setText("Ollama isn't installed. SAINT still runs its commands without a model; chat and "
                              "planning need one. See https://ollama.com/download/linux.")
    detect.clicked.connect(lambda: in_background(lambda: detect_ollama(base.text()), show_ollama))

    def do_save():
        try:
            save_ai(provider.currentText(), model.currentText(), base.text())
            ai_status.setText("Saved. SAINT picks this up the next time it starts (Service › Restart).")
        except ValueError as e:
            ai_status.setText(str(e))
    save.clicked.connect(do_save)
    # A real prompt to the chosen model: "running" alone doesn't mean the model answers.
    test_ai = QPushButton("Test a reply")

    def tested_ai(res):
        test_ai.setEnabled(True)
        ai_status.setText(f"Test failed: {res}" if isinstance(res, Exception) else
                          ("Working — " if res["state"] == "working" else "FAILED — ") + res["detail"])

    def run_ai_test():
        from core import health
        if not model.currentText():
            ai_status.setText("Pick or pull a model first (Detect local models).")
            return
        test_ai.setEnabled(False)
        ai_status.setText(f"Asking {model.currentText()} for a one-word reply…")
        in_background(lambda: health.ollama_inference(base.text(), model.currentText()), tested_ai)
    test_ai.clicked.connect(run_ai_test)
    # Download the chosen model with its progress (core/model_pull.py; also on SAINT's System page).
    pull_btn = QPushButton("Download model")
    pull_timer = QTimer(w)

    def show_pull():
        from core import model_pull
        s = model_pull.state()
        if s.get("model"):
            ai_status.setText(model_pull.describe(s))
        pull_btn.setEnabled(not s.get("running"))
        if not s.get("running"):
            pull_timer.stop()

    def run_pull():
        from core import model_pull
        name = model.currentText().strip()
        if not name:
            ai_status.setText("Type the model to download, e.g. llama3.1:8b.")
            return
        if not model_pull.start(base.text(), name):
            ai_status.setText("A model is already downloading.")
        pull_timer.start(1000)
        show_pull()
    pull_timer.timeout.connect(show_pull)
    pull_btn.clicked.connect(run_pull)
    btns.addWidget(detect)
    btns.addWidget(pull_btn)
    btns.addWidget(test_ai)
    btns.addWidget(save)
    btns.addStretch(1)
    v.addLayout(btns)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Voice
    w, v = page("Voice", "Wake word, speech recognition and the voice all run on this machine.")
    form = QFormLayout()
    mic = QComboBox()
    mic.addItem("System default")
    mic.addItems(microphones())
    if config.get("voice.mic_device"):
        mic.setCurrentText(str(config.get("voice.mic_device")))
    wake = QCheckBox("Listen for “Hey SAINT”")
    wake.setChecked(bool(config.get("voice.wake_word_enabled", True)))
    auto = QCheckBox("Start the microphone when SAINT starts")
    auto.setChecked(bool(config.get("voice.auto_start", True)))
    form.addRow("Microphone", mic)
    form.addRow("", wake)
    form.addRow("", auto)
    v.addLayout(form)
    # What SAINT really speaks and hears with, from files and tests (core/voice_check.py), never the config alone.
    from PySide6.QtWidgets import QFrame, QGridLayout as _Grid
    sheet = QFrame()
    sheet.setObjectName("Panel")
    vgrid = _Grid(sheet)
    vgrid.setContentsMargins(18, 14, 18, 14)
    vgrid.setHorizontalSpacing(18)
    vgrid.setVerticalSpacing(9)
    vgrid.setColumnStretch(2, 1)
    vstat = QLabel("Checking the voice system…")
    vstat.setObjectName("Muted")
    vgrid.addWidget(vstat, 0, 0, 1, 3)
    v.addWidget(sheet)

    def voice_service():
        try:
            from modules.voice.tts_service import TTSService
            return TTSService._instance if getattr(TTSService, "_instance", None) else None
        except Exception:
            return None

    def voice_tone(text):
        """A state mark for a status line: green when it's proven, red when it's broken or a fallback."""
        low = text.lower()
        if any(w in low for w in ("missing", "failed", "not kokoro", "fallback", "none (", "unavailable",
                                  "recorded silence")):
            return "danger"
        if low.startswith(("passed", "kokoro (", "kokoro ready")) or "(present)" in low or "(downloaded)" in low:
            return "success"
        return ""

    def show_voice(res):
        from ui.theme import current_palette
        p = current_palette()
        while vgrid.count():
            item = vgrid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if isinstance(res, Exception):
            vgrid.addWidget(QLabel(f"Couldn't read the voice system: {res}"), 0, 0, 1, 3)
            return
        for row, (k, val) in enumerate(res.items()):
            tone = voice_tone(str(val))
            dot = QLabel("●" if tone else "○")
            dot.setStyleSheet(f"color: {getattr(p, tone) if tone else p.faint}; font-size: 10px;")
            key = QLabel(k.upper())
            key.setObjectName("StatLabel")
            value = QLabel(str(val))
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            vgrid.addWidget(dot, row, 0)
            vgrid.addWidget(key, row, 1)
            vgrid.addWidget(value, row, 2)

    def refresh_voice():
        from core import voice_check
        in_background(lambda: voice_check.status(voice_service()), show_voice)

    trow = QHBoxLayout()
    test_tts = QPushButton("Test Kokoro voice")
    test_stt = QPushButton("Test Whisper")
    tmsg = QLabel("")
    tmsg.setWordWrap(True)
    for b in (test_tts, test_stt):
        trow.addWidget(b)
    trow.addStretch(1)
    v.addLayout(trow)
    v.addWidget(tmsg)

    def tested(res):
        test_tts.setEnabled(True)
        test_stt.setEnabled(True)
        if isinstance(res, Exception):
            tmsg.setText(f"Test failed: {res}")
        else:
            tmsg.setText(("Passed — " if res["ok"] else "FAILED — ") + res["detail"])
        refresh_voice()

    def run_test(which):
        from core import voice_check
        test_tts.setEnabled(False)
        test_stt.setEnabled(False)
        if which == "kokoro":
            tmsg.setText("Synthesising with Kokoro (downloads the voice first if it's missing)…")
            in_background(voice_check.test_kokoro, tested)
        else:
            in_background(lambda: voice_check.test_whisper(
                on_status=lambda t: bridge.line.emit(tmsg.setText, t)), tested)
    test_tts.clicked.connect(lambda: run_test("kokoro"))
    test_stt.clicked.connect(lambda: run_test("whisper"))
    refresh_voice()
    vsave = QPushButton("Save")
    vmsg = QLabel("")

    def save_voice():
        config.set("voice.mic_device", None if mic.currentIndex() == 0 else mic.currentText(), persist=False)
        config.set("voice.wake_word_enabled", wake.isChecked(), persist=False)
        config.set("voice.auto_start", auto.isChecked(), persist=True)
        vmsg.setText("Saved. Restart SAINT to use the new microphone.")
    vsave.clicked.connect(save_voice)
    v.addWidget(vsave, 0, Qt.AlignLeft)
    v.addWidget(vmsg)
    if not microphones():
        v.addWidget(QLabel("No microphone found (PipeWire reports no input devices)."))
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Permissions
    w, v = page("Permissions", "Every action SAINT takes has a risk level; this decides which ones ask first.")
    group = QButtonGroup(w)
    current = config.get("automation.permission_mode", "confirm")
    pmsg = QLabel("")
    for key, name, desc in PERMISSION_MODES:
        rb = QRadioButton(f"{name} — {desc}")
        rb.setChecked(key == current)
        rb.toggled.connect(lambda on, k=key: on and (set_permission_mode(k), pmsg.setText(f"Mode: {k}. Saved.")))
        group.addButton(rb)
        v.addWidget(rb)
    v.addWidget(pmsg)
    v.addWidget(QLabel("Moving files to the trash, uninstalling, power and force-quit always ask, in every mode."))
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
    v.addWidget(QLabel("Secrets (Spotify login, Link key) are kept in KWallet through the Secret Service."))
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

    # ---------------- Desktop & devices: the everyday settings, each opening KDE's own page for it
    w, v = page("Desktop & devices", "The settings people change most. Each opens Plasma's own settings page; "
                                      "everything else is in All settings.")
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

    # ---------------- Evolve: change Halo with an AI agent (core/evolve.py)
    from core import evolve
    w, v = page("Evolve", "Describe a change to your desktop and let Claude (or another AI agent) build it. You see "
                          "exactly what changes before anything is applied, and every change can be undone.")
    ask_box = QLineEdit()
    ask_box.setPlaceholderText("e.g. make window animations slower · a widget with my GPU temperature · "
                               "pause Spotify when my headphones disconnect")
    v.addWidget(ask_box)
    erow = QHBoxLayout()
    mode_pick = QComboBox()
    mode_pick.addItems(["Your desktop", "SAINT / Halo itself (source code)"])
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
            eview.setText("No SAINT source checkout found. Clone the Halo repository and set evolve.repo in "
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

    def run_cmds(cmds, done_text):
        def work():
            for c in cmds:
                res = subprocess.run(c, capture_output=True, text=True)
                if res.returncode != 0:
                    return f"Didn't work: {(res.stderr or res.stdout).strip()[:200] or ' '.join(c)}"
            return done_text
        in_background(work, lambda r: rmsg.setText(str(r)))

    fw = QPushButton("Restart into UEFI firmware settings")
    if not recovery.firmware_setup_supported():
        fw.setEnabled(False)
        fw.setToolTip("This PC's firmware doesn't support it (or it started in legacy BIOS mode).")
    fw.clicked.connect(lambda: run_cmds([recovery.REBOOT_TO_FIRMWARE], "Restarting into the firmware settings…"))
    v.addWidget(fw, 0, Qt.AlignLeft)
    v.addWidget(QLabel("Start another system once (the normal start order comes back after that):"))
    boot_box = QVBoxLayout()
    v.addLayout(boot_box)

    def fill_boot(entries):
        for e in entries if isinstance(entries, list) else []:
            if e.current:
                continue
            b = QPushButton(f"Restart into {e.label}")
            b.clicked.connect(lambda _=False, ent=e: run_cmds(recovery.boot_once(ent), f"Restarting into {ent.label}…"))
            boot_box.addWidget(b, 0, Qt.AlignLeft)
        if not boot_box.count():
            boot_box.addWidget(QLabel("No other system found on this PC."))
    in_background(recovery.boot_entries, fill_boot)
    v.addWidget(QLabel("Snapshots (taken before every app install and update; start an older one from the "
                       "GRUB menu's “Halo snapshots” if an update goes wrong):"))
    snap_list = QListWidget()
    snap_list.setMaximumHeight(160)
    v.addWidget(snap_list)

    def fill_snaps(snaps):
        snap_list.clear()
        if not isinstance(snaps, list):
            snap_list.addItem("Snapshots aren't set up on this system (they need Halo installed on Btrfs).")
            return
        for s in snaps[:50]:
            snap_list.addItem(f"#{s.number}  {s.date}  {s.description}")
    in_background(recovery.snapshots, fill_snaps)
    take = QPushButton("Take a snapshot now")
    take.clicked.connect(lambda: (run_cmds([recovery.snapshot_now("Taken in SAINT")], "Snapshot taken."),
                                  in_background(recovery.snapshots, fill_snaps)))
    v.addWidget(take, 0, Qt.AlignLeft)
    v.addWidget(rmsg)
    v.addStretch(1)
    stack.addWidget(w)

    # ---------------- Updates
    w, v = page("Updates", "Halo updates come from Arch Linux's repositories and the AUR (pacman / paru)."
                if is_halo() else "SAINTOS updates come from Fedora's repositories (dnf / Discover).")
    bi = build_info()
    txt = QLabel("\n".join(f"{k}: {bi[k]}" for k in ("halo_version", "arch_snapshot", "saintos_version",
                                                     "fedora_release", "source_commit", "built_at") if k in bi)
                 or f"No {product()} build information (running from a source checkout).")
    v.addWidget(txt)
    ubtn = QPushButton("Update now (opens a terminal)")
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
    v.addWidget(QLabel(f"SAINT itself (/opt/saint) is updated by installing a newer {product()} build; an in-place "
                       "SAINT updater is planned."))
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

    nav.currentRowChanged.connect(stack.setCurrentIndex)
    nav.currentRowChanged.connect(lambda i: page_names[i] == "Service" and refresh_service())
    by_lower = {name.lower(): i for i, name in enumerate(page_names)}
    nav.setCurrentRow(by_lower.get(start_page.lower(), 0))
    win._stack, win._nav = stack, nav            # for tests
    return win


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SAINTOS Control Center")
    ap.add_argument("--welcome", action="store_true", help="open on the Welcome page (first login)")
    ap.add_argument("--page", default="", help=f"open on one page: {', '.join(PAGES)}")
    args = ap.parse_args(argv)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(f"{product()} Control Center")
    app.setDesktopFileName("saintos-control")
    try:
        from core.config import config
        from ui.theme import build_stylesheet
        a = config.get("appearance", {}) or {}
        font = "Noto Sans" if os.name != "nt" else "Segoe UI"
        app.setStyleSheet(build_stylesheet(a.get("theme", "Dark"), a.get("accent", "#feaa34"), font))
    except Exception as e:                          # the window still works with Plasma's own style
        print(f"saintos-control: SAINT's theme didn't load ({e}); using the system style", file=sys.stderr)
    win = build_window("Welcome" if args.welcome else (args.page.title() if args.page else "Welcome"))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
