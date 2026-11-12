"""Page "Downloads": everything downloading or updating on this PC (core/downloads.py), refreshed every 2 seconds
while the page is open and not at all otherwise."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from core import downloads
from ui.widgets import Page, clear_layout, run_async

TITLE = "Downloads"
ICON = "download"
ORDER = 22
GROUP = "SAINT"
REFRESH_MS = 2000


class DownloadsPage(Page):
    def __init__(self, source=None):
        super().__init__(TITLE, "Everything downloading or updating on this PC: apps, AI models, games and browser "
                                "downloads.", scroll=True)
        self._source = source or downloads.snapshot
        self.empty = QLabel("Nothing is downloading right now.")
        self.empty.setObjectName("Muted")
        self.root.addWidget(self.empty)
        self.list = QVBoxLayout()
        self.root.addLayout(self.list)
        self.root.addStretch(1)
        self.timer = QTimer(self)
        self.timer.setInterval(REFRESH_MS)
        self.timer.timeout.connect(self.refresh)
        self._busy = False

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        run_async(self._source, self.show_items, lambda _e: setattr(self, "_busy", False))

    def show_items(self, items):
        self._busy = False
        clear_layout(self.list)
        self.empty.setVisible(not items)
        for item in items:
            row = QWidget()
            lay = QVBoxLayout(row)
            lay.setContentsMargins(0, 6, 0, 6)
            top = QHBoxLayout()
            name = QLabel(f"<b>{item.name}</b>")
            source = QLabel(item.source)
            source.setObjectName("Muted")
            top.addWidget(name, 1)
            top.addWidget(source)
            lay.addLayout(top)
            bar = QProgressBar()
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            if item.percent is None:
                bar.setRange(0, 0 if item.state == "downloading" else 1)   # moving when size unknown
            else:
                bar.setRange(0, 100)
                bar.setValue(item.percent)
            lay.addWidget(bar)
            detail = QLabel(item.text())
            detail.setObjectName("Muted")
            lay.addWidget(detail)
            self.list.addWidget(row)


def build():
    return DownloadsPage()
