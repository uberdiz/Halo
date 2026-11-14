"""
ui/os_notes.py

Meta+N: jot down something about HalOS for the agent to fix or add. A small window (one text box, Save with
Ctrl+Enter, Esc to close) appends the note as an open task to "OS notes.md" in SAINT Vault (core/vault.py),
where every Claude Code run SAINT starts (Evolve, agent mode) can read it and tick it off when done.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

NOTES_FILE = "OS notes.md"
HEADER = ("# OS notes\n\nThings to fix or add in HalOS, written with Meta+N. Agents: work through the open items "
          "(`- [ ]`), tick them (`- [x]`) when done and add a short line on what changed. Don't delete notes.\n\n")
KINDS = ("Fix", "Add", "Idea")


def notes_path(root: Optional[Path] = None) -> Path:
    from core import vault
    return (root or vault.path()) / NOTES_FILE


def add_note(text: str, kind: str = "Fix", root: Optional[Path] = None, now: Optional[datetime] = None) -> Path:
    """Append one note as an open task. Multi-line text stays one item (continuation lines indented)."""
    text = "\n".join(l.rstrip() for l in str(text).strip().splitlines() if l.strip())
    if not text:
        raise ValueError("empty note")
    kind = kind if kind in KINDS else "Fix"
    p = notes_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    first, *rest = text.splitlines()
    item = f"- [ ] **{kind}** ({stamp}) {first}\n" + "".join(f"  {l}\n" for l in rest)
    with open(p, "a", encoding="utf-8") as f:
        if f.tell() == 0:
            f.write(HEADER)
        f.write(item)
    return p


def open_items(root: Optional[Path] = None) -> list:
    p = notes_path(root)
    if not p.exists():
        return []
    return [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ]")]


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                                   QVBoxLayout, QWidget)
    app = QApplication(sys.argv)
    app.setApplicationName("halos-note")
    app.setDesktopFileName("halos-note")
    try:
        import os
        from core.config import config
        from ui import theme
        a = config.get("appearance", {}) or {}
        app.setPalette(theme.qt_palette(theme.current_palette()))
        app.setStyleSheet(theme.build_stylesheet(a.get("theme", "Dark"), a.get("accent", "#feaa34"),
                                                 a.get("font_family", "Noto Sans" if os.name != "nt" else "Segoe UI"),
                                                 a.get("font_size", 13)))
    except Exception:                                   # unthemed beats not opening
        pass
    w = QWidget()
    w.setWindowTitle("Note for SAINT")
    w.resize(460, 220)
    lay = QVBoxLayout(w)
    head = QHBoxLayout()
    title = QLabel("What should SAINT fix or add in HalOS?")
    title.setObjectName("CardTitle")
    kind = QComboBox()
    kind.addItems(KINDS)
    head.addWidget(title, 1)
    head.addWidget(kind)
    lay.addLayout(head)
    box = QPlainTextEdit()
    box.setPlaceholderText("e.g. The volume slider jumps when I scroll it")
    lay.addWidget(box, 1)
    hint = QLabel(f"Saved to SAINT Vault › {NOTES_FILE} · {len(open_items())} open")
    hint.setObjectName("Hint")
    row = QHBoxLayout()
    row.addWidget(hint, 1)
    save = QPushButton("Save  (Ctrl+Enter)")
    save.setObjectName("Primary")
    row.addWidget(save)
    lay.addLayout(row)

    def do_save():
        try:
            add_note(box.toPlainText(), kind.currentText())
        except ValueError:
            box.setFocus()
            return
        except OSError as e:
            hint.setText(f"Couldn't save: {e}")
            return
        w.close()

    save.clicked.connect(do_save)
    QShortcut(QKeySequence("Ctrl+Return"), w, do_save)
    QShortcut(QKeySequence("Ctrl+Enter"), w, do_save)
    QShortcut(QKeySequence(Qt.Key_Escape), w, w.close)
    w.show()
    w.raise_()
    w.activateWindow()
    box.setFocus()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
