"""
ui/pages/agent.py

SAINT's agent workspace: give Claude Code a task, watch its steps live, read what it did, continue it, or approve
its plan. Several tasks can run at once; each runs in the background and never takes focus
(core/claude_agent.py). Trust for it is set in Settings > What SAINT may do ("Claude Code agent").
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from core import claude_agent as ca
from core.events import EventType
from ui.reactive import ui_bus
from ui.widgets import Page, chip, clear_layout, set_chip

STATUS = {"starting": ("Starting", "accent"), "running": ("Working", "accent"), "planned": ("Plan ready", "warn"),
          "done": ("Done", "ok"), "failed": ("Didn't finish", "err"), "stopped": ("Stopped", "")}
GLYPH = {"pending": "○", "running": "●", "done": "✓", "failed": "✕", "skipped": "–"}


class AgentPage(Page):
    def __init__(self, shell=None, engine=ca):
        super().__init__("Agent", "Give SAINT a bigger job. Claude Code does it with your Claude subscription, step by "
                                  "step, while you keep working.")
        self.engine = engine
        self.cwd = None
        row = QHBoxLayout()
        self.task = QLineEdit()
        self.task.setPlaceholderText("What should SAINT do? e.g. \"fix the failing tests in my project\"")
        self.task.returnPressed.connect(self.go)
        self.folder = QPushButton("Folder…")
        self.folder.setObjectName("Ghost")
        self.folder.clicked.connect(self._pick)
        self.go_btn = QPushButton("Start")
        self.go_btn.setObjectName("Primary")
        self.go_btn.clicked.connect(self.go)
        row.addWidget(self.task, 1)
        row.addWidget(self.folder)
        row.addWidget(self.go_btn)
        self.root.addLayout(row)
        self.where = QLabel("Works in your home folder.")
        self.where.setObjectName("Muted")
        self.root.addWidget(self.where)

        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumWidth(300)
        self.list.currentItemChanged.connect(lambda *_: self.show_run())
        body.addWidget(self.list)
        detail = QVBoxLayout()
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: 600;")
        self.badge = chip("")
        self.badge.hide()
        head.addWidget(self.title, 1)
        head.addWidget(self.badge)
        detail.addLayout(head)
        self.steps = QVBoxLayout()
        detail.addLayout(self.steps)
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("What Claude Code did shows up here.")
        detail.addWidget(self.result, 1)
        actions_row = QHBoxLayout()
        self.more = QLineEdit()
        self.more.setPlaceholderText("Follow up on this task…")
        self.more.returnPressed.connect(self.follow)
        self.approve_btn = QPushButton("Approve plan")
        self.approve_btn.setObjectName("Primary")
        self.approve_btn.clicked.connect(self.approve)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("Ghost")
        self.stop_btn.clicked.connect(self.stop)
        actions_row.addWidget(self.more, 1)
        actions_row.addWidget(self.approve_btn)
        actions_row.addWidget(self.stop_btn)
        detail.addLayout(actions_row)
        body.addLayout(detail, 1)
        self.root.addLayout(body, 1)
        ui_bus.event.connect(self._on_event)
        self.refresh()

    # ------------------------------------------------------------------ #
    def _pick(self):
        folder = QFileDialog.getExistingDirectory(self, "Where should SAINT work?")
        if folder:
            self.cwd = folder
            self.where.setText(f"Works in {folder}.")

    def go(self):
        text = self.task.text().strip()
        if not text:
            return
        run = self.engine.start(text, self.cwd)
        self.task.clear()
        self.refresh(select=run.id)

    def follow(self):
        run = self.current()
        text = self.more.text().strip()
        if run is None or not text:
            return
        try:
            new = self.engine.follow_up(run.id, text)
        except KeyError as e:
            self.result.setPlainText(str(e))
            return
        self.more.clear()
        self.refresh(select=new.id)

    def approve(self):
        run = self.current()
        if run is not None:
            try:
                self.refresh(select=self.engine.approve(run.id).id)
            except KeyError as e:
                self.result.setPlainText(str(e))

    def stop(self):
        run = self.current()
        if run is not None:
            self.engine.stop(run.id)

    def _on_event(self, ev):
        if ev.type in (EventType.PLAN_STARTED, EventType.PLAN_STEP, EventType.PLAN_DONE):
            if any(r.id == (ev.payload or {}).get("plan") for r in self.engine.runs()):
                self.refresh()

    # ------------------------------------------------------------------ #
    def current(self):
        item = self.list.currentItem()
        rid = item.data(Qt.UserRole) if item else None
        return next((r for r in self.engine.runs() if r.id == rid), None)

    def refresh(self, select=None):
        keep = select or (self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None)
        self.list.blockSignals(True)
        self.list.clear()
        for r in self.engine.runs():
            word = STATUS.get(r.status, (r.status, ""))[0]
            item = QListWidgetItem(f"{r.task[:60]}\n{word}")
            item.setData(Qt.UserRole, r.id)
            self.list.addItem(item)
            if r.id == keep:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.show_run()

    def show_run(self):
        run = self.current()
        clear_layout(self.steps)
        if run is None:
            self.title.setText("No tasks yet.")
            self.badge.hide()
            self.result.clear()
            for b in (self.approve_btn, self.stop_btn, self.more):
                b.setEnabled(False)
            return
        self.title.setText(run.task)
        word, kind = STATUS.get(run.status, (run.status, ""))
        set_chip(self.badge, word, kind)
        self.badge.show()
        for s in run.steps:
            label = QLabel(f"{GLYPH.get(s.status, '○')}  {s.title}" + (f"\n     {s.message}" if s.message else ""))
            label.setWordWrap(True)
            self.steps.addWidget(label)
        text = run.error if run.status in ("failed", "stopped") else run.result
        if run.cost_usd:
            text += f"\n\n({run.turns} turns)"
        self.result.setPlainText(text)
        self.approve_btn.setVisible(run.status == "planned")
        self.approve_btn.setEnabled(run.status == "planned")
        self.stop_btn.setEnabled(run.status in ("starting", "running"))
        self.more.setEnabled(bool(run.session_id) and run.status not in ("starting", "running"))
