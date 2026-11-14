"""
ui/visual_shop.py

SAINT Visual Shop as its own window (`saint-visual-shop`), in SAINT's theme: browse the local catalog of looks
(core/visual_shop.py), search and filter, see an item's details, install / update / uninstall, favourite, apply
what can really be applied here, and import your own pack (folder or .zip). No accounts, payments or network.
"""

import os
import sys

if __package__ in (None, ""):                         # run as a script: /opt/saint/app/ui/visual_shop.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from core.visual_shop import CATEGORIES, PackError, Shop

VIEWS = [("all", "All looks"), ("installed", "Installed"), ("favourites", "Favourites"), ("updates", "Updates")]


def _size(n: int) -> str:
    return f"{n / 2**20:.1f} MB" if n >= 2**20 else f"{max(1, n // 1024)} KB"


class VisualShopWindow(QMainWindow):
    def __init__(self, shop: Shop = None):
        super().__init__()
        from ui import icons
        from ui.theme import current_palette
        self.shop = shop or Shop()
        self.current = None
        self.setWindowTitle("SAINT Visual Shop")
        icons.set_window_icon(self, icons.icon("sparkles", current_palette().accent, 64))
        self.resize(1180, 760)
        self.setMinimumSize(760, 520)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        side = QVBoxLayout()
        title = QLabel("Visual Shop")
        title.setObjectName("StoreHeadline")
        side.addWidget(title)
        self.nav = QListWidget()
        self.nav.setFixedWidth(200)
        for key, label in VIEWS:
            self._nav_item(label, ("view", key))
        present = {m["category"] for m in self.shop.items()}
        for c in CATEGORIES:
            if c in present:
                self._nav_item(c.replace("-", " ").capitalize(), ("category", c))
        self._nav_item("Wallpaper Engine ↗", ("engine", ""))      # its own app now: HalOS Wallpapers
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(lambda _: self.refresh())
        side.addWidget(self.nav, 1)
        imp = QPushButton("Import a pack...")
        imp.setObjectName("Ghost")
        imp.clicked.connect(self.import_pack)
        side.addWidget(imp)
        lay.addLayout(side)

        mid = QVBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("StoreSearch")
        self.query.setPlaceholderText("Search wallpapers, palettes, themes, icons...")
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
        mid.addWidget(self.grid, 1)
        self.empty = QLabel("Nothing here yet.")
        self.empty.setObjectName("Faint")
        self.empty.setAlignment(Qt.AlignCenter)
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
        row = QHBoxLayout()
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.install)
        self.remove_btn = QPushButton("Uninstall")
        self.remove_btn.setObjectName("Ghost")
        self.remove_btn.clicked.connect(self.uninstall)
        self.fav_btn = QPushButton("Favourite")
        self.fav_btn.setObjectName("Ghost")
        self.fav_btn.clicked.connect(self.toggle_favourite)
        for b in (self.install_btn, self.remove_btn, self.fav_btn):
            row.addWidget(b)
        det.addLayout(row)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply)
        det.addWidget(self.apply_btn)
        self.apply_why = QLabel()
        self.apply_why.setObjectName("Faint")
        self.apply_why.setWordWrap(True)
        det.addWidget(self.apply_why)
        self.progress = QProgressBar()
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
        self.refresh()

    def _nav_item(self, label, data):
        it = QListWidgetItem(label)
        it.setData(Qt.UserRole, data)
        self.nav.addItem(it)

    def _preview(self, m, w, h) -> QPixmap:
        p = self.shop.preview_path(m)
        pm = QIcon(str(p)).pixmap(QSize(w, h)) if p else QPixmap()
        return pm if not pm.isNull() else QPixmap(w, h)

    # --- list
    def refresh(self):
        it = self.nav.currentItem()
        kind, key = it.data(Qt.UserRole) if it else ("view", "all")
        if kind == "engine":
            from ui.settings_pages.wallpaper import open_wallpapers_app
            open_wallpapers_app()
            self.nav.setCurrentRow(0)
            return
        self.empty.setText("Nothing here yet.")
        items = self.shop.search(self.query.text(), category=key if kind == "category" else "",
                                 view=key if kind == "view" else "all")
        keep = self.current["id"] if self.current else None
        self.grid.blockSignals(True)
        self.grid.clear()
        inst, fav = self.shop.installed(), self.shop.favourites()
        for m in items:
            tag = " (update)" if self.shop.update_available(m) else " (installed)" if m["id"] in inst else ""
            li = QListWidgetItem(QIcon(self._preview(m, 208, 130)), ("★ " if m["id"] in fav else "") + m["name"] + tag)
            li.setData(Qt.UserRole, m)
            li.setToolTip(m.get("description", ""))
            self.grid.addItem(li)
            if m["id"] == keep:
                self.grid.setCurrentItem(li)
        self.grid.blockSignals(False)
        self.empty.setVisible(not items)
        if not self.grid.currentItem() and items:
            self.grid.setCurrentRow(0)
        self.show_item(self.grid.currentItem().data(Qt.UserRole) if self.grid.currentItem() else None)

    # --- detail
    def show_item(self, m):
        self.current = m
        self.detail.setEnabled(m is not None)
        for b in (self.install_btn, self.remove_btn, self.fav_btn):
            b.setVisible(True)
        if not m:
            self.name.setText("")
            self.desc.setText("")
            self.meta.setText("")
            self.big.clear()
            return
        self.big.setPixmap(self._preview(m, 320, 200))
        self.name.setText(m["name"])
        self.desc.setText(m.get("description", ""))
        self.meta.setText(
            f"{m['category'].replace('-', ' ').capitalize()}  ·  version {m['version']}  ·  {_size(m['size'])}\n"
            f"By {m['creator']}  ·  Licence: {m['license']}\n{m['attribution']}\n"
            f"Works on: {', '.join(m['compatibility'])}\nsha256 {m['sha256'][:16]}...")
        have = self.shop.installed().get(m["id"])
        update = self.shop.update_available(m)
        self.install_btn.setText("Update" if update else "Installed" if have else "Install")
        self.install_btn.setEnabled(update or not have)
        self.remove_btn.setEnabled(bool(have))
        self.fav_btn.setText("Unfavourite" if m["id"] in self.shop.favourites() else "Favourite")
        ok, why = self.shop.can_apply(m)
        self.apply_btn.setEnabled(ok)
        self.apply_btn.setText("Apply" if ok or not why.startswith("Apply on HalOS") else "Apply on HalOS")
        self.apply_why.setText(why)
        self.apply_why.setVisible(bool(why))

    # --- actions
    def _progress(self, done, total):
        self.progress.setValue(int(done * 100 / total))
        QApplication.processEvents()

    def _run(self, fn, ok_text):
        self.status.setText("")
        self.progress.setValue(0)
        self.progress.show()
        try:
            fn()
            self.status.setText(ok_text)
        except (PackError, OSError) as e:
            self.status.setText(f"Couldn't do that: {e}")
        finally:
            self.progress.hide()
        self.refresh()

    def install(self):
        m = self.current
        if m:
            from core import downloads

            def go():
                with downloads.Tracker(f"visual-shop:{m['id']}", m["name"], "Visual Shop") as track:
                    self.shop.install(m, progress=lambda d, t: (track.progress(d, t), self._progress(d, t)))
            self._run(go, f"{m['name']} is installed.")
            if m["id"] in self.shop.installed() and self.shop.applies_on_install(m):
                self.apply()                       # a wallpaper you install is one you want to see

    def uninstall(self):
        m = self.current
        if m:
            self._run(lambda: self.shop.uninstall(m["id"]), f"{m['name']} was removed.")

    def toggle_favourite(self):
        if self.current:
            self.shop.set_favourite(self.current["id"], self.current["id"] not in self.shop.favourites())
            self.refresh()

    def apply(self):
        m = self.current
        if m:
            out = {}
            self._run(lambda: out.setdefault("msg", self.shop.apply(m)), "")
            self.status.setText(out.get("msg", self.status.text()))

    def import_pack(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import a pack", os.path.expanduser("~"), "Packs (*.zip)")
        if not path:
            path = QFileDialog.getExistingDirectory(self, "Or choose a pack folder", os.path.expanduser("~"))
        if not path:
            return
        try:
            m = self.shop.import_pack(path, progress=self._progress)
        except (PackError, OSError) as e:
            QMessageBox.warning(self, "Visual Shop", f"That pack wasn't installed:\n{e}")
            return
        self.status.setText(f"{m['name']} is installed.")
        self.refresh()


def main(argv=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("SAINT Visual Shop")
    app.setDesktopFileName("saint-visual-shop")
    from ui.taskmanager import apply_style
    apply_style(app)
    win = VisualShopWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
