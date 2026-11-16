"""
ui/note_popup.py

The "Note to fix" box (core/fix_notes.py). In SAINT's own windows it opens from any right-click (ui/note_hook.py);
anywhere else from Meta+N or Dolphin's right-click menu, as its own process:

    python -m ui.note_popup --region               drag over what to show (Meta+N), then the box
    python -m ui.note_popup --active               screenshot of the window in front, then the box
    python -m ui.note_popup --where FILE           a file right-clicked in Dolphin
"""

import argparse
import os
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout)


class NoteDialog(QDialog):
    def __init__(self, where: str = "", details: str = "", shot: str = "", parent=None):
        super().__init__(parent)
        self.where, self.details, self.shot = where, details, shot
        self.setWindowTitle("Note to fix")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        head = QLabel("<b>What should be fixed?</b>" + (f"<br><span style='color:gray'>{where[:160]}</span>" if where else ""))
        head.setWordWrap(True)
        v.addWidget(head)
        if shot and os.path.isfile(shot):
            pic = QLabel()
            pic.setPixmap(QPixmap(shot).scaledToWidth(440, Qt.SmoothTransformation))
            v.addWidget(pic)
        self.box = QPlainTextEdit()
        self.box.setPlaceholderText("e.g. this button does nothing · the text is cut off · should remember my choice")
        self.box.setMaximumHeight(120)
        v.addWidget(self.box)
        self.same = QVBoxLayout()               # notes that already say this: add to one instead of repeating it
        v.addLayout(self.same)
        self.box.textChanged.connect(self._similar)
        row = QHBoxLayout()
        self.status = QLabel("Saved to SAINT Vault › Fix. Evolve › Fix my notes sends them to Claude Code.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: gray; font-size: 11px")
        row.addWidget(self.status, 1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save note")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        v.addLayout(row)
        self.box.setFocus()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ControlModifier:
            return self._save()
        super().keyPressEvent(e)

    def _similar(self):
        from core import fix_notes
        while self.same.count():
            w = self.same.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for n in fix_notes.similar(self.box.toPlainText(), n=2):
            b = QPushButton("Add to: " + " ".join(n.text.split())[:70])
            b.setToolTip("You already noted this. Adds what you typed to that note instead of making a new one.")
            b.clicked.connect(lambda _=False, n=n: self._add_to(n))
            self.same.addWidget(b)

    def _add_to(self, note):
        from core import fix_notes
        try:
            fix_notes.append(note, self.box.toPlainText())
        except Exception as e:
            return self.status.setText(str(e))
        self.accept()

    def _save(self):
        from core import fix_notes
        try:
            fix_notes.add(self.box.toPlainText(), self.where, self.details, self.shot or None)
        except Exception as e:
            self.status.setText(str(e))
            return
        self.accept()


def _shot(mode: str = "-a", timeout: float = 8) -> str:
    """A screenshot before our box covers it (spectacle works on Wayland): -a the window in front, -r a region you
    drag (Esc: none), -f every screen."""
    out = os.path.join(tempfile.gettempdir(), f"halos-note-{os.getpid()}.png")
    try:
        subprocess.run(["spectacle", mode, "-b", "-n", "-o", out], timeout=timeout, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out if os.path.isfile(out) and os.path.getsize(out) else ""


def _active_window_shot() -> str:
    return _shot("-a")


def _active_title() -> str:
    try:
        r = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--active", action="store_true")
    ap.add_argument("--region", action="store_true", help="drag over what to show, like a screenshot")
    ap.add_argument("--where", default="")
    ap.add_argument("--details", default="")
    a = ap.parse_args(argv)
    where, shot = a.where, ""
    if a.region:
        shot = _shot("-r", timeout=300)                 # you take your time dragging
        where = where or "A part of the screen (Meta+N)"
    elif a.active:
        title = _active_title()
        shot = _active_window_shot()
        where = where or (f"Window: {title}" if title else "The window in front")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("HalOS Note")
    app.setDesktopFileName("halos-note")
    from ui.taskmanager import apply_style
    apply_style(app)
    d = NoteDialog(where, a.details, shot)
    d.show()
    d.raise_()
    d.activateWindow()
    return 0 if d.exec() else 1


if __name__ == "__main__":
    sys.exit(main())
