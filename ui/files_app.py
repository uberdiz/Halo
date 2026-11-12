"""
ui/files_app.py

HalOS Files: the file manager. Places on the left (home folders, Windows' shared folders, drives), the folder in the
middle, a preview on the right, and one search box on top that understands plain words (core/file_index.py):
"the app for claude", "photos from last week", "tax pdf". Every change (new folder, rename, move to trash) is an OS
action (core/actions files.*), so it's logged and can be undone, here or by asking SAINT.

    python -m ui.files_app [folder]
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QDir, QModelIndex, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QFileSystemModel, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter,
                               QStackedWidget, QTreeView, QVBoxLayout, QWidget)

from core import actions
from core import file_index as fi

PREVIEW_TEXT = {".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".sh"}


def places() -> List[tuple]:
    """(label, path) of the left column: home folders that exist, then mounted drives."""
    home = Path.home()
    out = [("Home", home)]
    for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
        if (home / name).is_dir():
            out.append((name, home / name))
    try:
        from core import drives
        for v in drives.volumes():
            if v.mountpoint and v.mountpoint not in ("/", "/boot", "/boot/efi") and not v.is_esp:
                out.append((v.label or os.path.basename(v.mountpoint) or v.device, Path(v.mountpoint)))
    except Exception:
        pass
    return out


class _Bridge(QObject):
    indexed = Signal(int)


class FilesWindow(QMainWindow):
    def __init__(self, start: Optional[str] = None, index: Optional[fi.FileIndex] = None, roots=None, confirm=None):
        super().__init__()
        self.setWindowTitle("Files")
        self.resize(1180, 720)
        self.index = index or fi.FileIndex()
        self.roots = roots or [str(p) for _label, p in places()]
        self.confirm = confirm or self._ask
        self._bridge = _Bridge()
        self._bridge.indexed.connect(self._indexed)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        top = QHBoxLayout()
        self.back_btn = QPushButton("Up")
        self.back_btn.setToolTip("Up one folder (Backspace)")
        self.back_btn.clicked.connect(self.up)
        self.path_label = QLabel("")
        self.path_label.setObjectName("Muted")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search, or say what you're after: \"the app for claude\", \"photos from last week\"")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._search_soon)
        top.addWidget(self.back_btn)
        top.addWidget(self.path_label, 1)
        top.addWidget(self.search, 2)
        outer.addLayout(top)

        split = QSplitter()
        self.places = QListWidget()
        self.places.setMaximumWidth(220)
        for label, path in places():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(path))
            self.places.addItem(item)
        self.places.itemClicked.connect(lambda it: self.open_folder(it.data(Qt.UserRole)))
        split.addWidget(self.places)

        self.middle = QStackedWidget()
        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        self.model.setRootPath("")
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setSortingEnabled(True)
        self.tree.setColumnWidth(0, 360)
        self.tree.doubleClicked.connect(self._activate)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.selectionModel().currentChanged.connect(lambda cur, _prev: self.preview(self.model.filePath(cur)))
        self.results = QListWidget()
        self.results.itemActivated.connect(lambda it: self._open_hit(it.data(Qt.UserRole)))
        self.results.currentItemChanged.connect(lambda it, _p: it and self.preview(it.data(Qt.UserRole).path))
        self.middle.addWidget(self.tree)
        self.middle.addWidget(self.results)
        split.addWidget(self.middle)

        side = QWidget()
        sv = QVBoxLayout(side)
        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setMinimumHeight(200)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sv.addWidget(self.thumb)
        sv.addWidget(self.info)
        sv.addStretch(1)
        side.setMinimumWidth(260)
        split.addWidget(side)
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        outer.addWidget(self.status)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)                    # search as you type, without a query per keystroke
        self._timer.timeout.connect(self.run_search)
        for keys, fn in (("F2", self.rename), ("Delete", self.trash), ("Ctrl+Shift+N", self.new_folder),
                         ("Ctrl+F", self.search.setFocus), ("Ctrl+Z", self.undo), ("Backspace", self.up)):
            QShortcut(QKeySequence(keys), self, activated=fn)
        self.open_folder(start or str(Path.home()))
        self.reindex()

    # ------------------------------------------------------------------ browsing
    def open_folder(self, path: str):
        if not os.path.isdir(path):
            return
        self.current = path
        self.tree.setRootIndex(self.model.index(path))
        self.path_label.setText(path)
        self.middle.setCurrentWidget(self.tree)

    def up(self):
        if self.search.hasFocus() and self.search.text():
            return
        parent = os.path.dirname(self.current.rstrip("/\\"))
        if parent and parent != self.current:
            self.open_folder(parent)

    def _activate(self, index: QModelIndex):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self.open_folder(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def selected(self) -> Optional[str]:
        if self.middle.currentWidget() is self.results:
            it = self.results.currentItem()
            return it.data(Qt.UserRole).path if it else None
        idx = self.tree.currentIndex()
        return self.model.filePath(idx) if idx.isValid() else None

    # ------------------------------------------------------------------ search
    def reindex(self):
        def work():
            n = self.index.update(self.roots)
            self._bridge.indexed.emit(n)
        threading.Thread(target=work, daemon=True, name="files-index").start()
        self.status.setText("Updating the search index…")

    def _indexed(self, changed: int):
        self.status.setText(f"{self.index.count():,} files and folders indexed.")
        if self.search.text():
            self.run_search()

    def _search_soon(self, _text):
        self._timer.start()

    def run_search(self):
        text = self.search.text().strip()
        if not text:
            self.middle.setCurrentWidget(self.tree)
            return
        start = time.perf_counter()
        hits = self.index.search(text)
        ms = (time.perf_counter() - start) * 1000
        self.results.clear()
        for h in hits:
            where = h.detail if h.kind != "app" else f"App · {h.detail}" if h.detail else "App"
            item = QListWidgetItem(f"{h.title}\n{where}")
            item.setData(Qt.UserRole, h)
            self.results.addItem(item)
        if not hits:
            self.results.addItem(QListWidgetItem("Nothing found. Try fewer words, or a kind: \"pdf\", \"photos\"."))
        self.middle.setCurrentWidget(self.results)
        self.status.setText(f"{len(hits)} results in {ms:.0f} ms")

    def _open_hit(self, hit):
        if hit is None:
            return
        if hit.kind == "app" and hit.path.endswith(".desktop"):
            subprocess.Popen(["gtk-launch", os.path.basename(hit.path)[:-8]])
        elif hit.kind == "folder":
            self.search.clear()
            self.open_folder(hit.path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(hit.path))

    # ------------------------------------------------------------------ preview
    def preview(self, path: Optional[str]):
        self.thumb.clear()
        if not path or not os.path.exists(path):
            self.info.setText("")
            return
        st = os.stat(path)
        ext = os.path.splitext(path)[1].lower()
        kind = "Folder" if os.path.isdir(path) else fi.FileIndex._kind(ext, False).capitalize()
        size = "" if os.path.isdir(path) else f"{st.st_size / 1e6:.1f} MB" if st.st_size > 1e6 else f"{st.st_size / 1e3:.0f} KB"
        self.info.setText(f"<b>{os.path.basename(path)}</b><br>{kind} {size}<br>"
                          f"Changed {time.strftime('%d %b %Y %H:%M', time.localtime(st.st_mtime))}<br>"
                          f"<span style='color:gray'>{path}</span>")
        if ext in fi.KINDS["image"]:
            pix = QPixmap(path)
            if not pix.isNull():
                self.thumb.setPixmap(pix.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif ext in PREVIEW_TEXT and st.st_size < 200_000:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    self.thumb.setText(f.read(600))
                self.thumb.setWordWrap(True)
                self.thumb.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            except OSError:
                pass

    # ------------------------------------------------------------------ changes, through the action registry
    def _do(self, action_id: str, params: dict) -> bool:
        result = actions.execute(action_id, params, source="gui", confirm=self.confirm)
        self.status.setText(result.text + ("  (Ctrl+Z to undo)" if result.ok and result.undo is not None else ""))
        return result.ok

    def new_folder(self):
        name, ok = QInputDialog.getText(self, "New folder", "Name:")
        if ok and name.strip():
            self._do("files.new_folder", {"in": self.current, "name": name.strip()})

    def rename(self):
        path = self.selected()
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=os.path.basename(path))
        if ok and name.strip() and name.strip() != os.path.basename(path):
            self._do("files.rename", {"path": path, "name": name.strip()})

    def trash(self):
        path = self.selected()
        if path:
            self._do("files.trash", {"path": path})

    def undo(self):
        result = actions.undo_last(source="gui")
        self.status.setText(result.text)

    def _menu(self, pos):
        path = self.selected()
        menu = QMenu(self)
        menu.addAction("New folder", self.new_folder)
        if path:
            menu.addAction("Rename", self.rename)
            menu.addAction("Move to trash", self.trash)
            menu.addAction("Ask SAINT about this…", lambda: self._ask_saint(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    @staticmethod
    def _ask_saint(path: str):
        subprocess.Popen(["saint", "--ask", f"Tell me about the file {path}"])

    def _ask(self, request) -> bool:
        return QMessageBox.question(self, request.title, request.preview) == QMessageBox.Yes


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Files")
    app.setDesktopFileName("halos-files")
    try:
        from ui import theme
        app.setStyleSheet(theme.build_stylesheet())
    except Exception:
        pass
    w = FilesWindow(argv[0] if argv else None)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
