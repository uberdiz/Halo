"""
ui/components/side_rail.py

The left rail every HalOS app uses (Task Manager, Settings): an orange eyebrow with the app's family,
the app's name, one list of pages with icons, and an optional footer line. Styled by ui/theme.py
(#SideRail, #SideNav, #RailEyebrow, #RailTitle, #RailFoot), so the apps look like one system.

A page whose icon is "" is a group heading: it can't be selected and keyboard navigation skips it. ``search``
adds a filter box above the list (connect to ``self.search.textChanged``).
"""

from typing import Iterable, Optional, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class SideRail(QFrame):
    def __init__(self, eyebrow: str, title: str, pages: Iterable[Tuple[str, str]], width: int = 210,
                 footer: str = "", search: bool = False):
        super().__init__()
        self.setObjectName("SideRail")
        self.setFixedWidth(width)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        eb = QLabel(eyebrow.upper())
        eb.setObjectName("RailEyebrow")
        f = eb.font()
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.6)
        eb.setFont(f)
        v.addWidget(eb)
        t = QLabel(title)
        t.setObjectName("RailTitle")
        v.addWidget(t)
        self.search = None
        if search:
            self.search = QLineEdit()
            self.search.setObjectName("RailSearch")
            self.search.setPlaceholderText("Search settings…")
            v.addWidget(self.search)
        self.nav = QListWidget()
        self.nav.setObjectName("SideNav")
        self.nav.setIconSize(QSize(16, 16))
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # a long name elides; the rail doesn't side-scroll
        self.nav.setTextElideMode(Qt.ElideRight)
        self._icons = {}
        for name, icon in pages:
            item = QListWidgetItem(name)
            self._icons[name] = icon
            if not icon:                               # a group heading
                item.setFlags(Qt.NoItemFlags)
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self.nav.addItem(item)
        v.addWidget(self.nav, 1)
        self.foot = QLabel(footer)
        self.foot.setObjectName("RailFoot")
        self.foot.setWordWrap(True)
        self.foot.setVisible(bool(footer))
        v.addWidget(self.foot)
        self.nav.currentRowChanged.connect(self._paint_icons)
        self._paint_icons()

    def _paint_icons(self, _row: Optional[int] = None):
        """Icons in the muted colour, the current page's in SAINT orange."""
        try:
            from ui import icons
            from ui.theme import current_palette
            p = current_palette()
        except Exception:
            return
        for i in range(self.nav.count()):
            item = self.nav.item(i)
            name = self._icons.get(item.text())
            if name:
                item.setIcon(icons.icon(name, p.accent if i == self.nav.currentRow() else p.muted, 16))

    def set_footer(self, text: str):
        self.foot.setText(text)
        self.foot.setVisible(bool(text))
