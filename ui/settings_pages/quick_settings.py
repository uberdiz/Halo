"""Settings page "Quick settings": HalOS's everyday settings, built from the OS action registry (core/actions), so
every switch here is the same action SAINT runs by voice, with the same preview, log and undo. The search box takes
plain requests ("make the text bigger", "dark mode"): a phrase SAINT knows is offered as one button, anything else
filters the list. Plasma's full settings stay one click away ("More settings")."""

import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from core import actions
from ui.widgets import Page, clear_layout, set_button_state

TITLE = "Quick settings"
ICON = "settings"
ORDER = 1

GROUPS = [("Display", "settings.display."), ("Look", "settings.appearance."), ("Sound", "settings.sound."),
          ("Power", "settings.power."), ("Network", "network."), ("Typing and pointer", "settings.input."),
          ("Time and notifications", "settings.system."), ("Time and notifications", "settings.notifications."),
          ("Apps", "settings.apps.")]


def editor(name, spec):
    """A control for one parameter, and a function that reads it."""
    if spec.type == "boolean":
        w = QCheckBox()
        w.setChecked(bool(spec.default))
        return w, w.isChecked
    if spec.enum:
        w = QComboBox()
        for v in spec.enum:
            w.addItem(str(v).replace("-", " ").replace("_", " "), v)
        if spec.default in spec.enum:
            w.setCurrentIndex(spec.enum.index(spec.default))
        return w, w.currentData
    if spec.type in ("integer", "number") and spec.minimum is not None and spec.maximum is not None:
        w = QSpinBox() if spec.type == "integer" else QDoubleSpinBox()
        w.setRange(spec.minimum, spec.maximum)
        if spec.type == "number":
            w.setSingleStep(0.25)
        w.setValue(spec.default if spec.default is not None else (spec.minimum + spec.maximum) / 2
                   if spec.type == "number" else int((spec.minimum + spec.maximum) // 2))
        return w, w.value
    w = QLineEdit()
    w.setPlaceholderText(spec.description or name)
    return w, w.text


class ActionRow(QWidget):
    """One action: its title, a control per required parameter, and Apply (through actions.execute)."""

    def __init__(self, action, confirm=None, values=None):
        super().__init__()
        self.action = action
        self.confirm = confirm
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        title = QLabel(action.title)
        title.setMinimumWidth(240)
        lay.addWidget(title)
        self.readers = {}
        for name, spec in action.params.items():
            if not spec.required and name not in (values or {}):
                continue
            w, read = editor(name, spec)
            if values and name in values:
                if isinstance(w, QCheckBox):
                    w.setChecked(bool(values[name]))
                elif isinstance(w, QComboBox):
                    w.setCurrentIndex(max(0, w.findData(values[name])))
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.setValue(values[name])
                else:
                    w.setText(str(values[name]))
            w.setToolTip(spec.description)
            lay.addWidget(w)
            self.readers[name] = read
        lay.addStretch(1)
        self.apply = QPushButton("Apply")
        self.apply.clicked.connect(self.run)
        lay.addWidget(self.apply)
        self.said = QLabel("")
        self.said.setObjectName("Muted")
        self.said.setMinimumWidth(200)
        self.said.setWordWrap(True)
        lay.addWidget(self.said)

    def params(self):
        return {k: read() for k, read in self.readers.items() if read() not in ("", None)}

    def run(self):
        set_button_state(self.apply, "busy", "…")
        result = actions.execute(self.action.id, self.params(), source="gui", confirm=self.confirm)
        set_button_state(self.apply, "done" if result.ok else "failed", "Done" if result.ok else "Didn't work", 1800)
        self.said.setText(result.text)
        return result


class QuickSettingsPage(Page):
    def __init__(self, confirm=None):
        super().__init__(TITLE, "Everyday settings in plain words. SAINT changes the same ones when you ask, and "
                                "everything can be undone in What SAINT may do.", scroll=True)
        self.confirm = confirm or self._ask
        actions.load_builtin()
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings, or ask: \"make the text bigger\"")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        more = QPushButton("More settings")
        more.setObjectName("Ghost")
        more.clicked.connect(lambda: self._plasma())
        top.addWidget(self.search, 1)
        top.addWidget(more)
        self.root.addLayout(top)
        self.suggestion = QVBoxLayout()
        self.root.addLayout(self.suggestion)
        self.body = QVBoxLayout()
        self.root.addLayout(self.body)
        self.root.addStretch(1)
        self.rows = []
        self.headings = {}
        self._build()

    def _build(self):
        seen = set()
        for heading, prefix in GROUPS:
            group = [a for a in actions.registry.list() if a.id.startswith(prefix) and a.id not in seen]
            if not group:
                continue
            if heading not in self.headings:
                label = QLabel(heading.upper())
                label.setObjectName("CardTitle")
                self.body.addWidget(label)
                self.headings[heading] = label
            for a in group:
                seen.add(a.id)
                row = ActionRow(a, self.confirm)
                row.heading = heading
                self.rows.append(row)
                self.body.addWidget(row)
        if not self.rows:
            note = QLabel("These settings are part of HalOS; on Windows, use Windows Settings.")
            note.setObjectName("Muted")
            self.body.addWidget(note)

    def filter(self, text):
        words = text.strip().lower()
        clear_layout(self.suggestion)
        if words:
            from modules.agent.os_intents import _PHRASES
            for pattern, action_id, params in _PHRASES:
                m = pattern.match(words)
                a = actions.registry.get(action_id) if m else None
                if a is not None and a.available():
                    row = ActionRow(a, self.confirm, values=params(m))
                    row.apply.setText(f"Do it: {a.describe(a.validate(params(m)))}"[:60])
                    row.apply.setObjectName("Primary")
                    self.suggestion.addWidget(row)
                    break
        hits = {a.id for a in actions.registry.search(words, limit=50)} if words else None
        shown = set()
        for row in self.rows:
            visible = hits is None or row.action.id in hits or words in row.action.title.lower()
            row.setVisible(visible)
            if visible:
                shown.add(row.heading)
        for heading, label in self.headings.items():
            label.setVisible(heading in shown)

    def _ask(self, request):
        from PySide6.QtWidgets import QMessageBox
        return QMessageBox.question(self, request.title, request.preview) == QMessageBox.Yes

    @staticmethod
    def _plasma():
        try:
            subprocess.Popen(["systemsettings"])
        except OSError:
            pass


def build():
    return QuickSettingsPage()
