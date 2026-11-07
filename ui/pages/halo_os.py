"""
ui/pages/halo_os.py

The one settings page in SAINT's window, behind both the HalOS and the Settings sidebar items: the panel of
ui/saintos_center.py, whose rail has a HalOS group and a SAINT group. Built the first time it's opened, so it
costs nothing at startup. The HalOS sidebar item opens the HalOS group, Settings the SAINT group.

One level of navigation at a time: while it's open its rail is the left-hand navigation (SAINT's sidebar folds
to icons, giving the page the width), and Back at the top returns to where you were. On Windows, where the
operating system's pages don't apply, only the SAINT group is there.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from ui.widgets import Page


class HaloPage(Page):
    def __init__(self, window=None):
        super().__init__("Settings", "HalOS and SAINT settings.")
        self.window = window
        self._cc = None
        self._nav = None
        self._pending = ""
        self._pending_group = ""
        self._sidebar_was_collapsed = None
        back = QPushButton("←  Back")
        back.setObjectName("Ghost")
        back.setToolTip("Back to the page you came from")
        back.clicked.connect(self._back)
        self.root.insertWidget(0, back, 0, Qt.AlignLeft)
        self.title.hide()                             # the rail below carries the name
        self.subtitle.hide()

    @property
    def settings_ui(self):
        """The SettingsUI once it's built; None before the page was first opened."""
        return self._cc._settings if self._cc is not None else None

    def _on_group(self, group: str):
        """The sidebar's highlight follows the rail."""
        from ui import saintos_center as sc
        sidebar = getattr(self.window, "sidebar", None)
        key = "Halo" if group == sc.HALOS else "Settings"
        if sidebar is not None and sidebar.current() != key and key in sidebar.keys():
            sidebar.select(key, False)

    def _build(self):
        if self._cc is not None:
            return
        from ui import saintos_center as sc
        appearance = getattr(self.window, "apply_appearance", None)
        self._cc = sc.build_window("", os_pages=not sys.platform.startswith("win"),   # kept: it owns the callbacks
                                   on_appearance_changed=appearance, on_group_changed=self._on_group)
        panel = self._cc.takeCentralWidget()
        self.root.addWidget(panel, 1)
        self._nav = self._cc._nav
        if self.window is not None:
            sc.open_store = lambda: self.window.navigate("Store")

    def open(self, name: str):
        """Show one page of either group ("Recovery", "Voice", ...)."""
        self._pending = name
        if self.isVisible():
            self._select()

    def open_group(self, group: str):
        self._pending_group = group
        if self.isVisible():
            self._select()

    def _select(self):
        self._build()
        if self._pending_group:
            self._cc._open_group(self._pending_group)
        if self._pending:
            self._cc._open(self._pending)
        self._pending = self._pending_group = ""

    def _back(self):
        if self.window is not None:
            prev = getattr(self.window, "previous_page", "") or "Overview"
            self.window.navigate(prev if prev not in ("Halo", "Settings") else "Overview")

    def showEvent(self, e):
        super().showEvent(e)
        self._build()
        self._select()
        sidebar = getattr(self.window, "sidebar", None)
        if sidebar is not None and self._sidebar_was_collapsed is None:
            self._sidebar_was_collapsed = bool(getattr(sidebar, "_collapsed", False))
            sidebar.set_collapsed(True)

    def hideEvent(self, e):
        super().hideEvent(e)
        sidebar = getattr(self.window, "sidebar", None)
        if sidebar is not None and self._sidebar_was_collapsed is not None:
            sidebar.set_collapsed(self._sidebar_was_collapsed)
            self._sidebar_was_collapsed = None
