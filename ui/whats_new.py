"""
ui/whats_new.py

The "What's new" tour: a few soft cards over the drifting colour orbs (ui/orbs.py), one per highlight of this
release, each with a "Try it" that opens the page or app through SAINT's own actions. Shown once per version after
login (config whats_new.last_shown), and any time from the tray, Ctrl+K, or by saying "what's new".

The text lives in data/whats_new.json so it can be edited without touching code:
    {"version": "2.1", "title": "...", "cards": [{"icon", "title", "body", "try": {"page": "Wallpaper"}
                                                   | {"action": "files.open", "params": {...}}}]}
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from core.config import config
from core.paths import resource_path
from ui import motion
from ui.orbs import OrbBackground

log = logging.getLogger("saint.whats_new")
DATA = "data/whats_new.json"
SEEN_KEY = "whats_new.last_shown"
SLIDE_PX = 36

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
QLabel#WnDot { background: rgba(19, 20, 23, 0.18); border-radius: 3px; }
QLabel#WnDotOn { background: #131417; border-radius: 3px; }
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
    """Open what a card's "Try it" points at: a SAINT page (``open_page``, else `saint --page`) or an action."""
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
    return r.ok


# --------------------------------------------------------------------------- the dialog
class WhatsNewDialog(QDialog):
    def __init__(self, data: dict, open_page: Optional[Callable[[str], None]] = None, parent=None):
        super().__init__(parent)
        self.data, self.open_page = data, open_page
        self.cards = data["cards"]
        self.index = 0
        self.setWindowTitle(data.get("title") or "What's new")
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(620, 440)
        self.setStyleSheet(STYLE)
        self.orbs = OrbBackground(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 28)
        lay.setSpacing(22)
        self.card = QFrame()
        self.card.setObjectName("WnCard")
        sp = self.card.sizePolicy()
        sp.setRetainSizeWhenHidden(True)                 # the layout doesn't jump while a card fades out
        self.card.setSizePolicy(sp)
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(32, 28, 32, 28)
        cl.setSpacing(12)
        head = QHBoxLayout()
        self.icon = QLabel()
        self.icon.setObjectName("WnIcon")
        self.icon.setFixedSize(56, 56)
        self.icon.setAlignment(Qt.AlignCenter)
        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("WnEyebrow")
        head.addWidget(self.icon)
        head.addSpacing(8)
        head.addWidget(self.eyebrow, 1, Qt.AlignVCenter)
        self.title = QLabel()
        self.title.setObjectName("WnTitle")
        self.title.setWordWrap(True)
        self.body = QLabel()
        self.body.setObjectName("WnBody")
        self.body.setWordWrap(True)
        self.body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.try_btn = QPushButton("Try it")
        self.try_btn.setObjectName("WnTry")
        self.try_btn.setCursor(Qt.PointingHandCursor)
        self.try_btn.clicked.connect(self.try_it)
        cl.addLayout(head)
        cl.addWidget(self.title)
        cl.addWidget(self.body, 1)
        cl.addWidget(self.try_btn, 0, Qt.AlignLeft)
        lay.addWidget(self.card, 1)

        foot = QHBoxLayout()
        self.skip = QPushButton("Skip")
        self.skip.setObjectName("WnGhost")
        self.skip.clicked.connect(self.reject)
        self.dots = QHBoxLayout()
        self.dots.setSpacing(6)
        self._dots = []
        for _ in self.cards:
            d = QLabel()
            d.setFixedSize(6, 6)
            self._dots.append(d)
            self.dots.addWidget(d)
        self.back = QPushButton("Back")
        self.back.setObjectName("WnGhost")
        self.back.clicked.connect(lambda: self.go(self.index - 1))
        self.next = QPushButton("Next")
        self.next.setObjectName("WnNext")
        self.next.setDefault(True)
        self.next.clicked.connect(self.forward)
        for w in (self.skip,):
            foot.addWidget(w)
        foot.addStretch(1)
        foot.addLayout(self.dots)
        foot.addStretch(1)
        foot.addWidget(self.back)
        foot.addWidget(self.next)
        lay.addLayout(foot)
        self._fill(0)

    def _fill(self, i: int):
        c = self.cards[i]
        try:
            from ui.icons import pixmap
            self.icon.setPixmap(pixmap(c.get("icon") or "sparkles", "#2f5fd0", 28))
        except Exception:
            self.icon.clear()
        self.eyebrow.setText(f"{(self.data.get('title') or 'WHAT’S NEW').upper()}  ·  {i + 1} / {len(self.cards)}")
        self.title.setText(c["title"])
        self.body.setText(c.get("body", ""))
        self.try_btn.setVisible(bool(c.get("try")))
        for n, d in enumerate(self._dots):
            d.setObjectName("WnDotOn" if n == i else "WnDot")
            d.setFixedWidth(16 if n == i else 6)
            d.style().polish(d)
        self.back.setVisible(i > 0)
        self.next.setText("Done" if i == len(self.cards) - 1 else "Next")

    def go(self, i: int):
        if not 0 <= i < len(self.cards) or i == self.index:
            return
        direction = 1 if i > self.index else -1
        self.index = i

        def swap():
            self._fill(i)
            motion.fade_in(self.card, motion.SLOW)
            if motion.enabled():
                end = self.card.pos()
                motion.animate(self.card, b"pos", end + QPoint(SLIDE_PX * direction, 0), end, motion.SLOW)
        if motion.enabled():
            motion.fade_out(self.card, motion.FAST, on_done=swap)
        else:
            swap()

    def forward(self):
        if self.index >= len(self.cards) - 1:
            self.accept()
        else:
            self.go(self.index + 1)

    def try_it(self):
        target = self.cards[self.index].get("try")
        if target:
            run_target(target, self.open_page)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self.forward()
        elif ev.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.go(self.index - 1)
        else:
            super().keyPressEvent(ev)


def show(open_page: Optional[Callable[[str], None]] = None, parent: Optional[QWidget] = None,
         only_if_new: bool = False) -> Optional[WhatsNewDialog]:
    """Open the tour (marks this version as seen). ``only_if_new``: only when this version hasn't been shown."""
    data = load()
    if not data or (only_if_new and not should_show(data)):
        return None
    mark_shown(data)                                     # once per version, even if it's skipped or closed
    dlg = WhatsNewDialog(data, open_page, parent)
    dlg.show()
    motion.fade_in(dlg.card, motion.SLOW, dy=12)
    return dlg
