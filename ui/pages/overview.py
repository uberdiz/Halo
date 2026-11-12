"""
ui/pages/overview.py

The main screen: what SAINT is doing, what needs you, and the state of everything around it.

    ┌ Current task ──────────────┐ ┌ Needs attention ┐
    │ Setting up coding workspace│ │ Now playing     │
    │ ✓ … ● … ○ …   [Pause][Stop]│ │ Devices         │
    ├ Conversation ──────────────┤ │ System health   │
    ├ Recent activity ───────────┤ │ Up next         │
    └────────────────────────────┘ └─────────────────┘

Two columns when there's room, one when there isn't. Which panels show and in what order is
yours (Settings › Appearance › Layout: ``layout.overview_hidden`` / ``layout.overview_order``).
"""

import os
from datetime import datetime
from typing import Dict, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QPushButton,
                               QVBoxLayout, QWidget)

from core.config import config
from core.events import EventType
from ui import actions, icons
from ui.components.activity_item import ToolRow, TrailView, drop_demo_rows
from ui.components.attention import AttentionPanel
from ui.components.device_card import DevicesPanel
from ui.components.health_panel import HealthPanel
from ui.components.panel import Panel
from ui.components.task_card import TaskCard
from ui.design import tokens
from ui.reactive import ui_bus
from ui.theme import current_palette
from ui.widgets import ChatView, ElidedLabel, Page, clear_layout, run_async

# key, title, column ("main" / "side")
PANELS = [("task", "Current task", "main"), ("attention", "Needs attention", "side"),
          ("reminders", "Reminders", "main"), ("quick", "Quick actions", "side"),
          ("tasks", "SAINT tasks", "side"), ("summary", "This PC", "side"),
          ("conversation", "Conversation", "main"), ("media", "Now playing", "side"),
          ("activity", "Recent activity", "main"), ("devices", "Devices", "side"),
          ("health", "System health", "side"), ("next", "Up next", "side")]
TWO_COLUMNS_FROM = 980


def panel_order() -> List[str]:
    order = [k for k in (config.get("layout.overview_order", []) or []) if any(k == p[0] for p in PANELS)]
    keys = order + [p[0] for p in PANELS if p[0] not in order]
    hidden = set(config.get("layout.overview_hidden", []) or [])
    return [k for k in keys if k not in hidden]


class ActivityPanel(Panel):
    """The current (or last) task's trail, newest first; the live tool feed when there's no task."""

    def __init__(self, parent=None):
        super().__init__("Recent activity", parent=parent)
        self.trail = TrailView(newest_first=True, limit=10)
        self.body.addWidget(self.trail)
        self.live = QVBoxLayout()
        self.live.setSpacing(0)
        self.body.addLayout(self.live)
        self._rows: List[ToolRow] = []
        self._task_id = None
        ui_bus.event.connect(self._on_event)
        ui_bus.demo_changed.connect(lambda on: None if on else drop_demo_rows(self._rows, QLabel()))
        self.refresh()

    def refresh(self):
        t = actions.current_task()
        if t and t.get("trail"):
            self._task_id = t["id"]
            self.set_hint(t.get("goal", "")[:48])
            self.trail.set_entries(t["trail"])
            self.trail.show()
            self.relayout()
        else:
            self.trail.set_entries([], "Tools SAINT uses and the steps of its tasks appear here as they happen.")
            self.trail.setVisible(not self._rows)

    def _on_event(self, ev):
        t, p = ev.type, ev.payload or {}
        if t == EventType.AGENT_TASK:
            self._task_id = p.get("id")
            self.set_hint(p.get("goal", "")[:48])
            self.trail.set_entries(p.get("trail") or [])
            self.trail.show()
            self.relayout()
        elif t == EventType.TOOL_STARTED:
            row = ToolRow(p.get("tool", ""))
            self._rows.insert(0, row)
            self.live.insertWidget(0, row)
            while len(self._rows) > 4:
                self._rows.pop().deleteLater()
        elif t in (EventType.TOOL_COMPLETED, EventType.TOOL_FAILED):
            row = next((r for r in self._rows if r.tool == p.get("tool") and r.running), None)
            if row is not None:
                row.done(t == EventType.TOOL_COMPLETED, p.get("duration_ms", 0), p.get("error", ""))


class ConversationPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Conversation", parent=parent)
        clear = QPushButton("Clear")
        clear.setObjectName("Ghost")
        self.add_action(clear)
        self.chat = ChatView(max_messages=40)
        self.chat.setMinimumHeight(150)
        self.chat.setMaximumHeight(260)
        clear.clicked.connect(lambda: self.chat.clear_chat())
        self.body.addWidget(self.chat)
        actions.ChatBinder(self.chat, self)
        if self.chat.is_empty():
            self.chat.add("system", "Say “Hey SAINT” — or type in the box at the bottom.")


class MediaPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Now playing", parent=parent)
        from ui.pages.music import NowPlaying
        self.player = NowPlaying(cover=64, show_hint=False, any_media=True, volume=True)
        self.body.addWidget(self.player)


class NextPanel(Panel):
    def __init__(self, parent=None):
        super().__init__("Up next", parent=parent)
        self.next_list = QVBoxLayout()
        self.next_list.setSpacing(6)
        self.body.addLayout(self.next_list)
        self.scene_row = QHBoxLayout()
        self.scene_row.setSpacing(6)
        self.body.addLayout(self.scene_row)
        ui_bus.event.connect(self._on_event)
        QTimer.singleShot(400, self.refresh)

    def _on_event(self, ev):
        if ev.type in (EventType.AUTOMATION_CREATED, EventType.AUTOMATION_UPDATED, EventType.AUTOMATION_CANCELLED,
                       EventType.AUTOMATION_TRIGGERED):
            self.refresh()

    def refresh(self):
        from modules.automation.scenes import scenes
        from modules.automation.scheduler import scheduler

        def load():
            return [a for a in scheduler.list(active_only=True) if a.status == "active"][:4], scenes.all()[:3]

        def show(data):
            autos, scs = data
            clear_layout(self.next_list)
            if not autos:
                lab = QLabel("Nothing scheduled. Try “remind me at 5 to stretch”.")
                lab.setObjectName("Faint")
                lab.setWordWrap(True)
                self.next_list.addWidget(lab)
            for a in autos:
                row = QHBoxLayout()
                when = QLabel(datetime.fromtimestamp(a.next_run).strftime("%a %H:%M") if a.next_run else "—")
                when.setObjectName("Faint")
                when.setFixedWidth(70)
                row.addWidget(when)
                row.addWidget(ElidedLabel(a.title + ("  ↻" if a.recurring else "")), 1)
                self.next_list.addLayout(row)
            clear_layout(self.scene_row)
            for s in scs:
                b = QPushButton(s.name)
                b.setObjectName("SceneButton")
                b.setIcon(icons.icon("zap", current_palette().accent, 14))
                b.setToolTip("Run: " + " → ".join(s.steps))
                b.clicked.connect(lambda _=False, sc=s: actions.run_scene(sc))
                self.scene_row.addWidget(b)
            self.scene_row.addStretch()
        run_async(load, show, lambda _e: None)


# --------------------------------------------------------------------------- Home widgets
def bucket_reminders(autos, now: float) -> Dict[str, list]:
    """Overdue (missed, or due and not yet fired), today, and later — for the Reminders panel."""
    end_of_day = datetime.fromtimestamp(now).replace(hour=23, minute=59, second=59).timestamp()
    out = {"overdue": [], "today": [], "upcoming": []}
    for a in autos:
        if a.status == "missed" or (a.status == "active" and a.next_run and a.next_run <= now):
            out["overdue"].append(a)
        elif a.status == "active" and a.next_run:
            out["today" if a.next_run <= end_of_day else "upcoming"].append(a)
    return out


def _tool(name: str, done, **kwargs):
    """Run a registered tool off the GUI thread; ``done(error_or_empty)`` on the GUI thread."""
    from modules.automation.tools import get_tool_registry
    run_async(lambda: get_tool_registry().execute(name, **kwargs),
              lambda r: done("" if r.success else (r.error or "That didn't work.")), lambda e: done(str(e)))


class RemindersPanel(Panel):
    """Overdue, today and upcoming reminders with Snooze / Dismiss, and a quick "remind me" line."""

    def __init__(self, parent=None):
        super().__init__("Reminders", parent=parent)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(4)
        self.body.addLayout(self.rows)
        add = QHBoxLayout()
        self.what = QLineEdit()
        self.what.setPlaceholderText("Remind me to…")
        self.when = QLineEdit()
        self.when.setPlaceholderText("when (in 20 min, at 5pm)")
        self.when.setMaximumWidth(170)
        go = QPushButton("Add")
        go.clicked.connect(self._create)
        self.when.returnPressed.connect(self._create)
        for w in (self.what, self.when, go):
            add.addWidget(w)
        self.body.addLayout(add)
        self.status = QLabel("")
        self.status.setObjectName("Faint")
        self.status.setWordWrap(True)
        self.status.hide()
        self.body.addWidget(self.status)
        ui_bus.event.connect(self._on_event)
        QTimer.singleShot(400, self.refresh)
        self._tick = QTimer(self)                      # "today" becomes "overdue" without an event
        self._tick.timeout.connect(self.refresh)
        self._tick.start(60000)

    def _on_event(self, ev):
        if ev.type in (EventType.AUTOMATION_CREATED, EventType.AUTOMATION_UPDATED, EventType.AUTOMATION_CANCELLED,
                       EventType.AUTOMATION_TRIGGERED):
            self.refresh()

    def _say(self, text: str):
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _create(self):
        what, when = self.what.text().strip(), self.when.text().strip()
        if not what or not when:
            self._say("Say what and when.")
            return

        def done(err):
            self._say(err)
            if not err:
                self.what.clear()
                self.when.clear()
        _tool("automation.create_reminder", done, message=what, when=when)

    def refresh(self):
        from modules.automation.scheduler import scheduler

        def load():
            return bucket_reminders([a for a in scheduler.list() if a.kind == "reminder"], datetime.now().timestamp())
        run_async(load, self._show, lambda _e: None)

    def _show(self, b):
        clear_layout(self.rows)
        n = 0
        for key, label in (("overdue", "Overdue"), ("today", "Today"), ("upcoming", "Upcoming")):
            items = b[key][:4 if key != "upcoming" else 3]
            if not items:
                continue
            head = QLabel(label.upper())
            head.setObjectName("WarnText" if key == "overdue" else "StatLabel")
            self.rows.addWidget(head)
            for a in items:
                self.rows.addLayout(self._row(a, key))
                n += 1
        self.set_hint(f"{len(b['overdue'])} overdue" if b["overdue"] else "")
        if not n:
            lab = QLabel("No reminders. Add one below, or say “remind me at 5 to stretch”.")
            lab.setObjectName("Faint")
            lab.setWordWrap(True)
            self.rows.addWidget(lab)
        self.relayout()

    def _row(self, a, key):
        row = QHBoxLayout()
        fmt = "%H:%M" if key == "today" else "%a %H:%M"
        when = QLabel(datetime.fromtimestamp(a.next_run).strftime(fmt) if a.next_run else "missed")
        when.setObjectName("Faint")
        when.setFixedWidth(70)
        row.addWidget(when)
        row.addWidget(ElidedLabel(a.title + ("  ↻" if a.recurring else "")), 1)
        snooze = QPushButton("Snooze")
        snooze.setObjectName("Ghost")
        snooze.setToolTip("Again in 10 minutes")
        snooze.clicked.connect(lambda _=False, i=a.id: _tool("automation.snooze", self._say, id=i, minutes=10))
        dismiss = QPushButton("Dismiss")
        dismiss.setObjectName("Ghost")
        dismiss.setToolTip("Cancel this reminder" + (" (all its repeats)" if a.recurring else ""))
        dismiss.clicked.connect(lambda _=False, i=a.id: _tool("automation.cancel", self._say, id=i))
        row.addWidget(snooze)
        row.addWidget(dismiss)
        return row


def task_groups(tasks) -> Dict[str, list]:
    """SAINT's agent tasks by what they need: running, waiting on you / paused, failed (most recent first)."""
    from modules.agent.autonomy.model import TaskStatus
    out = {"active": [], "pending": [], "failed": []}
    for t in tasks:
        key = "active" if t.status in TaskStatus.ACTIVE else "pending" if t.status in TaskStatus.OPEN else \
            "failed" if t.status == TaskStatus.FAILED else ""
        if key:
            out[key].append(t)
    return out


class TasksPanel(Panel):
    """Active, pending and failed SAINT tasks; Open goes to the Tasks page."""

    def __init__(self, shell, parent=None):
        super().__init__("SAINT tasks", parent=parent)
        self.shell = shell
        open_ = QPushButton("Open")
        open_.setObjectName("Ghost")
        open_.clicked.connect(lambda: shell.navigate("Tasks"))
        self.add_action(open_)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(4)
        self.body.addLayout(self.rows)
        ui_bus.event.connect(lambda ev: ev.type == EventType.AGENT_TASK and self.refresh())
        QTimer.singleShot(500, self.refresh)

    def refresh(self):
        g = task_groups(actions.task_list(20))
        clear_layout(self.rows)
        words = {"active": "Running", "pending": "Needs you / paused", "failed": "Failed"}
        shown = 0
        for key in ("pending", "active", "failed"):
            for t in g[key][:3]:
                row = QHBoxLayout()
                tag = QLabel(words[key])
                tag.setObjectName({"failed": "WarnText", "pending": "WarnText"}.get(key, "OkText"))
                tag.setFixedWidth(130)
                row.addWidget(tag)
                row.addWidget(ElidedLabel(t.goal or t.request), 1)
                self.rows.addLayout(row)
                shown += 1
        self.set_hint(" · ".join(f"{len(g[k])} {k}" for k in ("active", "pending", "failed") if g[k]))
        if not shown:
            lab = QLabel("No tasks running. Ask SAINT to do something multi-step and it shows here.")
            lab.setObjectName("Faint")
            lab.setWordWrap(True)
            self.rows.addWidget(lab)
        self.relayout()


def open_system_overview():
    """SAINT Task Manager at its Performance page (its own process: saint-taskmgr on Halo, the script elsewhere)."""
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    exe = shutil.which("saint-taskmgr")
    argv = [exe] if exe else [sys.executable, str(Path(__file__).resolve().parents[1] / "taskmanager.py")]
    subprocess.Popen(argv + ["--page", "Performance"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def system_summary() -> Dict:
    import psutil
    from core import sysinfo
    g = (sysinfo.gpus() or [{}])[0]
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    return {"cpu": psutil.cpu_percent(interval=0.3), "mem": psutil.virtual_memory().percent,
            "gpu": g.get("percent"), "vram": (g.get("memory_used"), g.get("memory_total")),
            "disk_free": disk.free, "uptime": datetime.now().timestamp() - psutil.boot_time()}


class SystemSummaryPanel(Panel):
    """CPU, memory, GPU, disk and uptime in one line each; the full view is the System Overview."""

    def __init__(self, parent=None):
        super().__init__("This PC", parent=parent)
        more = QPushButton("System Overview")
        more.setObjectName("Ghost")
        more.setToolTip("Per-core CPU, GPU detail, history graphs")
        more.clicked.connect(open_system_overview)
        self.add_action(more)
        self.text = QLabel("—")
        self.text.setWordWrap(True)
        self.body.addWidget(self.text)
        self._timer = QTimer(self)                     # only while shown; nvidia-smi at most every 10 s
        self._timer.timeout.connect(self.refresh)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self._timer.start(10000)

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()

    def refresh(self):
        run_async(system_summary, self._show, lambda _e: None)

    def _show(self, s):
        from core.sysinfo import human_bytes, human_duration
        used, total = s["vram"]
        gpu = "GPU not reported" if s["gpu"] is None else f"GPU {s['gpu']:.0f}%" + (
            f" · VRAM {human_bytes(used)} / {human_bytes(total)}" if total else "")
        self.text.setText(f"CPU {s['cpu']:.0f}%  ·  Memory {s['mem']:.0f}%\n{gpu}\n"
                          f"{human_bytes(s['disk_free'])} free on the system disk  ·  up {human_duration(s['uptime'])}")


DEFAULT_QUICK = ["system", "page:Tasks", "page:Automations", "page:Music", "page:Storage"]


def quick_label(action: str) -> str:
    kind, _, arg = action.partition(":")
    return "System Overview" if kind == "system" else arg if kind == "page" else f"Open {arg}"


def run_quick(action: str, shell):
    """Do one quick action: a SAINT page, the System Overview, or an app (desktop.open_app, deterministic)."""
    kind, _, arg = action.partition(":")
    if kind == "system":
        open_system_overview()
    elif kind == "page":
        shell.navigate(arg)
    elif kind == "app":
        from modules.desktop.controller import desktop
        run_async(lambda: desktop.open_app(arg), None, lambda _e: None)


class QuickActionsPanel(Panel):
    """Your shortcuts (layout.quick_actions): + adds a page or an app, right-click removes one."""

    def __init__(self, shell, parent=None):
        super().__init__("Quick actions", parent=parent)
        self.shell = shell
        add = QPushButton("+")
        add.setObjectName("Ghost")
        add.setToolTip("Add a quick action")
        add.clicked.connect(lambda: self._add_menu().exec(add.mapToGlobal(add.rect().bottomLeft())))
        self.add_action(add)
        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        self.body.addLayout(self.grid)
        self.render()

    @staticmethod
    def items() -> List[str]:
        v = config.get("layout.quick_actions", None)
        return list(DEFAULT_QUICK if v is None else v)

    def _save(self, items):
        config.set("layout.quick_actions", items)
        self.render()

    def render(self):
        clear_layout(self.grid)
        for i, act in enumerate(self.items()):
            b = QPushButton(quick_label(act))
            b.setObjectName("SceneButton")
            b.setToolTip("Right-click to remove")
            b.clicked.connect(lambda _=False, a=act: run_quick(a, self.shell))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, a=act, w=b: self._remove_menu(a).exec(w.mapToGlobal(pos)))
            self.grid.addWidget(b, i // 3, i % 3)
        if not self.items():
            lab = QLabel("No quick actions. Press + to add pages or apps.")
            lab.setObjectName("Faint")
            self.grid.addWidget(lab, 0, 0)
        self.relayout()

    def _remove_menu(self, act):
        m = QMenu(self)
        m.addAction("Remove", lambda: self._save([a for a in self.items() if a != act]))
        return m

    def _add_menu(self):
        m = QMenu(self)
        have = set(self.items())
        if "system" not in have:
            m.addAction("System Overview", lambda: self._save(self.items() + ["system"]))
        pages = [k for k in dict.fromkeys(getattr(self.shell, "page_map", {})) if k not in ("Overview", "Halo")]
        for p in pages:
            if f"page:{p}" not in have:
                m.addAction(p, lambda p=p: self._save(self.items() + [f"page:{p}"]))
        m.addSeparator()
        m.addAction("An app…", self._add_app)
        return m

    def _add_app(self):
        name, ok = QInputDialog.getText(self, "Add an app", "App name (as you'd say “open …”):")
        if ok and name.strip():
            self._save(self.items() + [f"app:{name.strip()}"])


class OverviewPage(Page):
    def __init__(self, shell):
        super().__init__("Overview", "", scroll=True)
        self.shell = shell
        customize = QPushButton("Customize")
        customize.setObjectName("Ghost")
        customize.setToolTip("Choose which panels show here, and their order")
        customize.clicked.connect(lambda: shell.open_settings("Appearance"))
        self.actions.addWidget(customize)
        self.panels: Dict[str, QWidget] = {
            "task": TaskCard(), "attention": AttentionPanel(shell), "conversation": ConversationPanel(),
            "media": MediaPanel(), "activity": ActivityPanel(), "devices": DevicesPanel(shell),
            "health": HealthPanel(shell, compact=True), "next": NextPanel(),
            "reminders": RemindersPanel(), "quick": QuickActionsPanel(shell), "tasks": TasksPanel(shell),
            "summary": SystemSummaryPanel(),
        }
        for panel in self.panels.values():                 # owned by the page even while hidden
            panel.setParent(self.scroll.widget())
            panel.hide()
        from ui.components.live_banner import LiveBanner
        self.live_banner = LiveBanner()                    # hidden unless running live from the ISO
        self.root.addWidget(self.live_banner)
        self.cols = QHBoxLayout()
        self.cols.setSpacing(tokens.SECTION_GAP)
        self.main = QVBoxLayout()
        self.main.setSpacing(tokens.SECTION_GAP)
        self.side = QVBoxLayout()
        self.side.setSpacing(tokens.SECTION_GAP)
        side_w = QWidget()
        side_w.setLayout(self.side)
        side_w.setMinimumWidth(300)
        side_w.setMaximumWidth(420)
        self.side_w = side_w
        self.cols.addLayout(self.main, 3)
        self.cols.addWidget(side_w, 2)
        self.root.addLayout(self.cols)
        self.root.addStretch()
        self._two = None
        self._order = None
        self.arrange()
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(30000)
        self._tick()

    def _tick(self):
        now = datetime.now()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        self.title.setText(f"Good {part}")
        self.subtitle.setText(now.strftime("%A, %B %d").replace(" 0", " "))
        self.subtitle.show()

    def arrange(self, force: bool = False):
        """Place the visible panels: two columns when wide, one when narrow."""
        width = self.scroll.viewport().width() if self.scroll is not None else self.width()
        two = width >= TWO_COLUMNS_FROM
        order = panel_order()
        if not force and two == self._two and order == self._order:
            return
        self._two, self._order = two, order
        for lay in (self.main, self.side):
            # removeWidget() deletes the layout item. takeAt() left it alive, and Qt kept routing the
            # panel's size changes to that orphan item, so the new one never re-measured (rebuilt rows
            # were squeezed to a few pixels). Panels stay parented: never shown as loose windows.
            for panel in self.panels.values():
                lay.removeWidget(panel)
            while lay.count():
                item = lay.takeAt(0)
                if item is not None and item.spacerItem() is not None:
                    import shiboken6
                    shiboken6.delete(item)
        column = {k: c for k, _t, c in PANELS}
        for key in order:
            target = self.side if (two and column.get(key) == "side") else self.main
            target.addWidget(self.panels[key])
        self.main.addStretch()
        self.side.addStretch()
        self.side_w.setVisible(two)
        for key, panel in self.panels.items():
            panel.setVisible(key in order)
        # A panel that moved column has a new width: re-measure once it's laid out there.
        QTimer.singleShot(0, self._remeasure)

    def _remeasure(self):
        for key in self._order or []:
            panel = self.panels.get(key)
            if panel is not None and panel.isVisible() and hasattr(panel, "relayout"):
                panel.relayout()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.arrange()

    def showEvent(self, e):
        super().showEvent(e)
        self.arrange(force=False)

    def apply_theme(self):
        self.arrange(force=True)
        self.panels["task"].render()
