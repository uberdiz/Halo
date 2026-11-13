"""Page "Downloads": everything downloading or updating on this PC (core/downloads.py) as progress cards with speed
and time left, refreshed every 2 seconds while the page is open and not at all otherwise. Cards are updated in
place (no flicker); new ones fade in."""

import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from core import downloads
from ui import motion
from ui.widgets import Page, chip, run_async

TITLE = "Downloads"
ICON = "download"
ORDER = 22
GROUP = "SAINT"
REFRESH_MS = 2000


class DownloadCard(QFrame):
    def __init__(self, item):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.name = QLabel()
        self.name.setStyleSheet("font-weight: 600;")
        self.source = chip(item.source)
        self.pct = QLabel()
        self.pct.setObjectName("ReadoutSmall")
        top.addWidget(self.name, 1)
        top.addWidget(self.source)
        top.addWidget(self.pct)
        lay.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        self.detail = QLabel()
        self.detail.setObjectName("Muted")
        lay.addWidget(self.detail)
        self.update_item(item)

    def update_item(self, item):
        self.name.setText(item.name)
        pct = item.percent
        self.pct.setText("" if pct is None else f"{pct}%")
        if pct is None:
            self.bar.setRange(0, 0 if item.state == "downloading" else 1)   # moving when the size is unknown
        else:
            if self.bar.maximum() != 100:
                self.bar.setRange(0, 100)
            motion.animate(self.bar, b"value", self.bar.value(), pct, motion.SLOW)
        bits = []
        if item.total:
            bits.append(f"{item.done / 1e6:,.0f} of {item.total / 1e6:,.0f} MB")
        elif item.done:
            bits.append(f"{item.done / 1e6:,.0f} MB so far")
        if item.speed > 0:
            bits.append(f"{item.speed / 1e6:.1f} MB/s")
        left = downloads.fmt_eta(item.eta)
        if left:
            bits.append(left)
        if item.state != "downloading":
            bits.append(item.state)
        self.detail.setText("  ·  ".join(bits) or "Working…")


class DownloadsPage(Page):
    def __init__(self, source=None):
        super().__init__(TITLE, "Everything downloading or updating on this PC: apps, AI models, games, browser "
                                "downloads and Visual Shop items.", scroll=True)
        self._source = source or downloads.snapshot
        folder = QPushButton("Open Downloads folder")
        folder.clicked.connect(self._open_folder)
        self.actions.addWidget(folder)
        self.empty = QLabel("Nothing is downloading right now.")
        self.empty.setObjectName("Muted")
        self.root.addWidget(self.empty)
        self.list = QVBoxLayout()
        self.list.setSpacing(10)
        self.root.addLayout(self.list)
        self.root.addStretch(1)
        self.cards = {}
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
        keys = [i.key for i in items]
        for key in [k for k in self.cards if k not in keys]:
            card = self.cards.pop(key)
            self.list.removeWidget(card)
            card.deleteLater()
        for i, item in enumerate(items):
            card = self.cards.get(item.key)
            if card is None:
                card = self.cards[item.key] = DownloadCard(item)
                self.list.insertWidget(i, card)
                motion.fade_in(card, motion.BASE, dy=6)
            else:
                card.update_item(item)
        self.empty.setVisible(not items)

    @staticmethod
    def _open_folder():
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        dirs = downloads.download_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(dirs[0] if dirs else os.path.expanduser("~"))))


def build():
    return DownloadsPage()
