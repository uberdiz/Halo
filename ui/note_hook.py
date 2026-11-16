"""
ui/note_hook.py

Right-click anything in a SAINT window -> "Note to fix this…" (core/fix_notes.py). One event filter per app:
a menu that opens from a right-click gets the item added at the bottom; a right-click on something with no menu
of its own (a label, a button, a list) gets a small menu with just the item.

    install(app)
"""

import time

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu, QWidget

_TAG = "_halos_note"


def describe(w: QWidget) -> tuple:
    """(where, details) for the widget under the cursor: its window, its own text, and its parents."""
    win = w.window()
    title = win.windowTitle() or type(win).__name__
    chain, x = [], w
    while x is not None and len(chain) < 6:
        bit = type(x).__name__
        name = x.objectName()
        text = ""
        for attr in ("text", "title", "placeholderText", "toolTip"):
            fn = getattr(x, attr, None)
            if callable(fn):
                try:
                    t = fn()
                except TypeError:
                    continue
                if isinstance(t, str) and t.strip():
                    text = t.strip().splitlines()[0][:80]
                    break
        chain.append(bit + (f"#{name}" if name else "") + (f" “{text}”" if text else ""))
        x = x.parentWidget()
    app = QApplication.applicationName() or "SAINT"
    return f"{app} › {title} › {chain[0]}", "\n".join(chain)


class _Hook(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.target = None
        self.menu_seen = False
        self.pressed = 0.0

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.MouseButtonPress and ev.button() == Qt.RightButton and isinstance(obj, QWidget) \
                and not isinstance(obj, QMenu) and time.monotonic() - self.pressed > 0.1:
            # the deepest widget sees the press first; parents get the same press if it's ignored: keep the first
            self.target, self.menu_seen, self.pressed = obj, False, time.monotonic()
            QTimer.singleShot(250, self._no_menu)
        elif t == QEvent.Show and isinstance(obj, QMenu) and self.target is not None and not obj.property(_TAG) \
                and time.monotonic() - self.pressed < 1.0:
            self.menu_seen = True
            obj.setProperty(_TAG, True)
            obj.addSeparator()
            target = self.target
            obj.addAction("📝  Note to fix this…", lambda: open_note(target))
        return False

    def _no_menu(self):
        """Nothing opened a menu for that right-click: offer ours."""
        if self.menu_seen or self.target is None:
            return
        target, self.target = self.target, None
        try:
            target.window()
        except RuntimeError:            # deleted meanwhile
            return
        m = QMenu(target)
        m.setProperty(_TAG, True)
        m.addAction("📝  Note to fix this…", lambda: open_note(target))
        m.popup(QCursor.pos())


def open_note(w: QWidget):
    import os
    import tempfile
    from ui.note_popup import NoteDialog
    try:
        where, details = describe(w)
        shot = os.path.join(tempfile.gettempdir(), f"halos-note-{os.getpid()}.png")
        w.window().grab().save(shot, "PNG")
    except RuntimeError:
        return
    d = NoteDialog(where, details, shot, w.window())
    d.setAttribute(Qt.WA_DeleteOnClose)
    d.show()


def install(app):
    """Once per QApplication; harmless if called twice."""
    if app is None or app.property(_TAG):
        return
    app.setProperty(_TAG, True)
    hook = _Hook(app)
    app.installEventFilter(hook)
    app._halos_note_hook = hook
