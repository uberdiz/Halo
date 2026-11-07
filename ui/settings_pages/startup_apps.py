"""Control Center page "Startup apps": what starts when you sign in (core/startup_apps.py)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from core import startup_apps as sa
from ui.settings_pages.desktop import scrolling_page

TITLE = "Startup apps"
ICON = "power"
ORDER = 32

SOURCE = {"user": "Added by you", "system": "HalOS", "system+user": "HalOS", "service": "Service"}


def pick_app(parent) -> dict:
    """The installed-applications picker: the chosen app, or {} if cancelled."""
    d = QDialog(parent)
    d.setWindowTitle("Add app")
    d.resize(460, 520)
    v = QVBoxLayout(d)
    search = QLineEdit()
    search.setPlaceholderText("Search apps")
    v.addWidget(search)
    apps = QListWidget()
    v.addWidget(apps, 1)
    for app in sa.installed_apps():
        if app["file"] == "saint.desktop":        # SAINT is on the list already, as its service
            continue
        item = QListWidgetItem(app["name"])
        item.setData(Qt.UserRole, app)
        item.setToolTip(app["comment"] or app["exec"])
        apps.addItem(item)

    def narrow(text):
        for i in range(apps.count()):
            apps.item(i).setHidden(text.lower() not in apps.item(i).text().lower())

    search.textChanged.connect(narrow)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    apps.itemDoubleClicked.connect(lambda _i: d.accept())
    v.addWidget(buttons)
    if d.exec() != QDialog.Accepted or not apps.currentItem():
        return {}
    return apps.currentItem().data(Qt.UserRole)


def ask_command(parent):
    """(name, command) from the custom-command dialog, or None."""
    d = QDialog(parent)
    d.setWindowTitle("Add a command")
    form = QFormLayout(d)
    name, command = QLineEdit(), QLineEdit()
    command.setPlaceholderText("syncthing --no-browser")
    form.addRow("Name", name)
    form.addRow("Command", command)
    hint = QLabel("One program and its arguments. It doesn't run in a shell, so pipes and && aren't available.")
    hint.setObjectName("Muted")
    hint.setWordWrap(True)
    form.addRow(hint)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    form.addRow(buttons)
    return (name.text().strip(), command.text().strip()) if d.exec() == QDialog.Accepted else None


class Page:
    def __init__(self):
        self.widget, v = scrolling_page("Startup apps", "Apps that start when you sign in. Switching one off only "
                                                        "affects you.")
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        holder = QWidget()
        holder.setLayout(self.list)
        v.addWidget(holder)

        row = QHBoxLayout()
        add = QPushButton("Add app…")
        add.clicked.connect(self.add_app)
        custom = QPushButton("Add a command…")
        custom.clicked.connect(self.add_command)
        row.addWidget(add)
        row.addWidget(custom)
        row.addStretch(1)
        v.addLayout(row)

        self.msg = QLabel("")
        self.msg.setObjectName("Muted")
        self.msg.setWordWrap(True)
        v.addWidget(self.msg)
        v.addStretch(1)
        self.refresh()

    def refresh(self):
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        rows = sa.rows()
        if not rows:
            self.list.addWidget(QLabel("Nothing starts at sign-in yet."))
        for r in rows:
            self.list.addWidget(self.row_widget(r))

    def row_widget(self, r: dict) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        check = QCheckBox(r["name"])
        check.setChecked(r["enabled"])
        check.setToolTip(r["command"])
        check.toggled.connect(lambda on, r=r: self.toggle(r, on))
        h.addWidget(check, 1)
        source = QLabel(SOURCE.get(r["scope"], r["scope"]))
        source.setObjectName("Muted")
        h.addWidget(source)
        if r["removable"]:
            rm = QPushButton("Remove")
            rm.clicked.connect(lambda _c=False, r=r: self.remove(r))
            h.addWidget(rm)
        return w

    def attempt(self, action, then_refresh=True):
        try:
            result = action()
        except (OSError, ValueError) as e:
            self.msg.setText(str(e))
            self.refresh()
            return
        self.msg.setText(result)
        if then_refresh:
            self.refresh()

    def toggle(self, r, on):
        self.attempt(lambda: sa.set_enabled(r, on))

    def remove(self, r):
        self.attempt(lambda: sa.remove(r))

    def add_app(self):
        app = pick_app(self.widget)
        if app:
            self.attempt(lambda: (sa.add_app(app), f"{app['name']} will start when you sign in")[1])

    def add_command(self):
        got = ask_command(self.widget)
        if got:
            name, command = got
            self.attempt(lambda: (sa.add_command(name, command), f"{name} will start when you sign in")[1])


def build() -> QWidget:
    page = Page()
    page.widget._page = page
    return page.widget
