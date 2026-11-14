"""
ui/whats_new.py

What's new in HalOS. After the first login on a new version a small card pops up at the bottom right (it never
takes focus): "What's new in HalOS <version>" and the top highlights. A click opens the What's new page: every
highlight as a card over the drifting colour orbs (ui/orbs.py); click one to see what it does, how to use it and a
screenshot, and "Try it" opens the real page, app or action. Shown once per version (config whats_new.last_shown);
the page opens any time from the tray, Ctrl+K, or by saying "what's new".

The content is data/whats_new.json, edited without touching code (tests check every "try" exists):
    {"version": "2.3.0", "title": "What's new in HalOS 2.3",
     "cards": [{"icon": "sparkles",              an icon name from ui/icons.py
                "title": "...", "body": "...",   the card's one line
                "details": "...",                optional: shown when the card is opened
                "how": "...",                    optional: "How to use it" (newlines kept)
                "image": "docs/screenshots/...", optional: a screenshot shipped with SAINT
                "top": true,                     optional: listed in the popup (else the first three)
                "try": {"page": "Animations"} | {"action": "wallpapers.open", "params": {...}}}]}
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from core.config import config
from core.paths import resource_path
from ui.orbs import OrbBackground

log = logging.getLogger("saint.whats_new")
DATA = "data/whats_new.json"
SEEN_KEY = "whats_new.last_shown"
TOAST_W = 340
TOAST_ITEMS = 3
TOAST_MS = 25000                                      # the popup goes by itself after this

STYLE = """
QDialog { background: #f7f8fb; }
QLabel { color: #131417; background: transparent; }
QLabel#WnEyebrow { color: #5e626b; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#WnTitle { font-size: 24px; font-weight: 600; }
QLabel#WnBody { color: #3d4048; font-size: 14px; }
QFrame#WnCard { background: rgba(255, 255, 255, 0.72); border: 1px solid rgba(255, 255, 255, 0.9);
                border-radius: 22px; }
QLabel#WnIcon { background: rgba(127, 176, 255, 0.22); border-radius: 18px; }
QPushButton { border: none; border-radius: 16px; padding: 8px 18px; font-size: 13px; }
QPushButton#WnGhost { background: transparent; color: #5e626b; }
QPushButton#WnGhost:hover { color: #131417; background: rgba(0, 0, 0, 0.05); }
QPushButton#WnTry { background: rgba(19, 20, 23, 0.07); color: #131417; }
QPushButton#WnTry:hover { background: rgba(19, 20, 23, 0.12); }
QPushButton#WnNext { background: #131417; color: #ffffff; }
QPushButton#WnNext:hover { background: #2a2c31; }
QLabel#WnItemTitle { font-size: 15px; font-weight: 600; }
QLabel#WnChevron { color: #5e626b; font-size: 18px; }
QLabel#WnLink { color: #2f5fd0; font-size: 12px; font-weight: 600; }
QWidget#WnList, QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#WnToast { background: #f7f8fb; border: 1px solid rgba(19, 20, 23, 0.10); border-radius: 18px; }
"""


# --------------------------------------------------------------------------- data (tested)
def load(path: Optional[str] = None) -> dict:
    """The tour, or {} when the file is missing or broken (then nothing is shown)."""
    try:
        with open(path or resource_path(*DATA.split("/")), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        log.warning("whats_new.load_failed %s", type(e).__name__)
        return {}
    cards = [c for c in data.get("cards", []) if c.get("title")]
    return {**data, "cards": cards} if data.get("version") and cards else {}


def should_show(data: dict) -> bool:
    return bool(data) and str(config.get(SEEN_KEY, "") or "") != str(data["version"])


def mark_shown(data: dict):
    if data:
        config.set(SEEN_KEY, str(data["version"]))


def run_target(target: dict, open_page: Optional[Callable[[str], None]] = None):
    """Open what a card's "Try it" points at: a SAINT page (``open_page``, else `saint --page`) or an action
    (its ActionResult, so the card can say why it didn't work)."""
    from core import actions
    if target.get("page"):
        if open_page:
            open_page(target["page"])
        else:                                            # no SAINT window here: the running SAINT opens it
            from core.actions.sets import halos_apps as ha
            ha._spawn(ha._launcher("saint", str(ha.APP_ROOT / "app.py")) + ["--page", target["page"]])
        return True
    r = actions.execute(target["action"], target.get("params") or {}, source="gui")
    if not r.ok:
        log.info("whats_new.try_failed %s %s", target["action"], r.code)
    return r


# --------------------------------------------------------------------------- the What's new page
def image_of(card: dict) -> Optional[Path]:
    """A card's screenshot, if it names one that ships (a repo-relative path, no ..)."""
    rel = card.get("image")
    if not isinstance(rel, str) or not rel or ".." in rel.replace("\\", "/").split("/"):
        return None
    p = resource_path(*rel.replace("\\", "/").split("/"))
    return p if p.is_file() else None


class ItemCard(QFrame):
    """One highlight: icon, title and a line; a click opens its detail (what it does, how to use it, a screenshot)
    and its "Try it"."""

    def __init__(self, card: dict, open_page=None, parent=None):
        super().__init__(parent)
        self.card, self.open_page = card, open_page
        self.setObjectName("WnCard")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)
        head = QHBoxLayout()
        icon = QLabel()
        icon.setObjectName("WnIcon")
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignCenter)
        try:
            from ui.icons import pixmap
            icon.setPixmap(pixmap(card.get("icon") or "sparkles", "#2f5fd0", 20))
        except Exception:
            pass
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = QLabel(card["title"])
        self.title.setObjectName("WnItemTitle")
        self.title.setWordWrap(True)
        self.body = QLabel(card.get("body", ""))
        self.body.setObjectName("WnBody")
        self.body.setWordWrap(True)
        text.addWidget(self.title)
        text.addWidget(self.body)
        self.chevron = QLabel("›")
        self.chevron.setObjectName("WnChevron")
        head.addWidget(icon, 0, Qt.AlignTop)
        head.addSpacing(6)
        head.addLayout(text, 1)
        head.addWidget(self.chevron, 0, Qt.AlignVCenter)
        lay.addLayout(head)

        self.more = QWidget()
        more = QVBoxLayout(self.more)
        more.setContentsMargins(46, 4, 0, 0)
        more.setSpacing(8)
        if card.get("details"):
            d = QLabel(card["details"])
            d.setObjectName("WnBody")
            d.setWordWrap(True)
            more.addWidget(d)
        if card.get("how"):
            h = QLabel("<b>How to use it</b><br>" + html.escape(card["how"]).replace("\n", "<br>"))
            h.setObjectName("WnBody")
            h.setWordWrap(True)
            more.addWidget(h)
        self.shot = None
        img = image_of(card)
        if img:
            pm = QPixmap(str(img))
            if not pm.isNull():
                self.shot = QLabel()
                self.shot.setPixmap(pm.scaledToWidth(min(440, pm.width()), Qt.SmoothTransformation))
                more.addWidget(self.shot)
        self.try_btn = QPushButton(card.get("try_label") or "Try it")
        self.try_btn.setObjectName("WnTry")
        self.try_btn.setCursor(Qt.PointingHandCursor)
        self.try_btn.clicked.connect(self.try_it)
        self.try_btn.setVisible(bool(card.get("try")))
        more.addWidget(self.try_btn, 0, Qt.AlignLeft)
        self.status = QLabel()                           # why a "Try it" didn't work; it never fails silently
        self.status.setObjectName("WnBody")
        self.status.setWordWrap(True)
        more.addWidget(self.status)
        self.more.hide()
        lay.addWidget(self.more)

    def expanded(self) -> bool:
        return not self.more.isHidden()

    def set_expanded(self, on: bool):
        self.more.setVisible(on)
        self.chevron.setText("⌄" if on else "›")

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.set_expanded(not self.expanded())
        super().mouseReleaseEvent(ev)

    def try_it(self):
        target = self.card.get("try")
        if target:
            r = run_target(target, self.open_page)
            if r is not True and not r.ok:
                self.status.setText(r.error or r.message or "That didn't work.")


class WhatsNewDialog(QDialog):
    """Every highlight of this release as a card; click one to see more."""

    def __init__(self, data: dict, open_page: Optional[Callable[[str], None]] = None, parent=None):
        super().__init__(parent)
        self.data, self.open_page = data, open_page
        self.setWindowTitle(data.get("title") or "What's new")
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(680, 720)
        self.setStyleSheet(STYLE)
        self.orbs = OrbBackground(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 24)
        lay.setSpacing(14)
        eyebrow = QLabel(f"HALOS {data['version']}")
        eyebrow.setObjectName("WnEyebrow")
        title = QLabel(data.get("title") or "What's new")
        title.setObjectName("WnTitle")
        sub = QLabel("Click a card to see what it does and how to use it.")
        sub.setObjectName("WnBody")
        lay.addWidget(eyebrow)
        lay.addWidget(title)
        lay.addWidget(sub)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("WnList")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(10)
        self.items = [ItemCard(c, open_page) for c in data["cards"]]
        for it in self.items:
            col.addWidget(it)
        col.addStretch(1)
        area.setWidget(inner)
        lay.addWidget(area, 1)
        foot = QHBoxLayout()
        foot.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("WnNext")
        self.close_btn.clicked.connect(self.accept)
        foot.addWidget(self.close_btn)
        lay.addLayout(foot)

    def expand(self, i: int):
        """Open card ``i`` (and scroll to it); used by the popup to open on a highlight."""
        if 0 <= i < len(self.items):
            self.items[i].set_expanded(True)


# --------------------------------------------------------------------------- the popup after an update
class WhatsNewToast(QFrame):
    """A small card at the bottom right after the first login on a new version: "What's new in HalOS <ver>" and
    the top highlights. It never takes focus; a click opens the full page, × or a while closes it."""

    def __init__(self, data: dict, on_open: Callable[[], None]):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.on_open = on_open
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName("WnToast")
        self.setStyleSheet(STYLE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(TOAST_W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 12, 16)
        lay.setSpacing(6)
        head = QHBoxLayout()
        eyebrow = QLabel("WHAT’S NEW")
        eyebrow.setObjectName("WnEyebrow")
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("WnGhost")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("padding: 0; font-size: 16px;")
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self.close)
        head.addWidget(eyebrow, 1)
        head.addWidget(self.close_btn)
        lay.addLayout(head)
        self.title = QLabel(f"What's new in HalOS {data['version']}")
        self.title.setObjectName("WnItemTitle")
        lay.addWidget(self.title)
        top = [c for c in data["cards"] if c.get("top")] or data["cards"]
        self.lines = QLabel("\n".join(f"•  {c['title']}" for c in top[:TOAST_ITEMS]))
        self.lines.setObjectName("WnBody")
        self.lines.setWordWrap(True)
        lay.addWidget(self.lines)
        more = QLabel("Click to see everything")
        more.setObjectName("WnLink")
        lay.addWidget(more)
        self.adjustSize()
        QTimer.singleShot(TOAST_MS, self.close)

    def place(self):
        from ui import placement
        screen = placement.primary_screen() or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1280, 800)
        rect = QRect(area.right() - self.width() - 20, area.bottom() - self.height() - 20, self.width(), self.height())
        self.move(rect.topLeft())
        placement.wayland_place(self, rect, "SAINT notice")

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.close()
            self.on_open()
        super().mouseReleaseEvent(ev)


_open = []                                               # what's on screen, kept alive (no parent)


def open_page_dialog(data: dict, open_page=None, parent=None) -> WhatsNewDialog:
    dlg = WhatsNewDialog(data, open_page, parent)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    _open[:] = [w for w in _open if w.isVisible()] + [dlg]
    return dlg


def show(open_page: Optional[Callable[[str], None]] = None, parent: Optional[QWidget] = None,
         only_if_new: bool = False):
    """``only_if_new`` (after login): the popup, once per version. Otherwise (tray, Ctrl+K, "what's new", the
    popup's click) the full page. Marks this version as seen either way."""
    data = load()
    if not data or (only_if_new and not should_show(data)):
        return None
    mark_shown(data)                                     # once per version, even if it's closed unread
    if only_if_new:
        toast = WhatsNewToast(data, lambda: open_page_dialog(data, open_page, parent))
        toast.place()
        toast.show()
        _open[:] = [w for w in _open if w.isVisible()] + [toast]
        return toast
    return open_page_dialog(data, open_page, parent)
