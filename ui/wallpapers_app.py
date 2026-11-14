"""
ui/wallpapers_app.py

HalOS Wallpapers as its own app (`halos-wallpapers`), in SAINT's theme like the Store and the Visual Shop: one grid of
everything that can be the desktop (core/wallpapers.py): SAINT's living wallpaper (built in), every Wallpaper Engine
wallpaper downloaded through Steam on HalOS or on a Windows drive, and pictures. Pick one, choose a monitor, Apply.
One window per user: a second `halos-wallpapers` brings the first forward.
"""

import os
import sys

if __package__ in (None, ""):                         # run as a script: /opt/saint/app/ui/wallpapers_app.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImageReader, QMovie, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QProgressBar, QPushButton, QVBoxLayout, QWidget)

from core import wallpaper_engine as we
from core import wallpapers as wps

INSTANCE = "wallpapers"
VIEWS = [("all", "All wallpapers"), ("living", "SAINT"), ("engine", "Wallpaper Engine"), ("image", "Pictures")]
TYPE_TEXT = {"scene": "Wallpaper Engine scene", "video": "Wallpaper Engine video", "web": "Wallpaper Engine web page",
             "living": "Living wallpaper", "picture": "Picture"}
SOURCE_TEXT = {"halos": "Steam on HalOS", "migrated": "Brought over from Windows",
               "windows": "Steam on your Windows drive", "plasma": "Comes with HalOS",
               "pictures": "Your Pictures"}


def thumbnail(path, w: int, h: int) -> QPixmap:
    """A picture (or a GIF's first frame) scaled down while it's read, so big previews load fast."""
    if not path:
        return QPixmap()
    r = QImageReader(str(path))
    size = r.size()
    if size.isValid() and size.width() > 0:
        r.setScaledSize(size.scaled(w, h, Qt.KeepAspectRatioByExpanding))
    img = r.read()
    return QPixmap.fromImage(img) if not img.isNull() else QPixmap()


def living_preview(w: int, h: int) -> QPixmap:
    """SAINT's wallpaper drawn by the Wallpaper page's own preview (the same rules as its QML)."""
    from ui.settings_pages.wallpaper import Preview
    p = Preview()
    p.resize(w, h)
    return p.grab()


class WallpapersWindow(QMainWindow):
    loaded = Signal(list)
    support_done = Signal(bool, str)

    def __init__(self, catalog=None, applier=wps.apply):
        super().__init__()
        from ui import icons
        from ui.theme import current_palette
        self.applier = applier
        self.items = []
        self.current = None
        self._movie = None
        self._living_pm = None
        self.setWindowTitle("HalOS Wallpapers")
        icons.set_window_icon(self, QIcon.fromTheme("halos-wallpapers", icons.icon("image", current_palette().accent, 64)))
        self.resize(1180, 760)
        self.setMinimumSize(760, 520)
        self.loaded.connect(self._loaded)
        self.support_done.connect(self._support_done)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        side = QVBoxLayout()
        title = QLabel("Wallpapers")
        title.setObjectName("StoreHeadline")
        side.addWidget(title)
        self.nav = QListWidget()
        self.nav.setFixedWidth(200)
        for key, label in VIEWS:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, key)
            self.nav.addItem(it)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(lambda _: self.refresh())
        side.addWidget(self.nav, 1)
        self.windows_btn = QPushButton("Look on Windows drives")
        self.windows_btn.setObjectName("Ghost")
        self.windows_btn.setToolTip("Mounts your Windows drives read-only and finds the Wallpaper Engine wallpapers "
                                    "Steam downloaded there")
        self.windows_btn.clicked.connect(self.look_on_windows)
        side.addWidget(self.windows_btn)
        pick = QPushButton("Choose a picture…")
        pick.setObjectName("Ghost")
        pick.clicked.connect(self.choose_picture)
        side.addWidget(pick)
        lay.addLayout(side)

        mid = QVBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("StoreSearch")
        self.query.setPlaceholderText("Search wallpapers…")
        self.query.textChanged.connect(lambda _: self.refresh())
        mid.addWidget(self.query)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setIconSize(QSize(208, 130))
        self.grid.setGridSize(QSize(232, 176))
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setWordWrap(True)
        self.grid.currentItemChanged.connect(lambda it, _: self.show_item(it.data(Qt.UserRole) if it else None))
        self.grid.itemDoubleClicked.connect(lambda _it: self.apply())
        mid.addWidget(self.grid, 1)
        self.empty = QLabel("Looking for wallpapers…")
        self.empty.setObjectName("Faint")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        mid.addWidget(self.empty)
        lay.addLayout(mid, 1)

        det = QVBoxLayout()
        self.big = QLabel()
        self.big.setFixedSize(320, 200)
        self.big.setAlignment(Qt.AlignCenter)
        det.addWidget(self.big)
        self.name = QLabel()
        self.name.setObjectName("ShelfTitle")
        self.name.setWordWrap(True)
        det.addWidget(self.name)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        det.addWidget(self.desc)
        self.meta = QLabel()
        self.meta.setObjectName("Faint")
        self.meta.setWordWrap(True)
        self.meta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        det.addWidget(self.meta)
        self.screen = QComboBox()
        self.screen.addItem("All monitors", -1)
        for i, s in enumerate(QApplication.screens()):
            self.screen.addItem(f"Monitor {i + 1}: {s.name()}", i)
        det.addWidget(self.screen)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.clicked.connect(self.apply)
        det.addWidget(self.apply_btn)
        self.support_btn = QPushButton("Install Wallpaper Engine support")
        self.support_btn.clicked.connect(self.install_support)
        det.addWidget(self.support_btn)
        row = QHBoxLayout()
        self.customize_btn = QPushButton("Customize…")
        self.customize_btn.setObjectName("Ghost")
        self.customize_btn.setToolTip("Colours, logo, what it moves with: Settings > Wallpaper")
        self.customize_btn.clicked.connect(self.customize)
        self.widget_btn = QPushButton("Add as a widget")
        self.widget_btn.setObjectName("Ghost")
        self.widget_btn.setToolTip("The SAINT logo and visualizer over any wallpaper")
        self.widget_btn.clicked.connect(self.add_widget)
        row.addWidget(self.customize_btn)
        row.addWidget(self.widget_btn)
        det.addLayout(row)
        self.why = QLabel()
        self.why.setObjectName("Faint")
        self.why.setWordWrap(True)
        det.addWidget(self.why)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        det.addWidget(self.progress)
        self.status = QLabel()
        self.status.setWordWrap(True)
        det.addWidget(self.status)
        det.addStretch(1)
        self.detail = QWidget()
        self.detail.setLayout(det)
        self.detail.setFixedWidth(340)
        lay.addWidget(self.detail)
        self.setCentralWidget(root)

        if catalog is not None:
            self._loaded(catalog)
        else:
            self.load()

    # --- finding
    def load(self, windows=None):
        """Scan off the UI thread (an NTFS drive with a big workshop folder takes a moment)."""
        self.empty.setText("Looking for wallpapers…")
        self.empty.show()

        def work():
            try:
                found = wps.catalog(windows=windows)
            except Exception as e:                 # a scan must never take the window down
                import logging
                logging.getLogger("saint.wallpapers").warning("wallpapers.scan_failed %s", e)
                found = [wps.living_item()]
            try:
                self.loaded.emit(found)
            except RuntimeError:                   # the window closed meanwhile
                pass
        threading.Thread(target=work, daemon=True, name="wallpapers-scan").start()

    def _loaded(self, found):
        self.items = list(found)
        self.refresh()

    def look_on_windows(self):
        """Mount Windows drives read-only (the migration's own detection), then scan again."""
        self.windows_btn.setEnabled(False)
        self.status.setText("Looking on your Windows drives…")

        def work():
            try:
                from core import windows_migration as wm
                wm.detect_installs()
            except Exception as e:
                import logging
                logging.getLogger("saint.wallpapers").info("wallpapers.windows_detect %s", e)
            try:
                found = wps.catalog()
            except Exception:
                found = self.items
            try:
                self.loaded.emit(found)
            except RuntimeError:
                pass
        threading.Thread(target=work, daemon=True, name="wallpapers-windows").start()

    def choose_picture(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", str(Path.home() / "Pictures"),
                                              "Pictures (*.jpg *.jpeg *.png *.webp *.avif *.jxl *.bmp)")
        if path:
            self.add_picture(path)

    def add_picture(self, path: str):
        p = Path(path)
        item = {"kind": "image", "id": str(p), "title": p.stem, "type": "picture", "source": "pictures",
                "file": p, "preview": p}
        self.items = [i for i in self.items if i["id"] != item["id"]] + [item]
        self.nav.setCurrentRow([k for k, _ in VIEWS].index("image"))
        self.refresh(select=item["id"])

    # --- list
    def view(self) -> str:
        it = self.nav.currentItem()
        return it.data(Qt.UserRole) if it else "all"

    def visible_items(self):
        v, words = self.view(), self.query.text().lower().split()
        return [i for i in self.items if (v == "all" or i["kind"] == v)
                and all(w in i["title"].lower() for w in words)]

    def _thumb(self, item, w, h) -> QPixmap:
        if item["kind"] == "living":
            if self._living_pm is None:
                self._living_pm = living_preview(320, 200)
            return self._living_pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        pm = thumbnail(item.get("preview"), w, h)
        if pm.isNull():
            from ui import icons
            from ui.theme import current_palette
            pm = icons.pixmap("image", current_palette().faint, 48)
        return pm

    def refresh(self, select=None):
        shown = self.visible_items()
        keep = select or (self.current["id"] if self.current else None)
        self.windows_btn.setEnabled(True)
        self.grid.blockSignals(True)
        self.grid.clear()
        for item in shown:
            label = item["title"] + (f"  ·  {item['type']}" if item["kind"] == "engine" else "")
            li = QListWidgetItem(QIcon(self._thumb(item, 208, 130)), label)
            li.setData(Qt.UserRole, item)
            li.setToolTip(TYPE_TEXT.get(item["type"], "") + " · " + SOURCE_TEXT.get(item.get("source"), ""))
            self.grid.addItem(li)
            if item["id"] == keep:
                self.grid.setCurrentItem(li)
        self.grid.blockSignals(False)
        engine = [i for i in self.items if i["kind"] == "engine"]
        if self.view() == "engine" and not engine:
            self.empty.setText("No Wallpaper Engine wallpapers found yet. Subscribe to some in Wallpaper Engine on "
                               "Steam (on HalOS or on Windows) and they show up here. On a dual-boot PC, choose "
                               "Look on Windows drives.")
        else:
            self.empty.setText("Nothing matches.")
        self.empty.setVisible(not shown)
        if not self.grid.currentItem() and shown:
            self.grid.setCurrentRow(0)
        cur = self.grid.currentItem()
        self.show_item(cur.data(Qt.UserRole) if cur else None)

    # --- detail
    def show_item(self, item):
        self.current = item
        self.detail.setEnabled(item is not None)
        if self._movie:
            self._movie.stop()
            self._movie = None
        if not item:
            for w in (self.name, self.desc, self.meta, self.why):
                w.setText("")
            self.big.clear()
            return
        preview = item.get("preview")
        if preview and str(preview).lower().endswith(".gif"):       # Wallpaper Engine previews move
            self._movie = QMovie(str(preview))
            self._movie.setScaledSize(QSize(320, 200))
            self.big.setMovie(self._movie)
            self._movie.start()
        else:
            self.big.setPixmap(self._thumb(item, 320, 200).scaled(320, 200, Qt.KeepAspectRatio,
                                                                     Qt.SmoothTransformation))
        self.name.setText(item["title"])
        source = SOURCE_TEXT.get(item.get("source"), "")
        self.desc.setText(item.get("about") or f"{TYPE_TEXT.get(item['type'], item['type'])} · {source}")
        if item["kind"] == "engine":
            note = ("\nPlays from your Windows drive: it has to be mounted for this wallpaper to show."
                    if item.get("source") == "windows" else "")
            self.meta.setText(f"Workshop item {item['id']}\n{item['dir']}{note}")
        else:
            self.meta.setText(str(item.get("file") or ""))
        why = wps.can_apply(item)
        self.apply_btn.setEnabled(not why)
        self.why.setText(why)
        self.why.setVisible(bool(why))
        self.support_btn.setVisible(item["kind"] == "engine" and bool(why))
        living = item["kind"] == "living"
        self.customize_btn.setVisible(living)
        self.widget_btn.setVisible(living)

    # --- actions
    def apply(self):
        item = self.current
        if not item or wps.can_apply(item):
            return
        try:
            self.status.setText(self.applier(item, self.screen.currentData()))
        except we.EngineError as e:
            self.status.setText(str(e))

    def customize(self):
        from core.actions.sets import halos_apps as ha
        ha._spawn(ha._launcher("saint", str(ha.APP_ROOT / "app.py")) + ["--page", "Wallpaper"])

    def add_widget(self):
        from ui.settings_pages.wallpaper import run_script, widget_script
        why = run_script(widget_script(self.screen.currentData()))
        self.status.setText(why or "The SAINT Visualizer widget is on your desktop: drag it to place it. Right-click "
                                   "it for its settings.")

    def install_support(self):
        self.support_btn.setEnabled(False)
        self.progress.show()
        self.status.setText("Installing Wallpaper Engine support… (it asks for your password once)")

        def work():
            errors = {}
            try:
                ok = we.install_support(errors=errors)
            except Exception as e:                  # no queue / no paru: say so instead of spinning forever
                ok, errors["wallpaper-engine"] = False, str(e)
            self.support_done.emit(ok, errors.get("wallpaper-engine", ""))
        threading.Thread(target=work, daemon=True).start()

    def _support_done(self, ok, why):
        self.progress.hide()
        self.support_btn.setEnabled(True)
        self.status.setText("Wallpaper Engine support is installed. Log out and back in once, then choose Apply."
                            if ok else f"Couldn't install Wallpaper Engine support: {why or 'see the log'}")
        if self.current:
            self.show_item(self.current)

    def handle_command(self, _cmd: str):
        self.showNormal()
        self.raise_()
        self.activateWindow()


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("HalOS Wallpapers")
    app.setApplicationDisplayName("HalOS Wallpapers")
    # Wayland app id = halos-wallpapers.desktop: its windows group under its own icon.
    app.setDesktopFileName("halos-wallpapers")
    from core import instance
    if instance.send("show", name=INSTANCE):
        return 0
    from ui.taskmanager import apply_style
    apply_style(app)
    win = WallpapersWindow()
    server = instance.Server(app, name=INSTANCE)
    server.command.connect(win.handle_command)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
