"""Settings page "What SAINT may do": how much SAINT is trusted in each area, and the list of what it did, with Undo.
The rules themselves are in core/actions/trust.py; this page only shows and sets them."""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton

from core import actions
from core.actions import trust
from core.events import EventType
from ui.reactive import ui_bus
from ui.widgets import Page

TITLE = "What SAINT may do"
ICON = "check-circle"
ORDER = 20
GROUP = "SAINT"

CATEGORY_LABEL = {"settings": "Settings (display, sound, theme, power)", "network": "Wi-Fi and Bluetooth",
                  "files": "Files (move, rename, trash)", "packages": "Installing and removing apps",
                  "services": "Background services", "power": "Lock, sleep, restart, shut down",
                  "windows": "Windows (focus, snap, close)", "shell": "Running commands",
                  "agent": "Claude Code agent (bigger jobs, coding)"}
LEVEL_HELP = {trust.ASK: "SAINT asks before every action here.",
              trust.ASK_RISKY: "SAINT does safe things at once and asks before risky ones.",
              trust.TRUSTED: "SAINT does safe and risky things at once."}
AGENT_HELP = {trust.ASK: "Claude Code only makes a plan; you approve it before anything changes.",
              trust.ASK_RISKY: "Claude Code reads and edits files in the task's folder; commands and the web are refused.",
              trust.TRUSTED: "Claude Code decides with its own safety checks, including running commands."}
ALWAYS = ("Whatever you choose, anything that can lose data or work (deleting, restarting, dangerous commands) "
          "always shows what it will do and asks first.")
SOURCE = {"gui": "You", "saint": "SAINT", "agent": "SAINT (agent)"}


def entry_line(e: dict) -> str:
    """One row of the log: time, who, what happened."""
    when = datetime.fromtimestamp(e.get("time", 0)).strftime("%d %b %H:%M")
    if e.get("undone"):
        mark = "undone"
    elif e.get("ok"):
        mark = "done"
    else:
        mark = {"DECLINED": "you said no", "DENIED": "blocked"}.get(e.get("code", ""), "failed")
    text = e.get("message") if e.get("ok") else (e.get("error") or e.get("title"))
    return f"{when}  {SOURCE.get(e.get('source'), 'SAINT')}: {e.get('title')}  ({mark})\n{(text or '').strip()[:160]}"


class AIControlPage(Page):
    def __init__(self):
        super().__init__(TITLE, "Choose how much SAINT does on its own in each area. Everything it does is listed "
                                "below and most of it can be undone.", scroll=True)
        actions.load_builtin()
        note = QLabel(ALWAYS)
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self.root.addWidget(note)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        self.boxes = {}
        for category in actions.registry.categories(platform=None) + ["agent"]:   # agent: core/claude_agent.py
            box = QComboBox()
            for level in trust.LEVELS:
                box.addItem(trust.LEVEL_LABELS[level], level)
                box.setItemData(box.count() - 1, LEVEL_HELP[level], Qt.ToolTipRole)
            box.setCurrentIndex(trust.LEVELS.index(trust.get_level(category)))
            box.currentIndexChanged.connect(lambda _i, c=category, b=box: self._set(c, b.currentData()))
            self.boxes[category] = box
            form.addRow(CATEGORY_LABEL.get(category, category.capitalize()), box)
        self.root.addLayout(form)
        self.said = QLabel("")
        self.said.setObjectName("Muted")
        self.said.setWordWrap(True)
        self.root.addWidget(self.said)

        head = QHBoxLayout()
        title = QLabel("WHAT SAINT DID")
        title.setObjectName("CardTitle")
        self.undo_btn = QPushButton("Undo selected")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._undo)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.undo_btn)
        self.root.addLayout(head)
        self.log = QListWidget()
        self.log.setMinimumHeight(260)
        self.log.setWordWrap(True)
        self.log.currentItemChanged.connect(lambda *_: self._sync_undo())
        self.root.addWidget(self.log)
        self.root.addStretch(1)
        ui_bus.event.connect(self._on_event)
        self.refresh()

    def _set(self, category: str, level: str):
        trust.set_level(category, level)
        help_ = AGENT_HELP if category == "agent" else LEVEL_HELP
        self.said.setText(f"{CATEGORY_LABEL.get(category, category)}: {help_[level]}")

    def _on_event(self, ev):
        if ev.type in (EventType.ACTION_DONE, EventType.ACTION_FAILED, EventType.ACTION_DENIED,
                       EventType.ACTION_UNDONE):
            self.refresh()

    def refresh(self):
        from core.actions import log as log_mod
        entries = log_mod.action_log.entries(limit=60)
        self.log.clear()
        for e in entries:
            item = QListWidgetItem(entry_line(e))
            item.setData(Qt.UserRole, e["id"] if e.get("can_undo") else "")
            self.log.addItem(item)
        if not entries:
            empty = QListWidgetItem("Nothing yet. When SAINT changes a setting, moves a file or runs a command, it "
                                    "shows up here.")
            empty.setFlags(Qt.NoItemFlags)
            self.log.addItem(empty)
        self._sync_undo()

    def _sync_undo(self):
        item = self.log.currentItem()
        self.undo_btn.setEnabled(bool(item and item.data(Qt.UserRole)))

    def _undo(self):
        item = self.log.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        result = actions.undo(item.data(Qt.UserRole))
        self.said.setText(result.text)
        self.refresh()


def build():
    return AIControlPage()
