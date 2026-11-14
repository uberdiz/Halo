"""
ui/pages/activity.py

Never hide anything: every event through SAINT, live, filterable. The same
events also go to the rotating log file (data/logs/saint.log). Common events
read as plain words ("Finished  spotify.next · 212 ms"); anything else shows
its raw type and data. Changing the filter or the tab re-filters what's shown.
"""

import logging
from collections import deque

from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

from core.logger import NOISY_EVENTS, read_recent_lines
from ui.reactive import ui_bus
from ui.widgets import IconButton, Page, Segmented

GROUPS = [
    ("All", ()),
    ("Voice", ("voice.", "wake.", "tts.")),
    ("Agent & tools", ("agent.", "tool.", "ai.", "conversation.", "automation.", "memory.")),
    ("Spotify", ("spotify.",)),
    ("Problems", ("error", "warning", ".failed", ".error", "crash")),
]

# event type -> what it means, in plain words
PLAIN = {
    "app.started": "SAINT started", "avatar_appeared": "SAINT appeared", "voice.followup.request": "Listening again", "assistant.state": "Status", "ui.updated": "Opened page",
    "conversation.turn.start": "You said", "ui.chat.render": "SAINT said", "conversation.turn.end": "Reply done",
    "tool.requested": "Asked to run", "tool.started": "Running", "tool.completed": "Finished",
    "tool.failed": "Failed", "tool.permission.required": "Needs your OK", "tool.permission.granted": "Allowed",
    "tool.permission.denied": "Not allowed", "voice.stt.final": "Heard", "voice.interrupt": "Interrupted",
    "wake.status": "Wake word", "spotify.playback.changed": "Music", "spotify.error": "Spotify problem",
    "ai.error": "AI problem", "tts.error": "Voice problem", "error": "Error", "warning": "Warning",
}
_DETAIL_KEYS = ("tool", "text", "label", "page", "message", "error", "reason", "track", "status")


def describe(etype: str, payload) -> str:
    """One readable line (without the time) for an event."""
    p = payload if isinstance(payload, dict) else {}
    what = PLAIN.get(etype)
    if not what:
        return f"{etype}  {payload}" if payload else etype
    detail = next((str(p[k]) for k in _DETAIL_KEYS if p.get(k)), "")
    if p.get("duration_ms") is not None:
        detail += f" · {int(p['duration_ms'])} ms"
    if etype == "tool.failed" and p.get("error") and p.get("tool"):
        detail += f" · {p['error']}"
    return f"{what:<14}{detail}".rstrip()


class ActivityPage(Page):
    def __init__(self):
        super().__init__("Activity", "Everything SAINT does, live: what it heard, ran and said.")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(220)
        self.pause = IconButton("pause", "Pause the feed", 16, checkable=True)
        clear = IconButton("trash", "Clear the feed", 16)
        clear.clicked.connect(self._clear)
        for w in (self.search, self.pause, clear):
            self.actions.addWidget(w)
        self.groups = Segmented([g[0] for g in GROUPS])
        self.root.addWidget(self.groups)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName("ConsoleOutput")
        self.output.setMaximumBlockCount(3000)
        self.output.setPlaceholderText("Nothing here yet. Events show up as they happen.")
        self.root.addWidget(self.output, 1)
        self._lines = deque(maxlen=3000)        # (event type or "", shown line) — re-filtered on change
        for line in read_recent_lines(200):
            self._lines.append(("", line.rstrip("\n")))
        self.groups.changed.connect(lambda _i: self._rerender())
        self.search.textChanged.connect(lambda _t: self._rerender())
        self._rerender()
        ui_bus.event.connect(self._on_event)

    def _match(self, etype: str, text: str) -> bool:
        keys = GROUPS[max(0, self.groups.index())][1]
        hay = f"{etype} {text}"
        if keys and not any(k in hay for k in keys):
            return False
        q = self.search.text().strip().lower()
        return not q or q in hay.lower()

    def _rerender(self):
        self.output.setPlainText("\n".join(line for etype, line in self._lines if self._match(etype, line)))
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def _clear(self):
        self._lines.clear()
        self.output.clear()

    def _on_event(self, ev):
        if self.pause.isChecked():
            return
        if ev.type in NOISY_EVENTS and not logging.getLogger("saint").isEnabledFor(logging.DEBUG):
            return
        line = f"{ev.formatted_time()}   {describe(str(ev.type), ev.payload)}"
        self._lines.append((str(ev.type), line))
        if self._match(str(ev.type), line):
            self.output.appendPlainText(line)
