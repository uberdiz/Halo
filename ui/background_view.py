"""
ui/background_view.py

"Show me": a small live view of SAINT's background desktop (core/background_session.py), refreshed twice a second
while it's open. Look only: clicks and typing here never reach the background desktop or your own.

    python -m ui.background_view
"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from core.background_session import BackgroundError, shared


class BackgroundView(QWidget):
    def __init__(self, desktop=None):
        super().__init__()
        self.desktop = desktop or shared()
        self.setWindowTitle("SAINT's background desktop")
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(800, 470)
        lay = QVBoxLayout(self)
        self.view = QLabel("Nothing is running in the background.")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(320, 180)
        lay.addWidget(self.view, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def refresh(self):
        if not self.desktop.running:
            self.view.setText("Nothing is running in the background.")
            return
        try:
            img = self.desktop.screenshot().convert("RGB")
        except (BackgroundError, OSError) as e:
            self.view.setText(f"Can't see the background desktop: {e}")
            return
        q = QImage(img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888)
        self.view.setPixmap(QPixmap.fromImage(q).scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    w = BackgroundView()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
