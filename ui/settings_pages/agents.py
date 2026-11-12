"""Settings page "AI agents": which agents and models suit this PC (core/agent_catalog.py), installed in one click,
and models already downloaded on Windows copied over instead of downloaded again."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core import agent_catalog as ac
from ui.widgets import Page, chip, run_async, set_button_state

TITLE = "AI agents"
ICON = "sparkles"
ORDER = 21
GROUP = "SAINT"


class Row(QWidget):
    def __init__(self, r: ac.Rating, on_install):
        super().__init__()
        self.rating = r
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(f"<b>{r.name}</b>" + (f"  ·  {r.size_gb:.1f} GB" if r.kind == "local" else "  ·  cloud"))
        good = QLabel(r.good_for)
        good.setWordWrap(True)
        why = QLabel(r.reason)
        why.setObjectName("Muted")
        why.setWordWrap(True)
        for w in (name, good, why):
            col.addWidget(w)
        lay.addLayout(col, 1)
        self.badge = chip(ac.STATUS_LABEL[r.status], {ac.RECOMMENDED: "ok", ac.TOO_HEAVY: "warn"}.get(r.status, ""))
        lay.addWidget(self.badge, 0, Qt.AlignTop)
        self.button = QPushButton("Installed" if r.installed else "Install")
        self.button.setObjectName("Primary" if r.status == ac.RECOMMENDED and not r.installed else "")
        self.button.setEnabled(not r.installed and r.status != ac.TOO_HEAVY)
        self.button.clicked.connect(lambda: on_install(self))
        lay.addWidget(self.button, 0, Qt.AlignTop)


class AgentsPage(Page):
    def __init__(self, detect=None, installed=None, stores=None):
        super().__init__(TITLE, "Agents and models matched to this PC. Claude Code is SAINT's main agent; local models "
                                "work offline.", scroll=True)
        self._detect = detect or (lambda: ac.dp.detect())
        self._installed = installed or ac.installed_ids
        self._stores = stores or ac.windows_model_stores
        self.summary = QLabel("Checking this PC…")
        self.summary.setObjectName("Muted")
        self.summary.setWordWrap(True)
        self.root.addWidget(self.summary)
        self.list = QVBoxLayout()
        self.root.addLayout(self.list)
        self.reuse = QWidget()
        self.reuse.hide()
        self.root.addWidget(self.reuse)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)
        self.root.addStretch(1)
        self.rows = []
        run_async(lambda: (self._detect(), self._installed(), self._stores()), self.show_ratings,
                  lambda e: self.summary.setText(f"Couldn't check this PC: {e}"))

    def show_ratings(self, found):
        hw, have, stores = found
        ratings = ac.rate(hw, installed=have)
        gpu = f"{hw.gpu_name} ({hw.vram_gb:.0f} GB)" if hw.gpu_name else "no NVIDIA GPU"
        self.summary.setText(f"This PC: {hw.ram_gb:.0f} GB of RAM, {gpu}, {hw.disk_free_gb:.0f} GB free.")
        for r in ratings:
            row = Row(r, self._install)
            self.rows.append(row)
            self.list.addWidget(row)
        if stores:
            self._offer_reuse(stores[0])

    def _offer_reuse(self, store):
        lay = QHBoxLayout(self.reuse)
        lay.setContentsMargins(0, 8, 0, 0)
        text = QLabel(f"Found {len(store['models'])} models ({store['size_gb']:.1f} GB) on your Windows disk: "
                      f"{', '.join(store['models'][:4])}. Copy them instead of downloading again?")
        text.setWordWrap(True)
        go = QPushButton("Copy from Windows")
        go.clicked.connect(lambda: self._reuse(store, go))
        lay.addWidget(text, 1)
        lay.addWidget(go)
        self.reuse.show()

    def _reuse(self, store, button):
        from core import pkg_queue
        set_button_state(button, "busy", "Copying…")
        run_async(lambda: pkg_queue.run_plan(ac.reuse_steps(store["path"]), on_line=lambda _l: None),
                  lambda res: set_button_state(button, "done" if all(res.values()) else "failed",
                                               "Copied" if all(res.values()) else "Didn't copy"),
                  lambda e: (set_button_state(button, "failed", "Didn't copy"), self.status.setText(str(e))))

    def _install(self, row: Row):
        set_button_state(row.button, "busy", "Installing…")
        res = ac.install(row.rating.id)
        self.status.setText(res["message"])
        if not res["ok"]:
            set_button_state(row.button, "failed", "Try again", revert_ms=2500)


def build():
    return AgentsPage()
