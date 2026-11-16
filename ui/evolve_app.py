"""
ui/evolve_app.py

Evolve as its own app (`halos-evolve`): Claude Code working on HalOS, with what Claude's own app shows.

    Sessions      any number of agent sessions side by side, each on Claude or on the local models (one can
                  work on Claude while another works locally); the header shows every session live and the
                  subscription usage ring (click it for the 5-hour / weekly limits)
    Claude        chat with Claude Code (your subscription): model, folder, how much it may do, attach files or a
                  pasted screenshot; every step it takes, its tokens, cost and your 5-hour / weekly usage live;
                  the same output in a Konsole window; "Ask Llama" asks the local model what Claude is doing now
    Notes to fix  the notes made with right-click › Note to fix (core/fix_notes.py); Fix with Claude
    Vault         SAINT's Obsidian vault: browse, read, open in Obsidian, new note

Runs `claude -p --output-format stream-json --verbose` with the prompt on stdin; a follow-up resumes the session.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QProcess, QProcessEnvironment, QRectF, Qt, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import (QColor, QDesktopServices, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut,
                           QTextCursor)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSplitter, QTabWidget, QTextBrowser, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget, QDialog, QDialogButtonBox)

from core import claude_agent, evolve_chat

INSTANCE = "evolve"
SAINT_SRC = "/opt/saint/app"
LOG = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "saint" / "evolve" / "console.log"
USAGE = LOG.with_name("usage.json")
CHATS = LOG.with_name("chats")          # every session's transcript, to read again or carry on (History)      # the last subscription limits Claude Code reported, for the usage ring
MODELS = [("Default", ""), ("Sonnet", "sonnet"), ("Opus", "opus"), ("Haiku", "haiku"), ("Fable", "fable")]
BACKENDS = [("Claude (subscription)", "claude"), ("Local models (free, offline)", "local")]
TRUST = [("Edit files, ask nothing else", "acceptEdits"), ("Plan only (read-only)", "plan"),
         ("Auto (Claude's safety checks)", "auto")]
CONTEXT = ("You are running inside HalOS's Evolve app (Arch Linux, KDE Plasma 6, Wayland). SAINT's live source is "
           f"{SAINT_SRC}; edits there take effect after SAINT restarts (`pkill -f 'ui.halo_app'` etc. — tell the user "
           "which part to restart rather than doing it). Keep a short TodoWrite list so the user can follow along, and "
           "finish with two or three sentences: what changed and what the user must do.")
# Claude only (local models get evolve_chat.LOCAL_RULES instead: no extras, no sub-agents, SAINT runs the checks).
CONTEXT += (" Also add the small extras that clearly complement the request (a setting, a shortcut, an error "
            "message, a test) when they fit the existing design; list them at the end. SAINT compiles the changed "
            "files and runs their tests when you stop; for anything visible, also run the `ui-checker` agent.")
PREFLIGHT = ("You prepare a coding request for an agent working on HalOS (SAINT is its voice assistant app with a "
             "main window, an overlay and an avatar, on Arch Linux with KDE Plasma). Do not solve it. Reply with JSON "
             "only: {\"scope\": \"small\" | \"medium\" | \"large\", \"summary\": \"the task in one sentence\", "
             "\"questions\": [{\"q\": \"...\", \"options\": [\"...\", \"...\"]}], \"needs\": [\"...\"]}. "
             "questions: at most 4, only about what the user wants to SEE or HAPPEN when the answer changes what "
             "gets built (what a shortcut should open, which window, what happens in an edge case). The agent reads "
             "the code itself: never ask about file names, executables, APIs or how the code works. For a small job ask one "
             "question at most, and none when a sensible default exists. An empty list "
             "when the request is clear. needs: only real things the user must approve: a package or model to "
             "download, a root command, a paid service, an account. Usually an empty list. Never invent requirements.")
MAX_FIX_RETRIES = 1                      # how often a local model is sent back to fix what SAINT's checks found


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pct(x) -> str:
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "?"


def _pal():
    try:
        from ui.theme import current_palette
        return current_palette()
    except Exception:
        from types import SimpleNamespace
        return SimpleNamespace(text="#e6e6e6", muted="#9a9a9a", faint="#666", accent="#feaa34", accent_soft="#3a2e1c",
                               surface="#1b1d23", surface2="#23262d", border="#2c2f36", border_strong="#3a3e46",
                               success="#4caf72", warning="#e8b04a", danger="#e5534b", info="#7aa7ff")


def _bubble(who: str, body: str, you: bool = False) -> str:
    """One chat message as a tinted block with a coloured edge (QTextBrowser's rich text: tables, not divs)."""
    p = _pal()
    edge, bg = (p.accent, p.accent_soft) if you else (p.info, p.surface2)
    return (f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:10px'><tr>"
            f"<td width='3' bgcolor='{edge}'></td><td bgcolor='{bg}' style='padding:8px 12px'>"
            f"<span style='color:{p.muted};font-size:small;font-weight:600'>{who}</span><br>{body}</td></tr></table>")


def _usage_color(u: float) -> str:
    p = _pal()
    return p.success if u < 0.5 else p.warning if u < 0.8 else p.danger


def _window_name(key: str) -> str:
    """five_hour -> 5-hour, seven_day_opus -> Weekly · Opus."""
    head = {"five_hour": "5-hour", "seven_day": "Weekly"}
    for k, v in head.items():
        if key == k:
            return v
        if key.startswith(k + "_"):
            return f"{v} · {key[len(k) + 1:].replace('_', ' ').title()}"
    return key.replace("_", " ").title()


def _when(ts) -> str:
    try:
        secs = int(int(ts) - time.time())
    except (TypeError, ValueError):
        return ""
    if secs <= 0:
        return "now"
    h, m = divmod(secs // 60, 60)
    return f"{h}h {m}m" if h < 48 else f"{h // 24}d"


class _Ask(QThread):
    """One question to the local model, off the UI thread."""
    done = Signal(str)

    def __init__(self, prompt: str, system: str = "", model: str = "", extra: dict = None, haiku: bool = False):
        super().__init__()
        self.prompt, self.system, self.model, self.extra, self.haiku = prompt, system, model, extra or {}, haiku

    def run(self):
        if self.haiku:                     # Claude backend: the small Claude model, no tools, your subscription
            import subprocess
            try:
                r = subprocess.run([claude_agent.claude_path() or "claude", "-p", "--model", "haiku", "--tools", "",
                                    "--system-prompt", self.system, "--output-format", "text"], input=self.prompt,
                                   capture_output=True, text=True, timeout=120, env=claude_agent.subscription_env())
                return self.done.emit((r.stdout or "").strip() or "No answer.")
            except Exception as e:
                return self.done.emit(f"The local model didn't answer ({type(e).__name__}).")
        import requests
        try:
            from core.config import config
            model = self.model or config.get("ai.model", "llama3.1:8b") or "llama3.1:8b"
            base = (config.get("ai.base_url", "http://localhost:11434") or "http://localhost:11434").rstrip("/")
        except Exception:
            model, base = "llama3.1:8b", "http://localhost:11434"
        try:
            system = self.system or ("You watch a coding agent (Claude Code) work and answer the user's question "
                                     "about it in two or three plain sentences, from the log only. No code, no lists "
                                     "unless asked.")
            body = {"model": model, "stream": False, "keep_alive": "10m", "options": {"temperature": 0.2, "num_predict": 220},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": self.prompt}]}
            for k, val in self.extra.items():
                body[k] = {**body[k], **val} if isinstance(val, dict) and k in body else val
            r = requests.post(base.replace("localhost", "127.0.0.1") + "/api/chat", timeout=120, json=body)
            self.done.emit(r.json().get("message", {}).get("content", "").strip() or "No answer.")
        except Exception as e:
            self.done.emit(f"The local model didn't answer ({type(e).__name__}). Is Ollama running?")


class _Job(QThread):
    """One slow, model-free job (the checks after a run) off the UI thread."""
    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            self.done.emit((False, f"{type(e).__name__}: {e}", []))


class PreflightDialog(QDialog):
    """The questions a small model has before the agent starts, and what needs your OK, answered once."""

    def __init__(self, brief: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Before Evolve starts")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        size = {"small": "Small job", "medium": "Medium job", "large": "Large job"}.get(brief["scope"], "Job")
        head = QLabel(f"<b>{size}</b>: {_esc(brief['summary'])}" if brief["summary"] else f"<b>{size}</b>")
        head.setWordWrap(True)
        v.addWidget(head)
        self.qs, self.needs = [], []
        for q in brief["questions"]:
            lab = QLabel(_esc(q["q"]))
            lab.setWordWrap(True)
            v.addWidget(lab)
            box = QComboBox()
            box.setEditable(True)
            box.addItems(q["options"] + ["You decide"])
            box.setToolTip("Pick one or type your own answer")
            v.addWidget(box)
            self.qs.append((q["q"], box))
        if brief["needs"]:
            v.addWidget(QLabel("<b>Needs your OK</b> (untick what Evolve must not install or use):"))
        for n in brief["needs"]:
            c = QCheckBox(n)
            c.setChecked(True)
            v.addWidget(c)
            self.needs.append(c)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Start")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def answers_text(self) -> str:
        out = [f"- {q} -> {box.currentText().strip() or 'You decide'}" for q, box in self.qs]
        yes = [c.text() for c in self.needs if c.isChecked()]
        no = [c.text() for c in self.needs if not c.isChecked()]
        if yes:
            out.append("- Approved: " + "; ".join(yes))
        if no:
            out.append("- NOT approved (work around it or leave it out): " + "; ".join(no))
        return "\n\nThe user already answered these (don't ask again):\n" + "\n".join(out) if out else ""


class ActivityWidget(QWidget):
    """A small always-on-top strip, like the mini player: what the Evolve agent is doing now, and Stop."""
    PLACE_NAME = "Evolve activity"

    def __init__(self, tab):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.tab, self.moved = tab, False
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setToolTip("Drag to move")
        from ui import placement
        placement.wayland_helper(self, self.PLACE_NAME)
        self.setStyleSheet("background: #1b1d23; color: #ddd; border-radius: 8px; font-size: 12px")
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 6, 6)
        self.text = QLabel("Evolve")
        self.text.setFixedWidth(330)
        stop = QPushButton("Stop")
        stop.clicked.connect(tab.stop)
        show = QPushButton("Open")
        show.clicked.connect(lambda: (tab.window().showNormal(), tab.window().raise_(), tab.window().activateWindow()))
        for w in (self.text, show, stop):
            h.addWidget(w)
        self.adjustSize()

    def say(self, text: str):
        text = f"#{getattr(self.tab, 'n', 1)} {text}"
        self.text.setText(self.text.fontMetrics().elidedText(text, Qt.ElideRight, 326))
        if not self.isVisible() and self.moved:          # you put it somewhere: it stays there
            self.show()
        elif not self.isVisible():
            from PySide6.QtCore import QRect
            from ui import placement
            area = QGuiApplication.primaryScreen().availableGeometry()
            stack = (getattr(self.tab, "n", 1) - 1) % 5               # several sessions: one strip above another
            x = area.right() - self.width() - 14
            y = area.bottom() - (self.height() + 8) * (stack + 1) - 6
            self.move(x, y)
            placement.wayland_place(self, QRect(x, y, self.width(), self.height()), self.PLACE_NAME)
            self.show()


    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()           # the compositor moves it (works on Wayland)
            self.moved = True


class ClaudeTab(QWidget):
    """One agent session. Several run side by side (SessionsPanel), each on its own backend and log."""
    changed = Signal()
    made = 0

    def __init__(self, backend: str = ""):
        super().__init__()
        ClaudeTab.made += 1
        self.n = ClaudeTab.made
        self.log_path = LOG if self.n == 1 else LOG.with_name(f"console-{self.n}.log")
        self.limits, self.limits_ts, self.ctx = {}, 0.0, 0
        self.chat_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{self.n}"
        self.proc = None
        self.session = ""
        self.attachments = []
        self.buf = b""
        self.plain = []                  # readable log lines, for Llama and Konsole
        self.tools = {}                  # tool_use id -> description
        self.konsole = None
        self.asker = None
        self.started = 0.0
        self.tokens = {"in": 0, "out": 0, "cache": 0}
        self.cost = 0.0
        self.stopped = False             # the user pressed Stop (so the exit isn't reported as an error)
        self.answer, self.turns = "", None
        self.retries, self.queue = 0, []
        self.last_request, self.cwd = "", ""
        self.note_paths = []             # Fix notes this chat is working on: marked done when you say "commit"
        self.note_queue = []             # notes still to do: one at a time, so none is forgotten
        self.rootsh, self.root_ok, self.root_buf, self.root_cmd = None, False, b"", ""
        self.job, self.run_t0 = None, 0.0
        self.widget = ActivityWidget(self)
        LOG.parent.mkdir(parents=True, exist_ok=True)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(8)
        head = QFrame()                          # status, settings and usage: one card above the chat
        head.setObjectName("Card")
        hv = QVBoxLayout(head)
        hv.setContentsMargins(14, 10, 14, 10)
        hv.setSpacing(6)
        v.addWidget(head)
        top = QHBoxLayout()
        self.status = QLabel("Checking Claude Code…")
        self.status.setTextFormat(Qt.RichText)
        self.login = QPushButton("Sign in to Claude Code")
        self.login.hide()
        self.login.clicked.connect(self._login)
        top.addWidget(self.status, 1)
        top.addWidget(self.login)
        hv.addLayout(top)

        bar = QHBoxLayout()
        self.model = QComboBox()
        for label, val in MODELS:
            self.model.addItem(label, val)
        self.backend = QComboBox()
        for label, val in BACKENDS:
            self.backend.addItem(label, val)
        self.backend.setToolTip("Local: the same Claude Code, tools, sub-agents and skills on your own GPU via Ollama")
        try:
            from core.config import config
            self.backend.setCurrentIndex(max(0, self.backend.findData(backend or config.get("evolve.backend", "claude"))))
        except Exception:
            pass
        self.backend.currentIndexChanged.connect(self._backend_changed)
        self._fill_models()
        self.folder = QComboBox()
        dev = Path.home() / "saint-dev"          # the git checkout deploy.sh copies live; agents can write here
        if (dev / ".git").is_dir():
            self.folder.addItem(f"SAINT dev checkout  ({dev})", str(dev))
        self.folder.addItem("HalOS source  (" + SAINT_SRC + ")", SAINT_SRC)
        self.folder.addItem("Home folder", str(Path.home()))
        self.folder.addItem("Choose folder…", "")
        self.folder.activated.connect(self._pick_folder)
        self.trust = QComboBox()
        for label, val in TRUST:
            self.trust.addItem(label, val)
        self.show_konsole = QCheckBox("Konsole")
        self.show_konsole.setChecked(False)
        self.show_konsole.setToolTip("Open a Konsole window that shows what Claude is doing, live")
        konsole_btn = QPushButton("Open Konsole")
        konsole_btn.clicked.connect(self._open_konsole)
        new_btn = QPushButton("New session")
        new_btn.clicked.connect(self.new_session)
        for lab, w in (("Run on", self.backend), ("Model", self.model), ("Folder", self.folder), ("Can", self.trust)):
            l = QLabel(lab.upper())
            l.setObjectName("Faint")
            l.setStyleSheet("font-size: 10px; font-weight: 600; letter-spacing: 0.6px")
            bar.addWidget(l)
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(self.show_konsole)
        bar.addWidget(konsole_btn)
        bar.addWidget(new_btn)
        hv.addLayout(bar)

        from PySide6.QtWidgets import QProgressBar
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)               # indeterminate: moves while an agent works
        self.busy.setMaximumHeight(6)
        self.busy.setTextVisible(False)
        self.busy.hide()
        v.addWidget(self.busy)
        self.triage = QCheckBox("Ask first")
        self.triage.setChecked(True)
        self.triage.setToolTip("Before starting, a small model gauges the size of the job and asks its questions (and "
                               "what must be installed or approved) once, so the agent can then work until it's done")
        bar.insertWidget(bar.count() - 3, self.triage)
        self.show_widget = QCheckBox("Widget")
        self.show_widget.setChecked(True)
        self.show_widget.setToolTip("While the agent works, a small always-on-top strip shows what it is doing")
        bar.insertWidget(bar.count() - 3, self.show_widget)
        self.phase, self.triaging = "", False
        self.tick = QTimer(self)
        self.tick.setInterval(1000)
        self.tick.timeout.connect(self._tick)
        self.usage = QLabel("")
        self.usage.setObjectName("Faint")
        self.usage.setWordWrap(True)
        hv.addWidget(self.usage)

        split = QSplitter(Qt.Vertical)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setObjectName("Transcript")
        self.view.document().setDocumentMargin(14)
        split.addWidget(self.view)
        low = QFrame()                           # the composer card
        low.setObjectName("Card")
        lv = QVBoxLayout(low)
        lv.setContentsMargins(12, 10, 12, 10)
        self.chips = QLabel("")
        self.chips.setStyleSheet("color: gray")
        self.chips.setWordWrap(True)
        lv.addWidget(self.chips)
        self.answers = QHBoxLayout()     # buttons for a question the agent asked, or a root command to approve
        lv.addLayout(self.answers)
        self.box = QPlainTextEdit()
        self.box.setFrameShape(QFrame.NoFrame)
        self.box.setPlaceholderText("Tell Evolve what to change or fix…  (Ctrl+Enter sends, also while it works · "
                                    "“commit”, “status”, “undo” and “deploy” run without a model)")
        self.count = QLabel("")
        self.count.setStyleSheet("color: gray")
        self.box.textChanged.connect(self._count)
        lv.addWidget(self.box, 1)
        row = QHBoxLayout()
        attach = QPushButton("Attach files…")
        attach.clicked.connect(self._attach)
        paste = QPushButton("Paste image")
        paste.clicked.connect(self._paste_image)
        clear = QPushButton("Clear attachments")
        clear.clicked.connect(self._clear_attach)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self.send)
        for b in (attach, paste, clear):
            row.addWidget(b)
        row.addWidget(self.count)
        row.addStretch(1)
        row.addWidget(self.stop_btn)
        row.addWidget(self.send_btn)
        lv.addLayout(row)
        ask = QHBoxLayout()
        self.ask_box = QLineEdit()
        self.ask_box.setPlaceholderText("Ask the local Llama what Claude is doing right now…")
        self.ask_box.returnPressed.connect(self._ask_llama)
        ask_btn = QPushButton("Ask Llama")
        ask_btn.clicked.connect(self._ask_llama)
        ask.addWidget(self.ask_box, 1)
        ask.addWidget(ask_btn)
        lv.addLayout(ask)
        split.addWidget(low)
        split.setSizes([520, 220])
        v.addWidget(split, 1)
        QShortcut(QKeySequence("Ctrl+Return"), self.box, activated=self.send)
        QShortcut(QKeySequence("Ctrl+Enter"), self.box, activated=self.send)
        self.box.installEventFilter(self)
        QTimer.singleShot(0, self.check)

    # ------------------------------------------------------------------ status / sign-in
    def local(self) -> bool:
        return self.backend.currentData() == "local"

    def _backend_changed(self, *_):
        try:
            from core.config import config
            config.set("evolve.backend", self.backend.currentData())
        except Exception:
            pass
        self.new_session()             # a Claude session can't be resumed on a local model, or the other way round
        self._fill_models()
        self.check()
        self.changed.emit()

    def _fill_models(self):
        """Claude's aliases, or the models downloaded in Ollama when running locally."""
        self.model.clear()
        if self.local():
            names = claude_agent.local_models()
            self.model.addItem(f"Default ({claude_agent.local_setting('main')})", "")
            for n in names:
                self.model.addItem(n, n)
            self.model.setToolTip("Main agent model; sub-agents marked haiku still use "
                                  + claude_agent.local_setting("fast"))
        else:
            for label, val in MODELS:
                self.model.addItem(label, val)
            self.model.setToolTip("")

    def check(self):
        if self.local():
            why = claude_agent.local_status()
            self.status.setText(f"<b>{_esc(why)}</b>" if why else
                                f"✅ Local models: {_esc(claude_agent.local_setting('main'))} (main), "
                                f"{_esc(claude_agent.local_setting('fast'))} (sub-agents). Free, nothing leaves this PC.")
            self.login.hide()
            self.send_btn.setEnabled(not why)
            return not why
        st = claude_agent.status()
        if not st.installed:
            self.status.setText("<b>Claude Code isn't installed.</b>")
            self.login.setText("Install Claude Code")
        elif not st.signed_in:
            self.status.setText("<b>Claude Code isn't signed in.</b> Sign in once with your Claude account "
                                "(Pro/Max); SAINT never uses an API key.")
            self.login.setText("Sign in to Claude Code")
        else:
            self.status.setText("✅ Claude Code is signed in (your Claude subscription).")
        self.login.setVisible(not (st.installed and st.signed_in))
        self.send_btn.setEnabled(st.installed and st.signed_in)
        return st.installed and st.signed_in

    def _login(self):
        self.login.setEnabled(False)
        self.status.setText("Finish signing in in the Konsole window, then close it.")
        p = QProcess(self)
        p.finished.connect(lambda *_: (self.login.setEnabled(True), self.check()))
        argv = claude_agent.login_command(claude_agent.status().installed)
        p.start(argv[0], argv[1:])

    # ------------------------------------------------------------------ attachments
    def eventFilter(self, obj, ev):
        if obj is self.box and ev.type() == ev.Type.KeyPress and ev.matches(QKeySequence.Paste):
            if QGuiApplication.clipboard().mimeData().hasImage():
                self._paste_image()
                return True
        return False

    def _attach(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Attach files for Claude", str(Path.home()))
        self.attachments += [f for f in files if f not in self.attachments]
        self._chips()

    def _paste_image(self):
        img = QGuiApplication.clipboard().image()
        if img.isNull():
            self.chips.setText("There's no image on the clipboard.")
            return
        p = os.path.join(tempfile.gettempdir(), f"evolve-paste-{int(time.time() * 1000)}.png")
        img.save(p, "PNG")
        self.attachments.append(p)
        self._chips()

    def _clear_attach(self):
        self.attachments = []
        self._chips()

    def _chips(self):
        self.chips.setText(("📎 " + "   📎 ".join(Path(a).name for a in self.attachments)) if self.attachments else "")

    def _pick_folder(self, i):
        if self.folder.itemData(i):
            return
        d = QFileDialog.getExistingDirectory(self, "Folder Claude works in", str(Path.home()))
        if d:
            self.folder.insertItem(0, d, d)
        self.folder.setCurrentIndex(0)

    # ------------------------------------------------------------------ transcript
    def _html(self, html: str):
        self.view.moveCursor(QTextCursor.End)
        self.view.insertHtml(html + "<br>")
        self.view.moveCursor(QTextCursor.End)

    def _log(self, line: str):
        self.plain.append(line)
        del self.plain[:-400]
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _open_konsole(self):
        if self.konsole is not None and self.konsole.state() != QProcess.NotRunning:
            return
        self.log_path.touch()
        self.konsole = QProcess(self)
        self.konsole.start("konsole", ["--hide-menubar", "-p", f"tabtitle=Evolve · session {self.n}", "-e", "bash",
                                       "-c", f"echo 'Live view of Evolve session {self.n} (close any time).'; "
                                       f"tail -n 80 -F '{self.log_path}'"])

    # ------------------------------------------------------------------ running Claude
    def new_session(self):
        if self.proc is not None:
            return
        self.save_chat()
        self.session = ""
        self.last_request = ""
        self.chat_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{self.n}"
        self.note_paths, self.note_queue = [], []
        self._root_close()
        self._clear_answers()
        self.view.clear()
        self.tokens = {"in": 0, "out": 0, "cache": 0}
        self.cost = 0.0
        self._html("<i>New session.</i>")
        self._log("─" * 30 + " new session " + "─" * 30)

    def who(self) -> str:
        """Who is answering, by name: the local model, or Claude."""
        if not self.local():
            return "Claude"
        return getattr(self, "cur_model", "") or self.model.currentData() or claude_agent.local_setting("main")

    def _working(self, phase: str):
        self.phase = phase
        self.busy.show()
        if not self.tick.isActive():
            self.started = time.monotonic()
            self.tick.start()
        self._tick()

    def _tick(self):
        secs = int(time.monotonic() - self.started)
        self.status.setText(f"⏳ {_esc(self.who())} · {secs}s · {_esc(self.phase)}")
        if self.show_widget.isChecked() and not self.window().isActiveWindow():
            self.widget.say(f"⏳ {secs}s · {self.phase}")
        else:
            self.widget.hide()
        if secs % 5 == 0:
            evolve_chat.set_status(running=True, phase=self.phase)
        self.changed.emit()

    def _idle(self):
        self.tick.stop()
        self.busy.hide()
        self.widget.hide()
        self.changed.emit()
        self.save_chat()

    def fix_notes(self, notes):
        """Work through ``notes`` one at a time: each gets its own run and checks before the next starts."""
        self.note_queue = list(notes)
        self.next_note(first=True)

    def next_note(self, first: bool = False):
        from core import fix_notes
        if not self.note_queue or self.working():
            return
        n = self.note_queue.pop(0)
        self.note_paths.append(str(n.path))
        self.attachments = [str(n.path.parent / n.screenshot)] if n.screenshot else []
        self.last_request = "Fix: " + n.text.splitlines()[0][:80]
        if self.note_queue or not first:
            self._html(f"<span style='color:gray'>Note {len(self.note_paths)} of "
                       f"{len(self.note_paths) + len(self.note_queue)}: {_esc(n.text.splitlines()[0][:100])}</span>")
        self.send(fix_notes.prompt([n]), ask=first)     # questions once, before the first; then it keeps going

    def save_chat(self):
        """This chat to CHATS/<id>.json: the transcript as shown, and the session to resume it."""
        if not self.last_request:
            return
        try:
            CHATS.mkdir(parents=True, exist_ok=True)
            (CHATS / f"{self.chat_id}.json").write_text(json.dumps({
                "title": self.last_request, "backend": self.backend.currentData(), "session": self.session,
                "cwd": self.cwd, "updated": time.time(), "notes": self.note_paths,
                "html": self.view.toHtml()}), encoding="utf-8")
        except OSError as e:
            self._log(f"chat not saved: {e}")

    def load_chat(self, path: Path, data: dict):
        """Show a saved chat here; the next message carries on in its session (same backend)."""
        self.chat_id, self.session = path.stem, data.get("session", "")
        self.last_request, self.cwd = data.get("title", ""), data.get("cwd", "")
        i = self.folder.findData(self.cwd)
        if i >= 0:
            self.folder.setCurrentIndex(i)
        self.view.setHtml(data.get("html", ""))
        self._html(f"<i>Reopened. {'Your next message carries on in the same session.' if self.session else ''}</i>")
        self.changed.emit()

    def working(self) -> bool:
        return self.proc is not None or self.triaging or (self.job is not None and self.job.isRunning())

    def elapsed(self) -> int:
        return int(time.monotonic() - self.started) if self.tick.isActive() else 0

    def shutdown(self):
        if self.proc is not None:
            self.stopped = True
            self.proc.terminate()
        self._root_close()
        self.widget.close()

    def _count(self):
        n = len(self.box.toPlainText())
        self.count.setText(f"{n:,} characters · about {max(1, n // 4):,} tokens" if n else "")

    def _you(self, text: str, how: str = ""):
        self._html(_bubble("You" + _esc(how), _esc(text).replace(chr(10), '<br>'), you=True))
        self._log(f"\n>>> YOU ({time.strftime('%H:%M:%S')}, in {self.cwd}){how}:\n{text}\n")

    def _clear_answers(self):
        while self.answers.count():
            w = self.answers.takeAt(0).widget()
            if w is not None:
                w.deleteLater()

    def _offer(self, options, fn):
        self._clear_answers()
        for label in options:
            b = QPushButton(label[:70])
            b.clicked.connect(lambda _=False, l=label: (self._clear_answers(), fn(l)))
            self.answers.addWidget(b)
        self.answers.addStretch(1)

    def send(self, text: str = None, ask: bool = None):
        """Send a request. While the agent works it is queued and becomes its next turn.
        ``ask``: gauge the job and ask questions first (None: the "Ask first" box decides)."""
        typed = not isinstance(text, str)
        text = (self.box.toPlainText() if typed else text).strip()
        if not text or self.triaging:
            return
        if self.attachments:
            text += "\n\nAttached files (read them; images are screenshots):\n" + "\n".join(f"- {a}" for a in self.attachments)
        if self.proc is not None:                        # working: it becomes the agent's next turn, right after this one
            self.queue.append(text)
            self._you(text, " (queued: the agent gets it as soon as this step is done)")
            if typed:
                self.box.clear()
            return
        if (self.job is not None and self.job.isRunning()) or not self.check():
            return
        self.cwd = cwd = self.folder.currentData() or self.folder.itemData(0)
        self._clear_answers()
        self._you(text)
        if typed:
            self.box.clear()
        done = evolve_chat.quick(text, cwd, self.last_request)      # commit / status / undo / deploy: no model
        if done is not None:
            self._html(f"<p><b>{'✅' if done.ok else '❌'} {_esc(done.title)}</b> <span style='color:gray'>(no model "
                       f"used)</span><br><span style='font-family:monospace'>{_esc(done.text).replace(chr(10), '<br>')}</span></p>")
            self._log(f"{done.title}: {done.text}")
            if done.ok and done.title == "Committed":
                self._close_notes()
            self.save_chat()
            return
        self.dirs = sorted({str(Path(a).parent) for a in self.attachments} - {cwd})
        if typed or not self.last_request:
            self.last_request = text.splitlines()[0][:200]
        self.retries, self.run_t0 = 0, time.monotonic()
        if self.show_konsole.isChecked():
            self._open_konsole()
        self.attachments = []
        self._chips()
        self.cur_model = ""
        self.stop_btn.setEnabled(True)
        if not (self.triage.isChecked() if ask is None else ask):
            return self._start(text)
        self.triaging = True
        self._working("gauging the job and collecting questions…")
        # Local: the main model (already on the GPU; a second model would push it out). Claude: Haiku.
        model = self.model.currentData() or claude_agent.local_setting("main")
        self.asker = _Ask(text, PREFLIGHT, model, {"format": "json", "options": {"num_predict": 700}}, haiku=not self.local())

        def briefed(raw: str):
            self.triaging = False
            if not self.stop_btn.isEnabled():            # stopped while it was thinking
                return
            brief, full = evolve_chat.parse_preflight(raw), text
            if brief:
                self._html(f"<span style='color:#c9a'>🧭 {_esc(brief['scope'] or 'job')}: {_esc(brief['summary'])}</span>")
                self._log(f"BRIEF: {brief}")
                if brief["questions"] or brief["needs"]:
                    dlg = PreflightDialog(brief, self)
                    if not dlg.exec():
                        self._idle()
                        self.stop_btn.setEnabled(False)
                        self.status.setText("Cancelled.")
                        return self.box.setPlainText(text)
                    full += dlg.answers_text()
                    self._log(dlg.answers_text())
            self._start(full)
        self.asker.done.connect(briefed)
        self.asker.start()

    def _start(self, text: str):
        """Launch the agent on ``text`` in self.cwd (a follow-up resumes the session, so nothing is sent twice)."""
        local, cwd = self.local(), self.cwd
        argv = evolve_chat.argv(local, self.trust.currentData(), cwd, "" if local else CONTEXT,
                                self.model.currentData() or "", self.session,
                                (*claude_agent_vault()[1:], *getattr(self, "dirs", [])))
        if not self.session:                             # where to look and what earlier runs learned: once
            ctx = evolve_chat.context_for(text, cwd)
            text += ("\n\n" + ctx) if ctx else ""
        self.stop_btn.setEnabled(True)
        self._launch(argv, cwd, text)

    def _launch(self, argv, cwd, text):
        p = QProcess(self)
        env = QProcessEnvironment()
        for k, val in (claude_agent.local_env() if self.local() else claude_agent.subscription_env()).items():
            env.insert(k, val)
        p.setProcessEnvironment(env)
        p.setWorkingDirectory(cwd)
        p.setProcessChannelMode(QProcess.SeparateChannels)
        p.readyReadStandardOutput.connect(self._read)
        p.finished.connect(self._finished)
        p.errorOccurred.connect(lambda e: self._html(f"<span style='color:#e66'>Claude Code couldn't start ({e}).</span>"))
        self.proc, self.buf = p, b""
        self.stopped, self.answer, self.turns, self.queue = False, "", None, []
        self.last_call, self.same = None, 0
        evolve_chat.set_status(running=True, request=self.last_request, started=time.time(), phase="starting",
                               result="", to_test=[])
        self._working("loading the model…" if self.local() else "starting…")
        p.start(claude_agent.claude_path() or "claude", argv)
        p.write(evolve_chat.user_line(text))             # stdin stays open: more messages can follow while it works

    def _turn_done(self):
        """The agent finished a turn: hand it the messages typed meanwhile (one more turn, same process), or close
        stdin so Claude Code exits."""
        if self.proc is None:
            return
        if self.queue:
            text, self.queue = "\n\n".join(self.queue), []
            self._working("reading your message…")
            self.proc.write(evolve_chat.user_line(text))
        else:
            self.proc.closeWriteChannel()

    def stop(self):
        if self.triaging:
            self.triaging = False
            self.stop_btn.setEnabled(False)
            self._idle()
            self.status.setText("Stopped.")
            return
        if self.proc is not None:
            self.stopped = True
            self.proc.terminate()
            QTimer.singleShot(3000, lambda: self.proc and self.proc.kill())
            self._html("<i>Stopping…</i>")

    def _read(self):
        self.buf += bytes(self.proc.readAllStandardOutput())
        *lines, self.buf = self.buf.split(b"\n")
        for raw in lines:
            try:
                self._event(json.loads(raw.decode("utf-8", "replace")))
            except ValueError:
                if raw.strip():
                    self._log(raw.decode("utf-8", "replace"))

    def _event(self, ev: dict):
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            self.session = ev.get("session_id", self.session)
            self.cur_model = ev.get("model", "")
            self._log(f"[session {self.session[:8]} · {ev.get('model', '')}]")
            self._working("thinking…")
            self._show_usage()
        elif kind == "system" and ev.get("subtype") == "post_turn_summary" and ev.get("status_detail"):
            self._working(ev["status_detail"])
        elif kind == "assistant":
            msg = ev.get("message") or {}
            self.cur_model = msg.get("model", getattr(self, "cur_model", ""))
            u = msg.get("usage") or {}
            self.ctx = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                        + u.get("cache_creation_input_tokens", 0))
            for b in msg.get("content") or []:
                if b.get("type") == "text" and b.get("text", "").strip():
                    self._html(_bubble(_esc(self.who()), _esc(b["text"]).replace("\n", "<br>")))
                    self._log(f"{self.who()}: " + b["text"])
                    self._working("writing…")
                elif b.get("type") == "thinking" and b.get("thinking", "").strip():
                    self._log("(thinking) " + b["thinking"][:400])
                elif b.get("type") == "tool_use":
                    name, args = b.get("name", ""), b.get("input") or {}
                    if name == "TodoWrite":
                        todos = args.get("todos") or []
                        mark = {"completed": "☑", "in_progress": "▶", "pending": "☐"}
                        lines = [f"{mark.get(t.get('status'), '☐')} {t.get('content', '')}" for t in todos]
                        self._html("<span style='color:gray'>" + "<br>".join(map(_esc, lines)) + "</span>")
                        self._log("TODO:\n  " + "\n  ".join(lines))
                        continue
                    what = claude_agent.describe_tool(name, args)
                    self.tools[b.get("id", "")] = what
                    call = (name, json.dumps(args, sort_keys=True))
                    self.same = self.same + 1 if call == self.last_call else 0
                    self.last_call = call
                    if self.same >= 6 and not self.stopped:      # a small model re-doing the same step forever
                        self._html("<span style='color:#e66'>The model repeated the same step 7 times, so Evolve "
                                   "stopped it. Try rewording, or pick another model.</span>")
                        self.stop()
                    self._html(f"<span style='color:#7aa7ff'>🔧 {_esc(what)}</span>")
                    detail = args.get("command") or args.get("file_path") or args.get("pattern") or ""
                    self._log(f"🔧 {what}" + (f"   [{str(detail)[:200]}]" if detail and str(detail) not in what else ""))
                    self._working(what)
            self._show_usage()
        elif kind == "user":
            for b in (ev.get("message") or {}).get("content") or []:
                if b.get("type") == "tool_result" and b.get("is_error"):
                    c = b.get("content")
                    c = c if isinstance(c, str) else json.dumps(c)
                    what = self.tools.get(b.get("tool_use_id"), "A step")
                    self._html(f"<span style='color:#e66'>✗ {_esc(what)}: {_esc(c[:200])}</span>")
                    self._log(f"   ✗ {c[:300]}")
        elif kind == "rate_limit_event":
            self.limits, self.limits_ts = ev.get("rate_limit_info") or {}, time.time()
            UsageRing.save(self.limits)
            self._show_usage()
        elif kind == "result" or "total_cost_usd" in ev:
            u = ev.get("usage") or {}
            self.tokens["in"] += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            self.tokens["cache"] += u.get("cache_read_input_tokens", 0)
            self.tokens["out"] += u.get("output_tokens", 0)
            self.cost += float(ev.get("total_cost_usd") or 0)
            secs = (ev.get("duration_ms") or 0) / 1000 or (time.monotonic() - self.started)
            if ev.get("is_error") or ev.get("subtype", "success") != "success":
                err = str(ev.get("result") or ev.get("subtype", "error"))
                why = err[-300:] if self.local() else (claude_agent._explain(err, 1) if err else err)
                self._html(f"<span style='color:#e66'>{_esc(self.who())} stopped: {_esc(why)}</span>")
            self._html(f"<span style='color:gray'>— done in {secs:.0f}s · {ev.get('num_turns', '?')} turns</span>")
            self.answer, self.turns = str(ev.get("result") or ""), ev.get("num_turns")
            self._turn_done()
            self._log(f"── done in {secs:.0f}s ──")
            self._show_usage()

    def _show_usage(self):
        bits = []
        if getattr(self, "cur_model", ""):
            bits.append(f"Model <b>{_esc(self.cur_model)}</b>")
        if getattr(self, "ctx", 0):
            bits.append(f"context {self.ctx / 1000:.0f}k tokens")
        if any(self.tokens.values()):
            bits.append(f"session {self.tokens['in'] / 1000:.0f}k in · {self.tokens['out'] / 1000:.1f}k out · "
                        f"{self.tokens['cache'] / 1000:.0f}k cached")
        if self.cost:
            bits.append(f"≈ ${self.cost:.2f} if billed as API (included in your plan)")
        lim = getattr(self, "limits", {}) or {}
        w = lim.get("unifiedWindows") or {}
        if w.get("five_hour"):
            bits.append(f"5-hour usage <b>{_pct(w['five_hour'].get('utilization'))}</b> (resets in {_when(w['five_hour'].get('resetsAt'))})")
        if w.get("seven_day"):
            bits.append(f"weekly <b>{_pct(w['seven_day'].get('utilization'))}</b> (resets in {_when(w['seven_day'].get('resetsAt'))})")
        if lim.get("status") == "rejected":
            bits.append("<span style='color:#e66'>usage limit reached</span>")
        self.usage.setText("  ·  ".join(bits))
        self.changed.emit()

    def _finished(self, code, _status):
        err = bytes(self.proc.readAllStandardError()).decode("utf-8", "replace") if self.proc else ""
        if self.buf.strip():
            self.buf += b"\n"
            self._read()
        self._idle()
        self.proc = None
        self.stop_btn.setEnabled(False)
        if self.stopped:
            self.stopped = False
            self._html("<i>Stopped.</i>")
            self._log("STOPPED by the user")
            evolve_chat.set_status(running=False, result="stopped")
            self.check()
            return
        # Not errors: Claude Code's notes about the model name and about connectors being off with a local endpoint.
        lines = [l for l in err.strip().splitlines() if "unrecognized_model" not in l and "connectors are disabled" not in l]
        if code not in (0, None) and lines:
            msg = (f"{self.who()} stopped (exit {code}): " + " | ".join(lines[-3:])[:400]) if self.local() \
                else claude_agent._explain("\n".join(lines), code)
            self._html(f"<span style='color:#e66'>{_esc(msg)}</span>")
            self._log("ERROR: " + msg)
        cwd = self.cwd
        self._working("checking the change (compiling, running its tests)…")

        def checks():
            ok, text = evolve_chat.verify(cwd)
            return ok, text, evolve_chat.changed(Path(cwd)) if (Path(cwd) / ".git").exists() else []
        self.job = _Job(checks)
        self.job.done.connect(self._checked)
        self.job.start()

    def _checked(self, res):
        """After the agent stopped: SAINT's own checks (no model). A failure goes back to the agent once; then the
        run is logged in the vault and any question or root command the agent ended with is offered."""
        ok, checks, files = res
        secs = time.monotonic() - self.run_t0
        self._idle()
        if not ok and self.retries < MAX_FIX_RETRIES and self.session:
            self.retries += 1
            self._html(f"<span style='color:#e66'>✗ SAINT's checks failed; sent back to fix:</span><br>"
                       f"<span style='font-family:monospace'>{_esc(checks[-600:]).replace(chr(10), '<br>')}</span>")
            self._log("CHECKS FAILED: " + checks)
            return self._start("SAINT's checks failed after your change. Fix exactly this and nothing else:\n\n" + checks)
        reply = evolve_chat.parse_reply(self.answer)
        if files:
            self._html(f"<span style='color:{'#4c4' if ok else '#e66'}'>{'✓' if ok else '✗'} Checks: {_esc(checks[:400])}</span>")
            try:
                note = evolve_chat.log_run(self.last_request, self.cwd, ok, checks, secs, self.who(), self.answer,
                                           tuple(Path(n).stem for n in self.note_paths), self.turns)
                self._html(f"<span style='color:gray'>📓 Logged in the vault: Evolve/Runs/{_esc(note.name)} · say "
                           "<b>commit</b> to keep it, <b>undo</b> to set it aside</span>")
            except OSError as e:
                self._log(f"run log failed: {e}")
        evolve_chat.set_status(running=False, result=("checks passed" if ok else "checks FAILED") if files else "answered",
                               to_test=reply.tests)
        if not self.window().isActiveWindow():
            QProcess.startDetached("notify-send", ["--app-name=Evolve", "--icon=saint", "Evolve is done",
                                                   (self.last_request[:80] + ": " + ("checks passed" if ok else "checks failed"))])
        self.check()
        self.status.setText(self.status.text() + "  ·  Ready for a follow-up (same session).")
        if reply.root:
            self._ask_root(reply.root)
        elif reply.question:
            self._html(f"<span style='color:#c9a'>❓ {_esc(reply.question)}</span>")
            self._offer(reply.options or ["Yes", "No"], lambda a: self.send(a, ask=False))
        elif self.note_queue:                            # this note is done and checked: the next one
            QTimer.singleShot(800, self.next_note)

    def _close_notes(self):
        """The change was committed: the Fix notes it came from are done."""
        from core import fix_notes
        for n in fix_notes.notes(None):
            if str(n.path) in self.note_paths and n.status == "open":
                fix_notes.mark(n, "done")
        if self.note_paths:
            self._html(f"<span style='color:gray'>Marked {len(self.note_paths)} note(s) fixed.</span>")
        self.note_paths = []

    # ------------------------------------------------------------------ root, with your OK
    def _ask_root(self, cmd: str):
        why = evolve_chat.root_refused(cmd)
        self._html(f"<span style='color:#fc6'>🔑 Wants to run as root:</span> <span style='font-family:monospace'>{_esc(cmd)}</span>")
        if why:
            return self._html(f"<span style='color:#e66'>Refused: {_esc(why)}.</span>")
        if self.root_ok:
            return self._run_root(cmd, True)
        self._offer(["Run as root once", "Allow root for this chat", "Don't run it"],
                    lambda a: self.send(f"The user did not allow `{cmd}`. Continue without it.", ask=False)
                    if a.startswith("Don't") else self._run_root(cmd, a.startswith("Allow")))

    def _run_root(self, cmd: str, keep: bool):
        """Runs in a root shell started with pkexec: the system's password prompt, so the password never reaches
        Evolve or the model. ``keep``: the shell stays for this chat (New session or closing Evolve ends it)."""
        if self.rootsh is None:
            sh = QProcess(self)
            sh.setProcessChannelMode(QProcess.MergedChannels)
            sh.readyReadStandardOutput.connect(self._root_read)
            sh.finished.connect(lambda code, _s: self._root_done(code, closed=True))
            sh.start("pkexec", ["bash"])
            self.rootsh = sh
        self.root_ok, self.root_buf, self.root_cmd = keep, b"", cmd
        self._working(f"root: {cmd[:60]}")
        self._log(f"ROOT ({'chat' if keep else 'once'}): {cmd}")
        self.rootsh.write((cmd + "\necho __EVOLVE_ROOT_DONE__$?\n").encode())

    def _root_read(self):
        self.root_buf += bytes(self.rootsh.readAllStandardOutput())
        head, mark, tail = self.root_buf.rpartition(b"__EVOLVE_ROOT_DONE__")
        if mark and tail.strip().isdigit():
            self.root_buf = head
            self._root_done(int(tail.strip()))

    def _root_done(self, code: int, closed: bool = False):
        cmd, out, self.root_cmd = self.root_cmd, self.root_buf.decode("utf-8", "replace").strip(), ""
        if closed:
            self.rootsh, self.root_ok = None, False
        elif not self.root_ok:
            self._root_close()
        if not cmd:
            return
        self._idle()
        said = "wasn't approved (the password prompt was dismissed)" if closed and code in (126, 127) else f"exit {code}"
        self.send(f"`{cmd}` as root: {said}.\n{out[-3000:]}", ask=False)

    def _root_close(self):
        sh, self.rootsh, self.root_ok = self.rootsh, None, False
        if sh is not None:
            sh.blockSignals(True)
            sh.closeWriteChannel()
            sh.terminate()

    # ------------------------------------------------------------------ ask Llama
    def _ask_llama(self):
        q = self.ask_box.text().strip() or "What is Claude doing right now?"
        if self.asker is not None and self.asker.isRunning():
            return
        log = "\n".join(self.plain[-80:]) or "(Claude hasn't done anything yet.)"
        running = "Claude is still working." if self.proc is not None else "Claude has finished."
        self._html(f"<span style='color:#c9a'>🦙 You asked: {_esc(q)}</span>")
        self.ask_box.clear()
        self.asker = _Ask(f"{running}\n\nLog (newest last):\n{log[-6000:]}\n\nQuestion: {q}")
        self.asker.done.connect(lambda a: self._html(f"<span style='color:#c9a'>🦙 {_esc(a)}</span>"))
        self.asker.start()


def claude_agent_vault():
    try:
        from core import vault
        return vault.claude_args()
    except Exception:
        return []


class UsageRing(QWidget):
    """Your Claude subscription usage as a ring that fills and turns amber, then red; click it for every limit
    (5-hour, weekly, per model) and when each resets. Claude Code reports these during each run; the last report is
    kept in usage.json so the ring shows something before the first run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.setCursor(Qt.PointingHandCursor)
        self.limits, self.ts = {}, 0.0
        try:
            d = json.loads(USAGE.read_text(encoding="utf-8"))
            self.limits, self.ts = d.get("limits") or {}, float(d.get("ts") or 0)
        except (OSError, ValueError):
            pass
        self._tip()

    @staticmethod
    def save(limits: dict):
        try:
            USAGE.write_text(json.dumps({"ts": time.time(), "limits": limits}), encoding="utf-8")
        except OSError:
            pass

    def set_limits(self, limits: dict, ts: float):
        if limits and ts > self.ts:
            self.limits, self.ts = limits, ts
            self._tip()
            self.update()

    def windows(self):
        out = []
        for k, w in (self.limits.get("unifiedWindows") or {}).items():
            try:
                out.append((k, float(w.get("utilization")), w.get("resetsAt")))
            except (TypeError, ValueError, AttributeError):
                pass
        return sorted(out, key=lambda x: (x[0] != "five_hour", x[0] != "seven_day", x[0]))

    def worst(self):
        ws = self.windows()
        return max(u for _, u, _ in ws) if ws else None

    def _tip(self):
        u = self.worst()
        self.setToolTip("Claude usage: no report yet (run a Claude session)" if u is None else
                        f"Claude usage: highest limit at {u * 100:.0f}% — click for details")

    def paintEvent(self, _e):
        p, pal = QPainter(self), _pal()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(5, 5, self.width() - 10, self.height() - 10)
        pen = QPen(QColor(pal.border_strong), 5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawEllipse(r)
        u = self.worst()
        if u is not None:
            pen.setColor(QColor(_usage_color(u)))
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(360 * 16 * max(0.01, min(u, 1.0))))
        f = p.font()
        f.setPointSizeF(max(6.5, f.pointSizeF() - 3))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(pal.text if u is not None else pal.faint))
        p.drawText(self.rect(), Qt.AlignCenter, f"{u * 100:.0f}%" if u is not None else "–")

    def mousePressEvent(self, _e):
        pal = _pal()
        rows = "".join(
            f"<tr><td style='padding:3px 10px 3px 0'>{_esc(_window_name(k))}</td>"
            f"<td style='padding:3px 10px 3px 0;color:{_usage_color(u)};font-weight:600' align='right'>{u * 100:.0f}%</td>"
            f"<td style='color:{pal.muted}'>resets in {_esc(_when(at)) or '?'}</td></tr>" for k, u, at in self.windows())
        status = self.limits.get("status")
        age = f"{int((time.time() - self.ts) // 60)} min ago" if self.ts else "never"
        html = (f"<b>Claude subscription usage</b><br><table>{rows or '<tr><td>No report yet.</td></tr>'}</table>"
                + (f"<p style='color:{pal.danger}'>Usage limit reached.</p>" if status == "rejected" else "")
                + f"<p style='color:{pal.faint};font-size:small'>Reported by Claude Code {age}; updates live while a "
                  "Claude session works.</p>")
        pop = QLabel(html, self, Qt.Popup)
        pop.setTextFormat(Qt.RichText)
        pop.setStyleSheet(f"background:{pal.surface};border:1px solid {pal.border_strong};border-radius:10px;"
                          "padding:12px")
        pop.adjustSize()
        g = self.mapToGlobal(self.rect().bottomRight())
        pop.move(g.x() - pop.width(), g.y() + 6)
        pop.show()


class SessionCard(QFrame):
    """One session in the header: who runs it, what it's doing right now, and what it has cost so far."""

    def __init__(self, tab: "ClaudeTab", panel: "SessionsPanel"):
        super().__init__()
        self.tab, self.panel = tab, panel
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(190)
        self.setMaximumWidth(280)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        self.title = QLabel()
        self.title.setTextFormat(Qt.RichText)
        self.what = QLabel()
        self.what.setObjectName("Muted")
        self.stats = QLabel()
        self.stats.setObjectName("Faint")
        for w in (self.title, self.what, self.stats):
            v.addWidget(w)

    def mousePressEvent(self, _e):
        self.panel.focus(self.tab)

    def refresh(self, current: bool):
        t, pal = self.tab, _pal()
        working = t.working()
        dot = pal.accent if working else (pal.success if t.session else pal.faint)
        kind = "Local" if t.local() else "Claude"
        self.title.setText(f"<span style='color:{dot}'>●</span> <b>{kind} {t.n}</b> "
                           f"<span style='color:{pal.faint}'>· {_esc(t.who() if t.local() else (t.model.currentText()))}</span>")
        what = (f"{t.elapsed()}s · {t.phase}" if working else
                (t.last_request or "Ready") if t.session or t.last_request else "Ready for a request")
        self.what.setText(self.what.fontMetrics().elidedText(what, Qt.ElideRight, 250))
        bits = []
        if t.ctx:
            bits.append(f"{t.ctx / 1000:.0f}k context")
        if any(t.tokens.values()):
            bits.append(f"{(t.tokens['in'] + t.tokens['out']) / 1000:.0f}k tokens")
        if t.cost and not t.local():
            bits.append(f"≈${t.cost:.2f}")
        if t.note_paths:
            bits.append(f"{len(t.note_paths)} note(s)")
        self.stats.setText(" · ".join(bits) or ("free, on this PC" if t.local() else "your subscription"))
        self.setStyleSheet(f"QFrame#Card {{ border: 1px solid {pal.accent if current else pal.border}; }}")


class HistoryDialog(QDialog):
    """Earlier chats, newest first: search them, read one, or open it to carry on."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Evolve chats")
        self.resize(900, 600)
        self.picked = None
        v = QVBoxLayout(self)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Search your chats…")
        v.addWidget(self.find)
        split = QSplitter()
        self.list = QListWidget()
        self.view = QTextBrowser()
        self.view.setObjectName("Transcript")
        split.addWidget(self.list)
        split.addWidget(self.view)
        split.setSizes([320, 580])
        v.addWidget(split, 1)
        row = QHBoxLayout()
        self.info = QLabel()
        self.info.setObjectName("Faint")
        row.addWidget(self.info, 1)
        delete = QPushButton("Delete")
        delete.setObjectName("Danger")
        delete.clicked.connect(self._delete)
        open_ = QPushButton("Open and carry on")
        open_.setObjectName("Primary")
        open_.clicked.connect(self._open)
        row.addWidget(delete)
        row.addWidget(open_)
        v.addLayout(row)
        self.chats = []
        for p in sorted(CHATS.glob("*.json"), reverse=True) if CHATS.is_dir() else []:
            try:
                self.chats.append((p, json.loads(p.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                pass
        self.chats.sort(key=lambda c: -float(c[1].get("updated") or 0))
        self.find.textChanged.connect(self._fill)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemDoubleClicked.connect(lambda _it: self._open())
        self._fill()

    def _shown(self):
        q = self.find.text().lower().strip()
        return [c for c in self.chats if not q or q in (c[1].get("title", "") + " " + c[1].get("html", "")).lower()]

    def _fill(self):
        self.list.clear()
        for _p, d in self._shown():
            when = time.strftime("%b %d %H:%M", time.localtime(float(d.get("updated") or 0)))
            kind = "Local" if d.get("backend") == "local" else "Claude"
            self.list.addItem(f"{d.get('title', '(untitled)')[:70]}\n{kind} · {when}")
        self.info.setText(f"{len(self.chats)} saved chat{'s' if len(self.chats) != 1 else ''}")
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.view.setHtml("<i>No chats yet.</i>" if not self.chats else "<i>Nothing matches.</i>")

    def _show(self, i):
        shown = self._shown()
        if 0 <= i < len(shown):
            self.view.setHtml(shown[i][1].get("html", ""))

    def _open(self):
        shown, i = self._shown(), self.list.currentRow()
        if 0 <= i < len(shown):
            self.picked = shown[i]
            self.accept()

    def _delete(self):
        shown, i = self._shown(), self.list.currentRow()
        if 0 <= i < len(shown):
            shown[i][0].unlink(missing_ok=True)
            self.chats.remove(shown[i])
            self._fill()


class SessionsPanel(QWidget):
    """Agent sessions side by side, as tabs: + Claude / + Local start another, each runs on its own."""
    changed = Signal()
    wants_focus = Signal()

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_session)
        self.tabs.currentChanged.connect(lambda _i: self.changed.emit())
        corner = QWidget()
        h = QHBoxLayout(corner)
        h.setContentsMargins(0, 0, 4, 0)
        for label, be, tip in (("+ Claude", "claude", "A new session on your Claude subscription"),
                               ("+ Local", "local", "A new session on the local models (free, offline)")):
            b = QPushButton(label)
            b.setToolTip(tip + " — runs at the same time as the others")
            b.clicked.connect(lambda _=False, be=be: self.add(be))
            h.addWidget(b)
        hist = QPushButton("History")
        hist.setToolTip("Every earlier chat: search, read, or open one and carry on")
        hist.clicked.connect(self.history)
        h.insertWidget(0, hist)
        self.tabs.setCornerWidget(corner, Qt.TopRightCorner)
        v.addWidget(self.tabs)
        self.add("")

    def sessions(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def history(self):
        dlg = HistoryDialog(self)
        if not dlg.exec() or dlg.picked is None:
            return
        path, data = dlg.picked
        for t in self.sessions():                       # already open: just show it
            if t.chat_id == path.stem:
                return self.focus(t)
        backend = "local" if data.get("backend") == "local" else "claude"
        t = self.current()
        if t is None or t.working() or t.last_request or t.local() != (backend == "local"):
            t = self.add(backend)
        t.load_chat(path, data)
        self.focus(t)

    def current(self) -> "ClaudeTab":
        return self.tabs.currentWidget()

    def add(self, backend: str = "") -> "ClaudeTab":
        t = ClaudeTab(backend)
        t.changed.connect(lambda t=t: self._retitle(t))
        t.changed.connect(self.changed)
        self.tabs.addTab(t, "")
        self._retitle(t)
        self.tabs.setCurrentWidget(t)
        self.changed.emit()
        return t

    def _retitle(self, t):
        i = self.tabs.indexOf(t)
        if i >= 0:
            self.tabs.setTabText(i, ("● " if t.working() else "") + f"{'Local' if t.local() else 'Claude'} {t.n}")

    def focus(self, t):
        self.tabs.setCurrentWidget(t)
        self.wants_focus.emit()

    def idle(self, backend: str = "claude") -> "ClaudeTab":
        """A session on ``backend`` that isn't working (the one in front first), or a new one."""
        for t in [self.current()] + self.sessions():
            if t is not None and not t.working() and t.local() == (backend == "local"):
                return t
        return self.add(backend)

    def close_session(self, i: int):
        t = self.tabs.widget(i)
        if t.working() and QMessageBox.question(self, "Close session", f"Session {t.n} is still working. Stop it "
                                                "and close?") != QMessageBox.Yes:
            return
        t.shutdown()
        self.tabs.removeTab(i)
        t.deleteLater()
        if not self.tabs.count():
            self.add("")
        self.changed.emit()

    def shutdown(self):
        for t in self.sessions():
            t.save_chat()
            t.shutdown()


class Header(QFrame):
    """Top of Evolve: the title and a one-line summary, a live card per session, and the usage ring."""

    def __init__(self, panel: SessionsPanel):
        super().__init__()
        self.panel, self.cards = panel, {}
        self.setObjectName("EvolveHeader")
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(0)
        title = QLabel("Evolve")
        title.setStyleSheet("font-size: 20px; font-weight: 700; letter-spacing: 0.3px")
        self.summary = QLabel()
        self.summary.setObjectName("Muted")
        left.addWidget(title)
        left.addWidget(self.summary)
        h.addLayout(left)
        strip = QWidget()
        self.row = QHBoxLayout(strip)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(8)
        self.row.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(strip)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(84)
        scroll.setStyleSheet("background: transparent")
        h.addWidget(scroll, 1)
        self.ring = UsageRing()
        h.addWidget(self.ring)
        self.open_notes, self.notes_at = 0, 0.0
        panel.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        sessions = self.panel.sessions()
        alive = {id(t) for t in sessions}
        for k in [k for k in self.cards if k not in alive]:
            self.cards.pop(k).deleteLater()
        for t in sessions:
            if id(t) not in self.cards:
                self.cards[id(t)] = SessionCard(t, self.panel)
                self.row.insertWidget(self.row.count() - 1, self.cards[id(t)])
            self.cards[id(t)].refresh(t is self.panel.current())
            self.ring.set_limits(t.limits, t.limits_ts)
        if time.monotonic() - self.notes_at > 30:          # the notes are files: read them now and then, not per tick
            self.notes_at = time.monotonic()
            try:
                from core import fix_notes
                self.open_notes = len(fix_notes.open_notes())
            except Exception:
                pass
        working = sum(t.working() for t in sessions)
        fixing = sum(len(t.note_paths) for t in sessions if t.working())
        bits = [f"{len(sessions)} session{'s' if len(sessions) != 1 else ''}",
                f"{working} working" if working else "all idle", f"{self.open_notes} open notes"]
        if fixing:
            bits.append(f"{fixing} being fixed")
        self.summary.setText("  ·  ".join(bits))


class NotesTab(QWidget):
    """Fix notes by section (each section folds, and its tick box ticks all of its notes). What you ticked and what
    you folded survive Refresh, searching and "Show fixed and dropped"."""

    def __init__(self, sessions: SessionsPanel, tabs: QTabWidget):
        super().__init__()
        self.sessions, self.tabs = sessions, tabs
        self.ticked, self.folded = set(), set()          # note paths; section names
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Things you noted with right-click › <b>Note to fix</b> (or Meta+N anywhere: drag over what's wrong). "
                           "Tick notes (or a whole section), then pick what to do with them below."))
        self.show_done = QCheckBox("Show fixed and dropped")
        self.show_done.toggled.connect(self.refresh)
        top = QHBoxLayout()
        self.find = QLineEdit()
        self.find.setPlaceholderText("Search your notes…")
        self.find.textChanged.connect(self.refresh)
        top.addWidget(self.find, 1)
        for label, on in (("Select all", True), ("Deselect all", False)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, on=on: self._tick_all(on))
            top.addWidget(b)
        top.addWidget(self.show_done)
        v.addLayout(top)
        self.list = QTreeWidget()
        self.list.setHeaderHidden(True)
        self.list.currentItemChanged.connect(self._preview)
        self.list.itemChanged.connect(self._ticked)
        self.list.itemCollapsed.connect(lambda it: self.folded.add(it.data(0, Qt.UserRole + 1)))
        self.list.itemExpanded.connect(lambda it: self.folded.discard(it.data(0, Qt.UserRole + 1)))
        v.addWidget(self.list, 2)
        self.detail = QTextBrowser()
        v.addWidget(self.detail, 1)
        row = QHBoxLayout()
        self.count = QLabel("")
        self.count.setStyleSheet("color: gray")
        row.addWidget(self.count)
        for label, fn in (("Refresh", self.refresh), ("New note…", self._new), ("Mark fixed", lambda: self._mark("done")),
                          ("Drop", lambda: self._mark("dropped")), ("Reopen", lambda: self._mark("open")),
                          ("Open in Obsidian", self._obsidian)):
            b = QPushButton(label)
            if label in ("Mark fixed", "Drop", "Reopen"):
                b.setToolTip("The ticked notes, or the highlighted one when nothing is ticked")
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        idle = QCheckBox("Work on one when idle")
        idle.setToolTip("While the PC is idle, the local models try one small open note in its own worktree. You get a "
                        "notification and decide in Local runs: Keep or Drop. Nothing is applied without you.")
        try:
            from core.config import config
            idle.setChecked(bool(config.get("evolve.idle_work", True)))
            idle.toggled.connect(lambda on: config.set("evolve.idle_work", bool(on)))
        except Exception:
            idle.setEnabled(False)
        row.addWidget(idle)
        v.addLayout(row)
        row = QHBoxLayout()
        row.addStretch(1)
        chat = QPushButton("Send ticked to chat")
        chat.setToolTip("Puts the ticked notes (and their screenshots) in the chat box so you can add to them before sending")
        chat.clicked.connect(self._to_chat)
        row.addWidget(chat)
        check = QPushButton("Check if already fixed")
        check.setToolTip("The agent reads the code for each ticked note, changes nothing, and marks the ones that are "
                         "already implemented as fixed")
        check.clicked.connect(self._check_done)
        row.addWidget(check)
        local = QPushButton("Fix ticked locally")
        local.setToolTip("Each ticked note goes to the local models in its own worktree; watch it in Local runs")
        local.clicked.connect(self._fix_local)
        row.addWidget(local)
        fix = QPushButton("Fix ticked with Claude")
        fix.setObjectName("Primary")
        fix.clicked.connect(self._fix)
        row.addWidget(fix)
        v.addLayout(row)
        self.refresh()

    def _notes(self):
        """Every note row in the tree."""
        for i in range(self.list.topLevelItemCount()):
            sec = self.list.topLevelItem(i)
            yield from (sec.child(k) for k in range(sec.childCount()))

    def _fix_local(self):
        stems = [n.path.stem for n in self._items()]
        if stems and getattr(self, "runs", None):
            self.runs.run_notes(stems)
            self.tabs.setCurrentWidget(self.runs)

    def refresh(self):
        from core import fix_notes
        self.list.blockSignals(True)                     # filling the tree is not the person ticking
        self.list.clear()
        q = self.find.text().lower().strip()
        found = [n for n in fix_notes.notes(None if self.show_done.isChecked() else "open")
                 if not q or q in (n.text + " " + n.where).lower()]
        heads = {}
        fixing = {p: t.n for t in self.sessions.sessions() if t.working() or t.note_queue
                  for p in t.note_paths + [str(q.path) for q in t.note_queue]}
        for name in [name for name, _ in fix_notes.SECTIONS] + ["Other"]:
            mine = [n for n in found if fix_notes.section(n.text + " " + n.where) == name]      # newest first
            if not mine:
                continue
            head = QTreeWidgetItem(self.list, [f"{name}  ({len(mine)})"])
            head.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            head.setData(0, Qt.UserRole + 1, name)
            f = head.font(0)
            f.setBold(True)
            head.setFont(0, f)
            heads[name] = head
            for n in mine:
                busy = f"[being fixed in session {fixing[str(n.path)]}]  " if str(n.path) in fixing else ""
                it = QTreeWidgetItem(head, [f"{busy}{'' if n.status == 'open' else '[' + n.status + ']  '}"
                                            f"{n.text.splitlines()[0][:100]}   — {n.where[:60]}  ({n.created})"])
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                it.setCheckState(0, Qt.Checked if str(n.path) in self.ticked else Qt.Unchecked)
                it.setData(0, Qt.UserRole, n)
            if not any(str(n.path) in self.ticked for n in mine):
                head.setCheckState(0, Qt.Unchecked)      # otherwise Qt works it out from its notes
        for name, head in heads.items():
            head.setExpanded(name not in self.folded)
        self.list.blockSignals(False)
        self._count()
        if not found:
            self.detail.setText("Nothing matches." if q else "No notes yet. Right-click anything in a SAINT window "
                                                              "and choose “Note to fix this…”.")

    def _ticked(self, it, _col=0):
        n = it.data(0, Qt.UserRole)
        if n is not None:
            (self.ticked.add if it.checkState(0) == Qt.Checked else self.ticked.discard)(str(n.path))
            self._count()

    def _tick_all(self, on: bool):
        """Every note shown (not ones hidden by the search); Deselect all also forgets hidden ticks."""
        if not on:
            self.ticked.clear()
        for it in self._notes():
            it.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self._count()

    def _count(self):
        self.count.setText(f"{len(self._items())} ticked")

    def _preview(self, it, _prev=None):
        if it is None or it.data(0, Qt.UserRole) is None:     # a section header
            return
        n = it.data(0, Qt.UserRole)
        html = f"<p>{_esc(n.text).replace(chr(10), '<br>')}</p><p style='color:gray'>{_esc(n.where)}</p>"
        if n.details:
            html += f"<pre style='color:gray'>{_esc(n.details)}</pre>"
        if n.screenshot:
            html += f"<img src='{QUrl.fromLocalFile(str(n.path.parent / n.screenshot)).toString()}' width='460'>"
        self.detail.setHtml(html)

    def _current(self):
        it = self.list.currentItem()
        return it.data(0, Qt.UserRole) if it is not None else None

    def _items(self):
        """The ticked notes that are shown."""
        return [it.data(0, Qt.UserRole) for it in self._notes() if it.checkState(0) == Qt.Checked]

    def _mark(self, status):
        from core import fix_notes
        for n in self._items() or ([self._current()] if self._current() else []):
            fix_notes.mark(n, status)
            self.ticked.discard(str(n.path))             # done with it
        self.refresh()

    def _new(self):
        from ui.note_popup import NoteDialog
        d = NoteDialog("Written in Evolve", "", "", self)
        if d.exec():
            self.refresh()

    def _obsidian(self):
        from core import fix_notes
        n = self._current()
        _open_obsidian(n.path if n else fix_notes.folder())

    def _to_chat(self):
        """The ticked notes into the chat box with their screenshots attached, for you to add to and send."""
        picked = self._items()
        if not picked:
            return
        c = self.sessions.current()
        c.attachments += [s for s in (str(n.path.parent / n.screenshot) for n in picked if n.screenshot)
                          if s not in c.attachments]
        c._chips()
        c.note_paths = sorted(set(c.note_paths) | {str(n.path) for n in picked})
        text = "\n".join(f"- {n.text.strip()}" + (f"  (where: {n.where})" if n.where else "") for n in picked)
        c.box.setPlainText((c.box.toPlainText().rstrip() + "\n\n" if c.box.toPlainText().strip() else "")
                           + "About these notes of mine:\n" + text + "\n\n")
        self.sessions.focus(c)
        c.box.setFocus()
        c.box.moveCursor(QTextCursor.End)

    def _check_done(self):
        """Read-only pass: which ticked notes are already implemented? Those get status: done in their note file."""
        picked = self._items()
        if not picked:
            return
        c = self.sessions.idle("claude")                 # a free Claude session, or a new one beside the busy ones
        lines = ["Check whether each of these notes is ALREADY implemented in this source. Do not change any code. "
                 "For each: look for the feature or fix with rg, then answer one line: `<n>. DONE / NOT DONE / "
                 "PARTLY: the evidence (file:line)`. Only for a note that is clearly DONE, change `status: open` to "
                 "`status: done` in its note file. When unsure, say NOT DONE and leave the file alone.", ""]
        for i, n in enumerate(picked, 1):
            lines += [f"{i}. {n.text.strip()}", f"   Note file: {n.path}"]
        c.folder.setCurrentIndex(0)
        c.last_request = f"Check {len(picked)} note(s) for already being fixed"
        self.sessions.focus(c)
        c.send("\n".join(lines), ask=False)

    def _fix(self):
        from core import fix_notes
        picked = self._items()
        if not picked:
            return
        fixing = {p for t in self.sessions.sessions() if t.working() or t.note_queue
                  for p in t.note_paths + [str(q.path) for q in t.note_queue]}
        picked = [n for n in picked if str(n.path) not in fixing]      # never two sessions on one note
        if not picked:
            return
        c = self.sessions.idle("claude")                 # a free Claude session, or a new one beside the busy ones
        c.folder.setCurrentIndex(0)
        c.note_paths = []
        self.sessions.focus(c)
        c.fix_notes(picked)                              # one note per run, so none gets forgotten      # its questions first, then it works until done


def _open_obsidian(path: Path):
    """The note (or folder) in Obsidian when it's installed, else in the file manager / editor."""
    from core import vault
    root = vault.path()
    import shutil
    if shutil.which("flatpak") or shutil.which("obsidian"):
        try:
            rel = Path(path).relative_to(root)
            url = QUrl(f"obsidian://open?vault={QUrl.toPercentEncoding(root.name).data().decode()}"
                       + (f"&file={QUrl.toPercentEncoding(str(rel)).data().decode()}" if Path(path).is_file() else ""))
            if QDesktopServices.openUrl(url):
                return
        except ValueError:
            pass
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class VaultTab(QWidget):
    """SAINT's vault: every note, read it here, open it in Obsidian."""

    def __init__(self):
        super().__init__()
        from core import vault
        self.root = vault.ensure(skills=False) if hasattr(vault, "ensure") else vault.path()
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(f"<b>SAINT Vault</b>  <span style='color:gray'>{_esc(str(self.root))}</span>"), 1)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter notes…")
        self.filter.textChanged.connect(self.refresh)
        top.addWidget(self.filter)
        v.addLayout(top)
        split = QSplitter()
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show)
        self.view = QTextBrowser()
        split.addWidget(self.list)
        split.addWidget(self.view)
        split.setSizes([300, 600])
        v.addWidget(split, 1)
        row = QHBoxLayout()
        for label, fn in (("Refresh", self.refresh), ("New note", self._new), ("Open in Obsidian", self._obsidian),
                          ("Open folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root))))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self.refresh()

    def refresh(self):
        q = self.filter.text().lower().strip()
        self.list.clear()
        files = sorted(self.root.rglob("*.md"), key=lambda p: -p.stat().st_mtime)
        for p in files:
            rel = str(p.relative_to(self.root))
            if rel.startswith(".") or (q and q not in rel.lower()):
                continue
            it = QListWidgetItem(rel)
            it.setData(Qt.UserRole, str(p))
            self.list.addItem(it)

    def _show(self, it, _prev=None):
        if it is None:
            return
        p = Path(it.data(Qt.UserRole))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            text = str(e)
        self.view.document().setBaseUrl(QUrl.fromLocalFile(str(p.parent) + "/"))
        self.view.setMarkdown(text)

    def _new(self):
        d = self.root / "Notes"
        d.mkdir(exist_ok=True)
        p = d / f"Note {time.strftime('%Y-%m-%d %H%M')}.md"
        p.write_text("# New note\n\n", encoding="utf-8")
        self.refresh()
        _open_obsidian(p)

    def _obsidian(self):
        it = self.list.currentItem()
        _open_obsidian(Path(it.data(Qt.UserRole)) if it else self.root)


STAGES = ["new", "planned", "approved", "applied", "tested"]


class RunsTab(QWidget):
    """Evolve changes made by tools/dev/evolve_batch.py (local models): stage, live output, plan, tests, diff."""

    def __init__(self):
        super().__init__()
        self.batch = None
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Changes the local models are making, each in its own worktree. Nothing reaches SAINT "
                           "until you press <b>Keep</b>."))
        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(lambda *_: self._show(force=True))
        split.addWidget(self.list)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.stages = QLabel("")
        rv.addWidget(self.stages)
        self.detail = QTabWidget()
        self.live, self.plan, self.tests, self.diff = (QPlainTextEdit() for _ in range(4))
        for w, name in ((self.live, "Live"), (self.plan, "Plan"), (self.tests, "Tests"), (self.diff, "Diff")):
            w.setReadOnly(True)
            self.detail.addTab(w, name)
        rv.addWidget(self.detail, 1)
        split.addWidget(right)
        split.setSizes([330, 670])
        v.addWidget(split, 1)
        row = QHBoxLayout()
        self.state = QLabel("")
        row.addWidget(self.state, 1)
        for label, fn in (("Keep", self._keep), ("Drop", self._drop)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.shown = ("", "", 0)
        t = QTimer(self)
        t.timeout.connect(self.refresh)
        t.start(2000)
        self.refresh()

    def run_notes(self, stems):
        if self.batch is not None and self.batch.state() != QProcess.NotRunning:
            self.state.setText("A batch is already running; it picks up more notes when it's done.")
            return
        self.batch = QProcess(self)
        self.batch.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        self.batch.start(sys.executable, ["tools/dev/evolve_batch.py", *stems])
        self.state.setText(f"Started {len(stems)} note(s) on the local models.")

    def _ch(self):
        it = self.list.currentItem()
        if not it:
            return None
        from core import evolve
        return evolve.SourceChange.load(it.data(Qt.UserRole))

    def refresh(self):
        from core import evolve
        cur = self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        icons = {"tested": "✅", "kept": "📦", "failed": "❌", "rolled back": "↩️"}
        hist = evolve.source_history()
        self.list.blockSignals(True)
        self.list.clear()
        for h in hist:
            it = QListWidgetItem(f"{icons.get(h['status'], '⏳')} {h['request'].splitlines()[0][:70]}\n    {h['status']} · {h['id']}")
            it.setData(Qt.UserRole, h["path"])
            self.list.addItem(it)
            if h["path"] == cur or (cur is None and self.list.count() == 1):
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        self._show()

    def _show(self, force=False):
        ch = self._ch()
        if ch is None:
            return
        live_p = ch.meta / "live.log"
        size = live_p.stat().st_size if live_p.exists() else 0
        if not force and self.shown == (ch.id, ch.status, size):
            return
        self.shown = (ch.id, ch.status, size)
        done = STAGES.index(ch.status) if ch.status in STAGES else (len(STAGES) if ch.status == "kept" else -1)
        self.stages.setText("  →  ".join(f"<b style='color:#4c4'>{s}</b>" if i <= done else
                                         f"<span style='color:gray'>{s}</span>" for i, s in enumerate(STAGES))
                            + ("" if done >= 0 else f"  <b style='color:#e66'>{_esc(ch.status)}</b>"))
        at_end = self.live.verticalScrollBar().value() >= self.live.verticalScrollBar().maximum() - 4
        self.live.setPlainText((live_p.read_text(encoding="utf-8", errors="replace")[-60000:] if size else "")
                               + "\n".join(ch.log))
        if at_end:
            self.live.moveCursor(QTextCursor.End)
        self.plan.setPlainText(ch.plan or "(no plan yet)")
        self.tests.setPlainText((ch.tests or {}).get("output", "(not tested yet)"))
        if ch.status in ("applied", "tested", "failed", "kept"):
            from core import evolve
            try:
                self.diff.setPlainText(evolve.diff(ch))
            except Exception as e:
                self.diff.setPlainText(f"(no diff: {e})")

    def _keep(self):
        from core import evolve
        ch = self._ch()
        try:
            self.state.setText(evolve.keep(ch) if ch else "")
            from core import fix_notes
            stems = {l.split(" note ", 1)[1] for l in (ch.log if ch else []) if " note " in l}
            for n in fix_notes.open_notes():
                if n.path.stem in stems:
                    fix_notes.mark(n, "done")
        except Exception as e:
            self.state.setText(f"<span style='color:#e66'>{_esc(str(e))}</span>")
        self.refresh()

    def _drop(self):
        from core import evolve
        ch = self._ch()
        try:
            self.state.setText("; ".join(evolve.rollback(ch)) if ch else "")
        except Exception as e:
            self.state.setText(f"<span style='color:#e66'>{_esc(str(e))}</span>")
        self.refresh()


class EvolveWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evolve — Claude Code on HalOS")
        self.resize(1180, 860)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.sessions = SessionsPanel()
        self.sessions.wants_focus.connect(lambda: self.tabs.setCurrentWidget(self.sessions))
        self.notes = NotesTab(self.sessions, self.tabs)
        self.tabs.addTab(self.sessions, "Sessions")
        self.tabs.addTab(self.notes, "Notes to fix")
        self.tabs.addTab(VaultTab(), "Vault")
        self.runs = RunsTab()
        self.notes.runs = self.runs
        self.tabs.addTab(self.runs, "Local runs")
        self.tabs.currentChanged.connect(lambda i: self.notes.refresh() if self.tabs.widget(i) is self.notes else None)
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(14, 10, 14, 14)
        bv.setSpacing(10)
        bv.addWidget(Header(self.sessions))
        bv.addWidget(self.tabs, 1)
        self.setCentralWidget(body)
        pal = _pal()
        self.setStyleSheet(f"QFrame#EvolveHeader {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                           f"stop:0 {pal.accent_soft}, stop:0.45 {pal.surface}, stop:1 {pal.surface}); "
                           f"border: 1px solid {pal.border}; border-radius: 14px; }}"
                           f"QTextBrowser#Transcript {{ background: {pal.surface}; border: 1px solid {pal.border}; "
                           f"border-radius: 12px; }}")
        dev = Path.home() / "saint-dev"
        if (dev / ".git").is_dir():                       # Evolve/Code map.md in the vault follows the code
            self.mapper = _Job(lambda: evolve_chat.code_map(dev))
            QTimer.singleShot(2000, self.mapper.start)

    def handle_command(self, cmd: str):
        if cmd.startswith("notes"):
            self.tabs.setCurrentWidget(self.notes)
        elif cmd.startswith("vault"):
            self.tabs.setCurrentIndex(2)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        self.sessions.shutdown()
        super().closeEvent(e)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Evolve")
    app.setApplicationDisplayName("Evolve")
    app.setDesktopFileName("halos-evolve")
    from core import instance
    cmd = argv[0] if argv else "show"
    if instance.send(cmd, name=INSTANCE):
        return 0
    from ui.taskmanager import apply_style
    apply_style(app)
    try:
        from ui.note_hook import install
        install(app)
    except Exception:
        pass
    win = EvolveWindow()
    server = instance.Server(app, name=INSTANCE)
    server.command.connect(win.handle_command)
    win.show()
    if argv:
        win.handle_command(cmd)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
