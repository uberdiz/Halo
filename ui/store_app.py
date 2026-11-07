"""
ui/store_app.py

SAINT Store as its own app (`saint-store`): a window of its own, under its own icon, in SAINT's theme. It's a small
process that loads no voice or AI, so it opens fast and works when SAINT is busy or stopped. One Store per user:
a second `saint-store` brings the first forward, with its search if it was given one.

    saint-store                     open the Store
    saint-store blender             open it searching for that
    saint-store appstream://org.x   the same, from a link to an app (other programs' "get this app" links)

Closing the window during an install keeps the install running; the process ends when the queue does.
"""

import os
import sys

if __package__ in (None, ""):                         # run as a script: /opt/saint/app/ui/store_app.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

INSTANCE = "store"                                    # core/instance.py: this app's own channel


def query_from(args) -> str:
    """What the command line asks to see: words, or the id in an appstream:// link. Options are ignored."""
    words = [a for a in args if a and not a.startswith("-")]
    return " ".join(w.split("://", 1)[-1].strip("/") if w.startswith("appstream:") else w for w in words)[:64]


class StoreWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from ui import icons
        from ui.pages.store import StorePage
        from ui.theme import current_palette
        self.setWindowTitle("SAINT Store")
        icons.set_window_icon(self, QIcon.fromTheme("saint-store", icons.icon("download", current_palette().accent, 64)))
        self.resize(1280, 860)
        self.setMinimumSize(720, 520)
        self.page = StorePage(self)
        self.setCentralWidget(self.page)

    def handle_command(self, cmd: str):
        """From another `saint-store` (core/instance.py): come forward, and search if asked."""
        if cmd.startswith("ask:"):
            self.page.open_query(cmd[4:])
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if self.page.busy():                          # an install keeps going; the window goes away
            e.ignore()
            self.hide()
            self.page.idle.connect(QApplication.instance().quit)
            return
        super().closeEvent(e)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("SAINT Store")
    app.setApplicationDisplayName("SAINT Store")
    # Wayland app id = saint-store.desktop: its windows group under the Store's own icon, not SAINT's.
    app.setDesktopFileName("saint-store")
    from core import instance
    query = query_from(args)
    if instance.send(f"ask:{query}" if query else "show", name=INSTANCE):
        return 0
    from ui.taskmanager import apply_style
    apply_style(app)
    win = StoreWindow()
    server = instance.Server(app, name=INSTANCE)
    server.command.connect(win.handle_command)
    if query:
        win.page.open_query(query)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
