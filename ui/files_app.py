"""
ui/files_app.py

HalOS Files: the file manager. Tabs (Ctrl+T / Ctrl+W / Ctrl+Tab, drag to reorder, middle-click to close), back /
forward / up and a breadcrumb you can click or type a path into, a sidebar with Quick access and every drive (with
how full it is; click an unmounted one to mount it), Details / List / Icons views, folder sizes worked out in the
background, a preview on the right (Space for a big quick look) and one search box on top that understands plain
words (core/file_index.py): "the app for claude", "photos from last week", "tax pdf".

Every change (new folder, rename, move to trash, paste, drag and drop) is an OS action (core/actions files.*), so
it's logged and can be undone, here or by asking SAINT.

    python -m ui.files_app [folder]
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from PySide6.QtCore import (QDir, QEvent, QMimeData, QModelIndex, QObject, QRectF, QRunnable, QSize, Qt, QThreadPool,
                            QTimer, QUrl, Signal)
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFileSystemModel, QFrame, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
                               QMenu, QMessageBox, QPushButton, QSplitter, QStackedWidget, QStyledItemDelegate,
                               QTabWidget, QToolButton, QTreeView, QVBoxLayout, QWidget)

from core import actions
from core import file_index as fi

PREVIEW_TEXT = {".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".sh"}
VIEWS = ("Details", "List", "Icons")
DRIVE_REFRESH_MS = 5000
SIZE_TTL_S = 300                      # a folder's size is reused this long unless the folder itself changed
NO_SIZE = {"/proc", "/sys", "/dev", "/run"}     # virtual filesystems: nothing to add up
USED_ROLE, DRIVE_ROLE = Qt.UserRole + 1, Qt.UserRole + 2


# --------------------------------------------------------------------------- plain helpers (tested)
def places() -> List[tuple]:
    """(label, path) of the home folders that exist, then mounted drives (search roots)."""
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


def human_size(n: Optional[float]) -> str:
    if n is None:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def breadcrumbs(path: str, home: Optional[str] = None) -> List[Tuple[str, str]]:
    """[(label, full path)] from the root (or Home, when inside it) down to ``path``."""
    p = Path(path)
    home_p = Path(home) if home else Path.home()
    try:
        rest = p.relative_to(home_p).parts
        out, cur = [("Home", str(home_p))], home_p
    except ValueError:
        anchor = p.anchor or "/"
        out, cur = [(anchor.rstrip("\\/") or "/", anchor)], Path(anchor)
        rest = p.parts[1:]
    for part in rest:
        cur = cur / part
        out.append((part, str(cur)))
    return out


def _url_path(url: str) -> str:
    p = unquote(urlparse(url).path)
    return p[1:] if os.name == "nt" and len(p) > 2 and p[0] == "/" and p[2] == ":" else p


def parse_location(text: str, cwd: str) -> Tuple[Optional[str], Optional[str]]:
    """What a typed location means: (folder to open, file to select in it). ~, $VARS, file:// URLs and paths
    relative to the open folder work. (None, None) when it doesn't exist."""
    t = text.strip().strip('"')
    if not t:
        return None, None
    if t.startswith("file://"):
        t = _url_path(t)
    t = os.path.expandvars(os.path.expanduser(t))
    p = Path(t) if os.path.isabs(t) else Path(cwd) / t
    try:
        p = p.resolve()
    except OSError:
        return None, None
    if p.is_dir():
        return str(p), None
    if p.exists():
        return str(p.parent), str(p)
    return None, None


def recent_files(xbel: Optional[str] = None, limit: int = 60) -> List[str]:
    """Recently used files (freedesktop recently-used.xbel, what Plasma and GTK apps record), newest first, only
    those that still exist."""
    import xml.etree.ElementTree as ET
    path = xbel or os.path.expanduser("~/.local/share/recently-used.xbel")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    seen = []
    for b in root.iter("bookmark"):
        href = b.get("href", "")
        if href.startswith("file://"):
            seen.append((b.get("modified") or b.get("visited") or "", _url_path(href)))
    out = []
    for _when, p in sorted(seen, reverse=True):
        if p not in out and os.path.isfile(p):
            out.append(p)
    return out[:limit]


def folder_size(path: str, stop: Optional[threading.Event] = None) -> int:
    """Bytes in a folder and everything under it; symlinks aren't followed and other filesystems aren't entered."""
    total = 0
    try:
        dev = os.stat(path).st_dev
    except OSError:
        return 0
    stack = [path]
    while stack and not (stop and stop.is_set()):
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        st = e.stat(follow_symlinks=False)
                        if e.is_dir(follow_symlinks=False):
                            if st.st_dev in (dev, 0):          # 0: Windows' scandir doesn't fill it in
                                stack.append(e.path)
                        else:
                            total += st.st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def drive_entries(vols) -> List[Dict]:
    """Sidebar rows for core/drives volumes: every drive you'd use (not EFI / recovery / the live medium)."""
    out = []
    for v in vols:
        if v.protected:
            continue
        root = v.mountpoint == "/"
        icon = "drive-removable-media-usb" if v.removable else "drive-harddisk"
        label = "HalOS (this drive)" if root else v.name
        out.append({"label": label, "path": v.mountpoint, "size": v.size, "free": v.free if v.mountpoint else None,
                    "icon": icon, "volume": v, "locked": v.locked})
    return out


def _windows_drive_entries() -> List[Dict]:
    from PySide6.QtCore import QStorageInfo
    out = []
    for s in QStorageInfo.mountedVolumes():
        if s.isValid() and s.isReady():
            out.append({"label": f"{s.displayName() or 'Local disk'} ({s.rootPath().rstrip('/')})",
                        "path": s.rootPath(), "size": s.bytesTotal(), "free": s.bytesAvailable(),
                        "icon": "drive-harddisk", "volume": None, "locked": False})
    return out


def list_drives() -> List[Dict]:
    if os.name == "nt":
        return _windows_drive_entries()
    from core import drives
    return drive_entries(drives.volumes())


def theme_icon(name: str, fallback: str) -> QIcon:
    """The HalOS icon theme's icon when the desktop has it, else SAINT's own line icon."""
    ic = QIcon.fromTheme(name)
    if ic.isNull():
        from ui import icons
        from ui.theme import current_palette
        ic = icons.icon(fallback, current_palette().muted, 18)
    return ic


# --------------------------------------------------------------------------- folder sizes, off the GUI thread
class _SizeJob(QRunnable):
    def __init__(self, owner, path):
        super().__init__()
        self.owner, self.path = owner, path

    def run(self):
        try:
            size = self.owner.walk(self.path, self.owner.stop)
        except Exception:
            size = None
        self.owner._finished.emit(self.path, size)


class FolderSizes(QObject):
    """Folder sizes worked out on a small thread pool and cached: ``get(path)`` answers at once (None while it's
    being added up, or the last size while it's refreshed) and ``ready(path, size)`` follows when it's done."""
    ready = Signal(str, object)
    _finished = Signal(str, object)

    def __init__(self, walk=folder_size, clock=time.monotonic, threads: int = 2):
        super().__init__()
        self.walk, self.clock = walk, clock
        self.cache: Dict[str, Tuple[int, float, int]] = {}      # path -> (folder mtime_ns, when, bytes)
        self.pending = set()
        self.stop = threading.Event()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(threads)                   # don't swamp the disk the user is browsing
        self._finished.connect(self._store)

    def get(self, path: str) -> Optional[int]:
        if path in NO_SIZE:
            return None
        try:
            mtime = os.stat(path).st_mtime_ns
        except OSError:
            return None
        hit = self.cache.get(path)
        # ponytail: a folder's mtime only changes with its direct children, so deep changes show after SIZE_TTL_S
        if hit and hit[0] == mtime and self.clock() - hit[1] < SIZE_TTL_S:
            return hit[2]
        if path not in self.pending:
            self.pending.add(path)
            self.pool.start(_SizeJob(self, path))
        return hit[2] if hit else None

    def _store(self, path, size):
        self.pending.discard(path)
        if size is None:
            return
        try:
            self.cache[path] = (os.stat(path).st_mtime_ns, self.clock(), size)
        except OSError:
            return
        self.ready.emit(path, size)

    def shutdown(self):
        self.stop.set()
        self.pool.clear()


class FilesModel(QFileSystemModel):
    """QFileSystemModel that shows folder sizes (from FolderSizes) in the Size column."""

    def __init__(self, sizes: FolderSizes, parent=None):
        super().__init__(parent)
        self.sizes = sizes
        sizes.ready.connect(self._size_ready)

    def data(self, index, role=Qt.DisplayRole):
        if index.column() == 1 and role == Qt.DisplayRole and self.isDir(index):
            n = self.sizes.get(self.filePath(index))
            return "…" if n is None else human_size(n)
        return super().data(index, role)

    def _size_ready(self, path, _size):
        idx = self.index(path, 1)
        if idx.isValid():
            self.dataChanged.emit(idx, idx, [Qt.DisplayRole])


# --------------------------------------------------------------------------- views
class _ViewMixin:
    """Shared by the Details and List/Icons views: drops (move or copy through the actions), Space for quick look,
    the mouse's back/forward buttons."""
    tab = None

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else super().dragMoveEvent(e)

    def dropEvent(self, e):
        if not e.mimeData().hasUrls():
            return super().dropEvent(e)
        idx = self.indexAt(e.position().toPoint())
        target = self.model().filePath(idx) if idx.isValid() and self.model().isDir(idx) else self.tab.path
        self.tab.window_.drop([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()], target,
                              copy=bool(e.modifiers() & Qt.ControlModifier))
        e.setDropAction(Qt.CopyAction)            # the actions did the move: the source view must not remove rows
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not e.modifiers():
            self.tab.window_.quick_look()
            return
        super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.BackButton:
            self.tab.back()
        elif e.button() == Qt.ForwardButton:
            self.tab.forward()
        else:
            super().mousePressEvent(e)


class DetailsView(_ViewMixin, QTreeView):
    pass


class ItemsView(_ViewMixin, QListView):
    pass


def _setup_view(view, model, tab):
    from ui import motion
    view.tab = tab
    view.setModel(model)
    view.setDragEnabled(True)
    view.setAcceptDrops(True)
    view.setDropIndicatorShown(True)
    view.setDragDropMode(QAbstractItemView.DragDrop)
    view.setDefaultDropAction(Qt.MoveAction)
    view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    view.setContextMenuPolicy(Qt.CustomContextMenu)
    view.setObjectName("FilesView")
    motion.smooth_scroll(view)
    return view


class FolderTab(QWidget):
    """One tab: a folder in Details, List or Icons view, with its own back/forward history."""
    changed = Signal()

    def __init__(self, window, model, path, mode=0):
        super().__init__()
        self.window_, self.model = window, model
        self.path, self.history, self.future = "", [], []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        self.details = _setup_view(DetailsView(), model, self)
        self.details.setSortingEnabled(True)
        self.details.sortByColumn(0, Qt.AscendingOrder)
        self.details.setRootIsDecorated(False)
        self.details.setItemsExpandable(False)
        self.details.setUniformRowHeights(True)
        self.details.setIconSize(QSize(20, 20))
        self.details.setColumnWidth(0, 340)
        self.details.setColumnWidth(1, 90)
        self.details.setColumnWidth(2, 150)
        self.details.header().setStretchLastSection(True)
        self.items = _setup_view(ItemsView(), model, self)
        self.items.setResizeMode(QListView.Adjust)
        self.items.setUniformItemSizes(True)
        self.items.setMovement(QListView.Static)
        for v in (self.details, self.items):
            self.stack.addWidget(v)
            v.activated.connect(self._activate)
            v.customContextMenuRequested.connect(lambda pos, view=v: window._menu(pos, view))
            v.selectionModel().currentChanged.connect(lambda cur, _p: window.preview(model.filePath(cur)))
            v.selectionModel().selectionChanged.connect(lambda *_: window._update_status())
        self.set_mode(mode)
        self.open(path, remember=False)

    def view(self):
        return self.stack.currentWidget()

    def set_mode(self, mode: int):
        self.mode = mode
        if mode == 0:
            self.stack.setCurrentWidget(self.details)
            return
        icons = mode == 2
        self.items.setViewMode(QListView.IconMode if icons else QListView.ListMode)
        self.items.setFlow(QListView.LeftToRight if icons else QListView.TopToBottom)
        self.items.setWrapping(True)
        self.items.setWordWrap(icons)
        self.items.setIconSize(QSize(64, 64) if icons else QSize(20, 20))
        self.items.setGridSize(QSize(120, 112) if icons else QSize(260, 30))
        self.items.setSpacing(6 if icons else 0)
        self.stack.setCurrentWidget(self.items)

    def open(self, path: str, remember: bool = True) -> bool:
        if not path or not os.path.isdir(path):
            return False
        if remember and self.path and os.path.normcase(path) != os.path.normcase(self.path):
            self.history.append(self.path)
            self.future.clear()
        self.path = path
        root = self.model.index(path)
        for v in (self.details, self.items):
            v.setRootIndex(root)
        self.changed.emit()
        return True

    def back(self):
        while self.history:
            prev = self.history.pop()
            if os.path.isdir(prev):
                self.future.append(self.path)
                self.open(prev, remember=False)
                return

    def forward(self):
        while self.future:
            nxt = self.future.pop()
            if os.path.isdir(nxt):
                self.history.append(self.path)
                self.open(nxt, remember=False)
                return

    def up(self):
        parent = os.path.dirname(self.path.rstrip("/\\")) or self.path
        if os.name == "nt" and len(parent) == 2 and parent[1] == ":":
            parent += "\\"
        if parent != self.path:
            self.open(parent)

    def selected_paths(self) -> List[str]:
        rows = self.view().selectionModel().selectedRows(0) if self.view() is self.details else \
            self.view().selectionModel().selectedIndexes()
        return [self.model.filePath(i) for i in rows]

    def title(self) -> str:
        return breadcrumbs(self.path)[-1][0] or self.path

    def _activate(self, index: QModelIndex):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self.open(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


# --------------------------------------------------------------------------- breadcrumb bar
class PathBar(QStackedWidget):
    """Clickable folder segments; click the empty part (or Ctrl+L) to type a path instead."""
    go = Signal(str)

    def __init__(self):
        super().__init__()
        self.path = ""
        self.crumbs = QFrame()
        self.crumbs.setObjectName("Crumbs")
        self.crumbs.setCursor(Qt.IBeamCursor)
        self.row = QHBoxLayout(self.crumbs)
        self.row.setContentsMargins(4, 2, 4, 2)
        self.row.setSpacing(0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Type a folder, ~/Downloads, or a file to show it")
        self.edit.returnPressed.connect(lambda: self.go.emit(self.edit.text()))
        self.edit.installEventFilter(self)
        self.addWidget(self.crumbs)
        self.addWidget(self.edit)
        self.crumbs.mousePressEvent = lambda _e: self.start_edit()
        self.setFixedHeight(34)

    def set_path(self, path: str):
        self.path = path
        while self.row.count():
            w = self.row.takeAt(0).widget()
            if w:
                w.deleteLater()
        parts = breadcrumbs(path)
        shown = parts[-6:]
        if len(parts) > len(shown):
            more = QPushButton("…")
            more.setObjectName("Crumb")
            more.setToolTip(path)
            more.clicked.connect(self.start_edit)
            self.row.addWidget(more)
        for i, (label, full) in enumerate(shown):
            if i or len(parts) > len(shown):
                sep = QLabel("›")
                sep.setObjectName("CrumbSep")
                self.row.addWidget(sep)
            b = QPushButton(label)
            b.setObjectName("Crumb")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(full)
            b.clicked.connect(lambda _=False, f=full: self.go.emit(f))
            self.row.addWidget(b)
        self.row.addStretch(1)
        self.setCurrentWidget(self.crumbs)

    def start_edit(self):
        self.edit.setText(self.path)
        self.setCurrentWidget(self.edit)
        self.edit.setFocus()
        self.edit.selectAll()

    def eventFilter(self, obj, ev):
        if obj is self.edit and (ev.type() == QEvent.FocusOut or
                                 ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Escape):
            self.setCurrentWidget(self.crumbs)
        return False


# --------------------------------------------------------------------------- sidebar
class _SidebarDelegate(QStyledItemDelegate):
    """A capacity bar under each drive (amber past 90 % full)."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        used = index.data(USED_ROLE)
        if used is None:
            return
        from ui.theme import current_palette
        p = current_palette()
        r = QRectF(option.rect)
        track = QRectF(r.left() + 40, r.bottom() - 9, r.width() - 52, 4)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(p.border_strong))
        painter.drawRoundedRect(track, 2, 2)
        fill = QRectF(track)
        fill.setWidth(max(4.0, track.width() * used))
        painter.setBrush(QColor(p.warning if used > 0.9 else p.accent))
        painter.drawRoundedRect(fill, 2, 2)
        painter.restore()


class QuickLook(QDialog):
    """Space: a big preview of the selected file; Space or Esc closes it."""

    def __init__(self, parent, path: str):
        super().__init__(parent)
        self.setWindowTitle(os.path.basename(path))
        self.resize(820, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setWordWrap(True)
        self.view.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.view, 1)
        name = QLabel(f"<b>{os.path.basename(path)}</b>  ·  {path}")
        name.setObjectName("Muted")
        lay.addWidget(name)
        ext = os.path.splitext(path)[1].lower()
        pix = QPixmap(path) if ext in fi.KINDS["image"] else QPixmap()
        if not pix.isNull():
            self.view.setPixmap(pix.scaled(780, 540, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif ext in PREVIEW_TEXT and os.path.getsize(path) < 2_000_000:
            with open(path, encoding="utf-8", errors="replace") as f:
                self.view.setText(f.read(20_000))
            self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        else:
            self.view.setText("No preview for this kind of file. Enter opens it.")

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Space, Qt.Key_Escape):
            self.close()
        else:
            super().keyPressEvent(e)


class _Bridge(QObject):
    indexed = Signal(int)


# --------------------------------------------------------------------------- window
class FilesWindow(QMainWindow):
    def __init__(self, start: Optional[str] = None, index: Optional[fi.FileIndex] = None, roots=None, confirm=None):
        super().__init__()
        from ui.widgets import IconButton, Segmented
        self.setWindowTitle("Files")
        self.resize(1240, 760)
        self.index = index or fi.FileIndex()
        self.roots = roots or [str(p) for _label, p in places()]
        self.confirm = confirm or self._ask
        self._bridge = _Bridge()
        self._bridge.indexed.connect(self._indexed)
        self.view_mode = 0
        self._clip: Tuple[List[str], bool] = ([], False)          # (paths, cut)
        self._drive_sig = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.back_btn = IconButton("arrow-left", "Back (Alt+Left)")
        self.fwd_btn = IconButton("arrow-right", "Forward (Alt+Right)")
        self.up_btn = IconButton("arrow-up", "Up one folder (Alt+Up, Backspace)")
        self.back_btn.clicked.connect(lambda: self.tab().back())
        self.fwd_btn.clicked.connect(lambda: self.tab().forward())
        self.up_btn.clicked.connect(self.up)
        self.pathbar = PathBar()
        self.pathbar.go.connect(self.go_to)
        self.views = Segmented(list(VIEWS))
        self.views.changed.connect(self.set_view)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search, or say what you're after: \"photos from last week\"")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._search_soon)
        for w in (self.back_btn, self.fwd_btn, self.up_btn):
            top.addWidget(w)
        top.addWidget(self.pathbar, 3)
        top.addWidget(self.views)
        top.addWidget(self.search, 2)
        outer.addLayout(top)

        split = QSplitter()
        split.setHandleWidth(8)
        self.places = QListWidget()
        self.places.setObjectName("FilesSidebar")
        self.places.setItemDelegate(_SidebarDelegate(self.places))
        self.places.setIconSize(QSize(20, 20))
        self.places.setMinimumWidth(200)
        self.places.setMaximumWidth(280)
        self.places.itemClicked.connect(self._place_clicked)
        self._fill_quick_access()
        split.addWidget(self.places)

        self.middle = QStackedWidget()
        self.sizes = FolderSizes()
        self.model = FilesModel(self.sizes, self)
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        self.model.setRootPath("")
        self.model.directoryLoaded.connect(lambda _p: self._update_status())
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.ElideMiddle)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(lambda _i: self._tab_changed())
        new_tab = QToolButton()
        new_tab.setObjectName("IconButton")
        from ui import icons
        from ui.theme import current_palette
        new_tab.setIcon(icons.icon("plus", current_palette().muted, 16))
        new_tab.setToolTip("New tab (Ctrl+T)")
        new_tab.clicked.connect(lambda: self.new_tab())
        self.tabs.setCornerWidget(new_tab, Qt.TopRightCorner)
        bar = self.tabs.tabBar()
        bar.installEventFilter(self)
        bar.setAcceptDrops(True)
        self.results = QListWidget()
        self.results.itemActivated.connect(lambda it: self._open_hit(it.data(Qt.UserRole)))
        self.results.currentItemChanged.connect(lambda it, _p: it and it.data(Qt.UserRole) and
                                                self.preview(it.data(Qt.UserRole).path))
        self.middle.addWidget(self.tabs)
        self.middle.addWidget(self.results)
        split.addWidget(self.middle)

        side = QWidget()
        sv = QVBoxLayout(side)
        sv.setContentsMargins(8, 4, 0, 0)
        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setMinimumHeight(200)
        self.info = QLabel("Select a file to preview it.  Space shows it bigger.")
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sv.addWidget(self.thumb)
        sv.addWidget(self.info)
        sv.addStretch(1)
        side.setMinimumWidth(240)
        split.addWidget(side)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 760, 260])
        outer.addWidget(split, 1)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        outer.addWidget(self.status)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)                    # search as you type, without a query per keystroke
        self._timer.timeout.connect(self.run_search)
        self._drive_timer = QTimer(self)
        self._drive_timer.setInterval(DRIVE_REFRESH_MS)
        self._drive_timer.timeout.connect(self.refresh_drives)
        for keys, fn in (("F2", self.rename), ("Delete", self.trash), ("Ctrl+Shift+N", self.new_folder),
                         ("Ctrl+F", self.search.setFocus), ("Ctrl+Z", self.undo), ("Backspace", self.up),
                         ("Alt+Left", lambda: self.tab().back()), ("Alt+Right", lambda: self.tab().forward()),
                         ("Alt+Up", self.up), ("Ctrl+L", self.pathbar.start_edit), ("F4", self.pathbar.start_edit),
                         ("Ctrl+T", lambda: self.new_tab()), ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
                         ("Ctrl+Tab", lambda: self._cycle(1)), ("Ctrl+Shift+Tab", lambda: self._cycle(-1)),
                         ("Ctrl+C", lambda: self.copy_selection(False)), ("Ctrl+X", lambda: self.copy_selection(True)),
                         ("Ctrl+V", self.paste), ("F5", self.refresh_drives)):
            QShortcut(QKeySequence(keys), self, activated=fn)
        self.new_tab(start or str(Path.home()))
        self.reindex()

    # ------------------------------------------------------------------ tabs
    def tab(self) -> FolderTab:
        return self.tabs.currentWidget()

    @property
    def current(self) -> str:
        return self.tab().path

    @property
    def tree(self):
        """The current tab's Details view."""
        return self.tab().details

    def new_tab(self, path: Optional[str] = None) -> FolderTab:
        path = path or (self.tab().path if self.tabs.count() else str(Path.home()))
        t = FolderTab(self, self.model, path, self.view_mode)
        t.changed.connect(lambda tab=t: self._tab_path_changed(tab))
        i = self.tabs.addTab(t, t.title())
        self.tabs.setTabToolTip(i, t.path)
        self.tabs.setCurrentIndex(i)
        return t

    def close_tab(self, i: int):
        if self.tabs.count() <= 1:
            self.close()
            return
        w = self.tabs.widget(i)
        self.tabs.removeTab(i)
        w.deleteLater()

    def _cycle(self, step: int):
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def _tab_path_changed(self, tab):
        i = self.tabs.indexOf(tab)
        if i >= 0:
            self.tabs.setTabText(i, tab.title())
            self.tabs.setTabToolTip(i, tab.path)
        if tab is self.tab():
            self._tab_changed()

    def _tab_changed(self):
        t = self.tab()
        if t is None:
            return
        self.pathbar.set_path(t.path)
        self.back_btn.setEnabled(bool(t.history))
        self.fwd_btn.setEnabled(bool(t.future))
        self.views.set_index(t.mode)
        self.middle.setCurrentWidget(self.tabs)
        self.setWindowTitle(f"{t.title()} — Files")
        self._update_status()

    def eventFilter(self, obj, ev):
        bar = self.tabs.tabBar()
        if obj is bar:
            t = ev.type()
            if t == QEvent.MouseButtonRelease and ev.button() == Qt.MiddleButton:
                i = bar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self.close_tab(i)
                    return True
            elif t in (QEvent.DragEnter, QEvent.DragMove) and ev.mimeData().hasUrls():
                i = bar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self.tabs.setCurrentIndex(i)         # hover a tab to drop into one of its folders
                    ev.acceptProposedAction()
                    return True
            elif t == QEvent.Drop and ev.mimeData().hasUrls():
                i = bar.tabAt(ev.position().toPoint())
                if i >= 0:
                    self.drop([u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()],
                              self.tabs.widget(i).path, copy=bool(ev.modifiers() & Qt.ControlModifier))
                    ev.setDropAction(Qt.CopyAction)
                    ev.accept()
                    return True
        return super().eventFilter(obj, ev)

    # ------------------------------------------------------------------ browsing
    def open_folder(self, path: str):
        if self.tab().open(path):
            self.middle.setCurrentWidget(self.tabs)

    def go_to(self, text: str):
        folder, file = parse_location(text, self.current)
        if folder is None:
            self.status.setText(f"Couldn't find {text}")
            self.pathbar.set_path(self.current)
            return
        self.open_folder(folder)
        self.pathbar.set_path(self.current)
        if file:
            idx = self.model.index(file)
            self.tab().view().setCurrentIndex(idx)
            self.tab().view().scrollTo(idx)

    def up(self):
        if self.search.hasFocus() and self.search.text():
            return
        self.tab().up()

    def set_view(self, mode: int):
        self.view_mode = mode
        self.tab().set_mode(mode)

    def selected(self) -> Optional[str]:
        if self.middle.currentWidget() is self.results:
            it = self.results.currentItem()
            hit = it.data(Qt.UserRole) if it else None
            return hit.path if hit else None
        idx = self.tab().view().currentIndex()
        return self.model.filePath(idx) if idx.isValid() else None

    def _update_status(self):
        t = self.tab()
        if t is None or self.middle.currentWidget() is self.results:
            return
        n = self.model.rowCount(self.model.index(t.path))
        sel = len(t.selected_paths())
        self.status.setText(f"{n} items" + (f"  ·  {sel} selected" if sel else ""))

    # ------------------------------------------------------------------ sidebar
    def _section(self, title: str):
        it = QListWidgetItem(title.upper())
        it.setFlags(Qt.NoItemFlags)
        f = it.font()
        f.setBold(True)
        f.setPointSizeF(max(7.0, f.pointSizeF() * 0.8))
        it.setFont(f)
        it.setSizeHint(QSize(0, 34))
        self.places.addItem(it)

    def _fill_quick_access(self):
        self.places.clear()
        self._section("Quick access")
        icons = {"Home": ("user-home", "home"), "Desktop": ("user-desktop", "layout"),
                 "Documents": ("folder-documents", "folder"), "Downloads": ("folder-downloads", "download"),
                 "Pictures": ("folder-pictures", "folder"), "Music": ("folder-music", "music"),
                 "Videos": ("folder-videos", "video")}
        for label, path in places():
            if label not in icons:
                continue
            it = QListWidgetItem(theme_icon(*icons[label]), label)
            it.setData(Qt.UserRole, str(path))
            it.setSizeHint(QSize(0, 34))
            self.places.addItem(it)
        rec = QListWidgetItem(theme_icon("document-open-recent", "history"), "Recent files")
        rec.setData(Qt.UserRole, "recent:")
        rec.setSizeHint(QSize(0, 34))
        self.places.addItem(rec)
        self._section("Drives")
        self._drive_start = self.places.count()

    def show_drives(self, entries: List[Dict]):
        sig = [(e["label"], e["path"], e["free"]) for e in entries]
        if sig == self._drive_sig:
            return
        self._drive_sig = sig
        while self.places.count() > self._drive_start:
            self.places.takeItem(self.places.count() - 1)
        for e in entries:
            if e["path"]:
                sub = f"{human_size(e['free'])} free of {human_size(e['size'])}" if e["size"] else ""
            else:
                sub = "Locked: unlock in Settings" if e["locked"] else "Not mounted: click to open"
            it = QListWidgetItem(theme_icon(e["icon"], "drive"), f"{e['label']}\n{sub}")
            it.setData(Qt.UserRole, e["path"] or None)
            it.setData(DRIVE_ROLE, e)
            if e["path"] and e["size"]:
                it.setData(USED_ROLE, max(0.0, min(1.0, 1 - (e["free"] or 0) / e["size"])))
            it.setSizeHint(QSize(0, 56))
            it.setToolTip(e["path"] or e["label"])
            self.places.addItem(it)

    def refresh_drives(self):
        from ui.widgets import run_async
        run_async(list_drives, self.show_drives, lambda _e: None)

    def _place_clicked(self, it: QListWidgetItem):
        path = it.data(Qt.UserRole)
        if path == "recent:":
            self.show_recent()
        elif path:
            self.search.clear()
            self.open_folder(path)
        elif it.data(DRIVE_ROLE):
            self.mount_and_open(it.data(DRIVE_ROLE))

    def mount_and_open(self, entry: Dict):
        v = entry.get("volume")
        if v is None or entry.get("locked"):
            self.status.setText(f"{entry['label']} is locked with BitLocker: unlock it in Settings > Drives."
                                if entry.get("locked") else f"Can't open {entry['label']}.")
            return
        from core import drives
        from ui.widgets import run_async
        self.status.setText(f"Mounting {entry['label']}…")

        def done(res):
            self.status.setText(res.message or f"{entry['label']} is ready" + (" (read-only)" if res.read_only else ""))
            if res.ok and res.mountpoint:
                self.open_folder(res.mountpoint)
                self.refresh_drives()
        run_async(lambda: drives.mount(v), done, lambda e: self.status.setText(f"Couldn't mount it: {e}"))

    def show_recent(self, files: Optional[List[str]] = None):
        files = recent_files() if files is None else files
        self.results.clear()
        for p in files:
            hit = fi.Hit("file", os.path.basename(p), p, os.path.dirname(p))
            item = QListWidgetItem(f"{hit.title}\n{hit.detail}")
            item.setData(Qt.UserRole, hit)
            self.results.addItem(item)
        if not files:
            self.results.addItem(QListWidgetItem("Nothing opened recently (apps record it as you open files)."))
        self.middle.setCurrentWidget(self.results)
        self.status.setText(f"{len(files)} recent files")

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh_drives()
        self._drive_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._drive_timer.stop()

    def closeEvent(self, e):
        self.sizes.shutdown()
        super().closeEvent(e)

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
            self.middle.setCurrentWidget(self.tabs)
            self._update_status()
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
        is_dir = os.path.isdir(path)
        kind = "Folder" if is_dir else fi.FileIndex._kind(ext, False).capitalize()
        size = human_size(self.sizes.get(path)) if is_dir else human_size(st.st_size)
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

    def quick_look(self):
        path = self.selected()
        if path and os.path.isfile(path):
            QuickLook(self, path).exec()

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
        paths = self.tab().selected_paths() if self.middle.currentWidget() is self.tabs else []
        for path in paths or [p for p in [self.selected()] if p]:
            if not self._do("files.trash", {"path": path}):
                break

    def undo(self):
        result = actions.undo_last(source="gui")
        self.status.setText(result.text)

    def drop(self, paths: List[str], folder: str, copy: bool = False) -> int:
        """Dragged files land in ``folder``: moved on the same drive, copied onto another (or with Ctrl held)."""
        done = 0
        for p in paths:
            if not p or os.path.normcase(os.path.dirname(p.rstrip("/\\"))) == os.path.normcase(folder) \
                    or os.path.normcase(p) == os.path.normcase(folder):
                continue
            try:
                same_drive = os.stat(p).st_dev == os.stat(folder).st_dev
            except OSError:
                continue
            if self._do("files.copy" if copy or not same_drive else "files.move", {"path": p, "to": folder}):
                done += 1
            else:
                break
        return done

    def copy_selection(self, cut: bool):
        if self.search.hasFocus() or self.pathbar.edit.hasFocus():
            return
        paths = self.tab().selected_paths()
        if not paths:
            return
        self._clip = (paths, cut)
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(p) for p in paths])
        QApplication.clipboard().setMimeData(data)
        self.status.setText(f"{len(paths)} {'cut' if cut else 'copied'}: Ctrl+V to put them here or in another tab")

    def paste(self):
        if self.search.hasFocus() or self.pathbar.edit.hasFocus():
            return
        urls = QApplication.clipboard().mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        cut = self._clip[1] and paths == self._clip[0]
        for p in paths:
            if not self._do("files.move" if cut else "files.copy", {"path": p, "to": self.current}):
                break
        if cut:
            self._clip = ([], False)

    def _menu(self, pos, view):
        path = self.selected()
        menu = QMenu(self)
        if path and os.path.isdir(path):
            menu.addAction("Open in new tab", lambda: self.new_tab(path))
        if path and os.path.isfile(path):
            menu.addAction("Quick look (Space)", self.quick_look)
        menu.addAction("New folder", self.new_folder)
        if path:
            menu.addAction("Copy", lambda: self.copy_selection(False))
            menu.addAction("Cut", lambda: self.copy_selection(True))
        if QApplication.clipboard().mimeData().hasUrls():
            menu.addAction("Paste", self.paste)
        if path:
            menu.addSeparator()
            menu.addAction("Rename", self.rename)
            menu.addAction("Move to trash", self.trash)
            menu.addAction("Copy path", lambda: QApplication.clipboard().setText(path))
            menu.addAction("Ask SAINT about this…", lambda: self._ask_saint(path))
        menu.exec(view.viewport().mapToGlobal(pos))

    def handle_command(self, cmd: str):
        """From a second `halos-files <folder>` (core/instance.py): that folder in a new tab, window to the front."""
        from core import instance
        if cmd.startswith("token:"):
            instance.use_activation_token(cmd[6:])
            return
        if cmd.startswith("open:"):
            folder, file = parse_location(cmd[5:], self.current)
            if folder:
                self.new_tab(folder)
                if file:
                    self.go_to(file)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _ask_saint(path: str):
        subprocess.Popen(["saint", "--ask", f"Tell me about the file {path}"])

    def _ask(self, request) -> bool:
        return QMessageBox.question(self, request.title, request.preview) == QMessageBox.Yes


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    from core import instance
    token = instance.activation_token()               # before QApplication takes it out of the environment
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Files")
    app.setDesktopFileName("halos-files")
    if QIcon.themeName() in ("", "hicolor") and os.path.isdir("/usr/share/icons/HalOS"):
        QIcon.setThemeName("HalOS")
    try:
        from core.config import config
        from ui import theme
        a = config.get("appearance", {}) or {}
        app.setPalette(theme.qt_palette(theme.current_palette()))
        app.setStyleSheet(theme.build_stylesheet(a.get("theme", "Dark"), a.get("accent", "#feaa34"),
                                                 a.get("font_family", "Noto Sans" if os.name != "nt" else "Segoe UI"),
                                                 a.get("font_size", 13)))
    except Exception:
        pass
    args = [a for a in argv if not a.startswith("--")]
    folder, file = parse_location(args[0], os.getcwd()) if args else (None, None)   # a path or a file:// URL (%U)
    start = folder or str(Path.home())
    if "--new-window" not in argv:
        if token:                                      # so the running window may come to the front (Wayland)
            instance.send(f"token:{token}", 800, name="files")
        if instance.send(f"open:{file or start}", 800, name="files"):
            return 0                                   # the running Files opened it in a new tab
    w = FilesWindow(start)
    if file:
        w.go_to(file)
    server = instance.Server(app, name="files")
    server.command.connect(w.handle_command)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
