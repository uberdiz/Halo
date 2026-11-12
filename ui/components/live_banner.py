"""
ui/components/live_banner.py

The live session's banner, on Storage and Overview: everything here is in RAM and HalOS isn't installed yet, with
the button that installs it. Invisible on an installed system.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core import drives
from ui.theme import current_palette
from ui.widgets import run_async


class LiveBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LiveBanner")
        p = current_palette()
        self.setStyleSheet(f"QFrame#LiveBanner {{ border: 2px solid {p.warning}; border-radius: 10px; }}")
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(4)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {p.warning};")
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("Muted")
        text.addWidget(self.message)
        text.addWidget(self.hint)
        row.addLayout(text, 1)
        self.install_btn = QPushButton("Install HalOS")
        self.install_btn.setObjectName("Primary")
        self.install_btn.clicked.connect(self._install)
        row.addWidget(self.install_btn)
        self.hide()
        if drives.is_live():
            self.refresh()

    def refresh(self):
        run_async(drives.live_status, self.show_status)

    def show_status(self, status: drives.LiveStatus):
        self.setVisible(status.live)
        if status.live:
            self.message.setText(status.message)
            self.hint.setText(status.install_hint)

    def _install(self):
        error = drives.launch_installer()
        if error:
            self.hint.setText(error)
