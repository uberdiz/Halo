"""
ui/components/store_tiles.py

The Store's pieces: an art loader (icons and screenshots from core/store_art.py, fetched off the GUI thread
and cached on disk), app cards with a screenshot preview in a grid that reflows with the window, the full-bleed
featured banner, and an app's own page. Artwork is the publisher's own (AppStream); an app without any shows a
tile in its brand colour (else one derived from its name) with its icon or initial.
"""

import html
import zlib
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from ui.theme import current_palette
from ui.widgets import chip

TILE_W, TILE_H = 250, 280
PREVIEW_H = 128


class ArtLoader(QObject):
    """One per process. ``loaded(key, kind, path, meta)``: kind is "icon", "thumb" (a card's preview), "hero" (a
    full-width screenshot), "shot" or "meta" (the facts only, no image); path "" when there's none.

    What a person is looking at (``priority``: the featured banner, an app's page) has its own workers, so it
    doesn't wait behind a page of cards."""
    loaded = Signal(str, str, str, dict)
    _instance = None
    _URLS = {"icon": ("icon",), "thumb": ("thumb", "screenshot"), "hero": ("hero", "screenshot"), "shot": ("screenshot",)}

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = ArtLoader()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="store-art")
        self._first = ThreadPoolExecutor(max_workers=3, thread_name_prefix="store-art-first")
        self._done = {}                               # (key, kind) -> (path, meta)
        self._pending = set()

    def request(self, key: str, kind: str, flathub_id: str = "", url: str = "", lookup: str = "",
                any_host: bool = False, priority: bool = False):
        from core.config import config
        if not key or not config.get("store.artwork", True):
            return
        if (key, kind) in self._done:
            path, meta = self._done[(key, kind)]
            QTimer.singleShot(0, lambda: self.loaded.emit(key, kind, path, meta))
            return
        if (key, kind) in self._pending:
            return
        self._pending.add((key, kind))
        (self._first if priority else self._pool).submit(self._work, key, kind, flathub_id, url, lookup, any_host)

    def _work(self, key, kind, flathub_id, url, lookup, any_host):
        from core import store_art
        meta, path = {}, None
        try:
            # A Flathub listing already names the app's icon: no metadata request per card just for that.
            if (flathub_id or lookup) and not (kind == "icon" and url):
                meta = store_art.app_metadata(flathub_id, lookup)
            any_host = any_host or bool(meta.get("local"))
            if kind == "icon" and meta.get("icon_path"):
                path = meta["icon_path"]
            elif kind != "meta":
                for u in ([url] if url else [meta.get(k) for k in self._URLS.get(kind, ())]):
                    path = u and store_art.image(u, any_host=any_host)
                    if path:
                        break
        except Exception:
            path = None
        meta = {k: v for k, v in (meta or {}).items() if not k.startswith("_")}
        if path or meta:                              # a failure may be the network: the next visit tries again
            self._done[(key, kind)] = (path or "", meta)
        self._pending.discard((key, kind))
        from PySide6.QtCore import QCoreApplication
        if QCoreApplication.instance() is not None and not QCoreApplication.closingDown():
            self.loaded.emit(key, kind, path or "", meta)


def rounded(pix: QPixmap, size: int, radius: float) -> QPixmap:
    out = QPixmap(size * 2, size * 2)
    out.setDevicePixelRatio(2.0)
    out.fill(Qt.transparent)
    g = QPainter(out)
    g.setRenderHint(QPainter.Antialiasing)
    g.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    g.setClipPath(path)
    scaled = pix.scaled(size * 2, size * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    x, y = (size - scaled.width() / 2) / 2, (size - scaled.height() / 2) / 2         # centred, if it isn't square
    g.drawPixmap(QRectF(x, y, scaled.width() / 2, scaled.height() / 2), scaled, QRectF(scaled.rect()))
    g.end()
    return out


def monogram(name: str, size: int) -> QPixmap:
    """The app's initial on a tinted square: shown when there's no real icon (never a made-up logo)."""
    p = current_palette()
    out = QPixmap(size * 2, size * 2)
    out.setDevicePixelRatio(2.0)
    out.fill(Qt.transparent)
    g = QPainter(out)
    g.setRenderHint(QPainter.Antialiasing)
    g.setPen(Qt.NoPen)
    g.setBrush(QColor(p.accent_soft))
    g.drawRoundedRect(QRectF(0, 0, size, size), size * 0.24, size * 0.24)
    f = QFont()
    f.setPixelSize(int(size * 0.46))
    f.setWeight(QFont.DemiBold)
    g.setFont(f)
    g.setPen(QColor(p.accent))
    g.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, (name.strip()[:1] or "?").upper())
    g.end()
    return out


def bundled_icon(result):
    """The icon shipped with SAINT for an app that has no Flathub entry (data/store-icons), or None."""
    rel = (result.extra or {}).get("icon_file")
    if not rel:
        return None
    from core.paths import resource_path
    path = resource_path(*rel.split("/"))
    pix = QPixmap(str(path)) if path.is_file() else QPixmap()
    return None if pix.isNull() else pix


def art_key(result):
    """(key, flathub id, direct icon url, name to look it up by) for a Store result."""
    from core.store_art import flathub_id
    fid = flathub_id(result) or ""
    url = (result.extra or {}).get("icon", "")
    lookup = "" if fid else (result.id if result.source in ("repo", "aur") else result.name)
    return (fid or url or f"{result.source}:{result.id}"), fid, url, lookup


def fallback_colour(name: str, meta=None) -> QColor:
    """A tile's colour when there's no screenshot: the app's brand colour, else one of its own derived from its
    name (the same every time, and different between apps)."""
    p = current_palette()
    brand = (meta or {}).get("brand_dark" if p.dark else "brand_light")
    if brand and QColor(brand).isValid():
        return QColor(brand)
    return QColor.fromHsl(zlib.crc32(name.encode("utf-8", "replace")) % 360, 90, 62 if p.dark else 200)


def cover(pix: QPixmap, w: int, h: int, dpr: float) -> QPixmap:
    """``pix`` filling w x h (device-independent), cropped around its centre, ready to paint at that size."""
    tw, th = max(1, int(w * dpr)), max(1, int(h * dpr))
    scaled = pix.scaled(tw, th, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = scaled.copy((scaled.width() - tw) // 2, (scaled.height() - th) // 2, tw, th)
    out.setDevicePixelRatio(dpr)
    return out


class ShotCanvas(QWidget):
    """A screenshot filling this widget, or the app's fallback tile: its colour with its icon in the middle."""

    def __init__(self, name: str, radius: float = 14, top_only: bool = False, icon_size: int = 64):
        super().__init__()
        self.name, self.radius, self.top_only, self.icon_size = name, radius, top_only, icon_size
        self.shot = None
        self.icon = None
        self.meta = {}
        self._cover = None

    def set_shot(self, pix: QPixmap):
        self.shot = pix
        self._cover = None
        self.update()

    def set_icon(self, pix: QPixmap):
        self.icon = pix
        if self.shot is None:
            self.update()

    def set_meta(self, meta):
        self.meta = meta or {}
        if self.shot is None:
            self.update()

    def resizeEvent(self, e):
        self._cover = None
        super().resizeEvent(e)

    def _clip(self) -> QPainterPath:
        w, h, r = self.width(), self.height(), self.radius
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h + (r if self.top_only else 0)), r, r)
        return path

    def paintEvent(self, _):
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.setRenderHint(QPainter.SmoothPixmapTransform)
        g.setClipPath(self._clip())
        if self.shot is not None:
            if self._cover is None:
                self._cover = cover(self.shot, self.width(), self.height(), self.devicePixelRatioF())
            g.drawPixmap(0, 0, self._cover)
        else:
            base = fallback_colour(self.name, self.meta)
            fill = QLinearGradient(QPointF(0, 0), QPointF(self.width(), self.height()))
            fill.setColorAt(0, base.lighter(125))
            fill.setColorAt(1, base.darker(120))
            g.fillRect(self.rect(), fill)
            s = self.icon_size
            x, y = (self.width() - s) / 2, (self.height() - s) / 2
            icon = self.icon if self.icon is not None else monogram(self.name, s)
            g.drawPixmap(QRectF(x, y, s, s), icon, QRectF(icon.rect()))
        self._decorate(g)
        g.end()

    def _decorate(self, g):
        pass


class AppTile(QFrame):
    """One app: its screenshot, icon, name, developer, summary, where it comes from, and its action. Clicking the
    card (not its button) opens the app's own page when ``on_details`` is given."""
    ICON = 40

    def __init__(self, result, on_install, on_open=None, on_details=None):
        super().__init__()
        self.result = result
        self._on_details = on_details
        self._on_install = on_install
        self._on_open = on_open
        self._installed = False
        if on_details:
            self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("StoreTile")
        self.setFixedSize(TILE_W, TILE_H)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 0)                     # inside the card's border
        outer.setSpacing(0)
        self.preview = ShotCanvas(result.name, radius=13, top_only=True, icon_size=56)
        self.preview.setFixedSize(TILE_W - 2, PREVIEW_H)
        outer.addWidget(self.preview)
        v = QVBoxLayout()
        v.setContentsMargins(13, 10, 13, 12)
        v.setSpacing(5)
        outer.addLayout(v, 1)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.icon = QLabel()
        self.icon.setFixedSize(self.ICON, self.ICON)
        self.icon.setPixmap(monogram(result.name, self.ICON))
        top.addWidget(self.icon, 0, Qt.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.name = QLabel(result.name)
        self.name.setObjectName("TileName")
        self.name.setTextFormat(Qt.PlainText)                    # names and summaries come from the network
        self.dev = QLabel((result.extra or {}).get("developer", "") or "")
        self.dev.setObjectName("Faint")
        self.dev.setTextFormat(Qt.PlainText)
        for label in (self.name, self.dev):
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)   # a long name is cut, not a wider card
        names.addWidget(self.name)
        names.addWidget(self.dev)
        names.addStretch()
        top.addLayout(names, 1)
        v.addLayout(top)
        self.about = QLabel(result.summary or "")
        self.about.setObjectName("Muted")
        self.about.setTextFormat(Qt.PlainText)
        self.about.setWordWrap(True)
        self.about.setMaximumHeight(36)
        self.about.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        v.addWidget(self.about, 1)
        bottom = QHBoxLayout()
        from core.store import compatibility
        compat = compatibility(result)
        bottom.addWidget(chip("Won't work" if compat == "blocked" else result.label,
                              "err" if compat == "blocked" else "accent" if result.source == "featured" else ""))
        if result.source == "aur":
            e = result.extra
            bottom.addWidget(chip(f"{e.get('votes', 0)} votes", "warn" if e.get("out_of_date") else ""))
        bottom.addStretch()
        self.action = QPushButton("Install")
        self.action.setObjectName("TileAction")
        self.action.clicked.connect(self._clicked)
        self._blocked = (result.extra or {}).get("blocked", "")
        if self._blocked:
            self.action.setText("Linux version" if (result.extra or {}).get("instead") else "Won't work")
            self.action.setEnabled(bool((result.extra or {}).get("instead")))
            self.action.setToolTip(self._blocked)
            self.setToolTip(self._blocked)
        bottom.addWidget(self.action)
        v.addLayout(bottom)
        self._key, fid, url, lookup = art_key(result)
        own = bundled_icon(result)
        if own is not None:
            self.icon.setPixmap(rounded(own, self.ICON, self.ICON * 0.22))
            self.preview.set_icon(rounded(own, 56, 56 * 0.22))
        loader = ArtLoader.get()
        loader.loaded.connect(self._art)
        if own is None:
            loader.request(self._key, "icon", fid, url, lookup)
        loader.request(self._key, "thumb", fid, "", lookup)

    def mouseReleaseEvent(self, e):
        if self._on_details and e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self._on_details(self.result)
        super().mouseReleaseEvent(e)

    def _clicked(self):
        if self._installed and self._on_open:
            self._on_open(self.result)
        else:
            self._on_install(self.result)

    def _art(self, key, kind, path, meta):
        if key != self._key or kind not in ("icon", "thumb"):
            return
        try:
            pix = QPixmap(path) if path else QPixmap()
            if kind == "thumb":
                if not pix.isNull():
                    self.preview.set_shot(pix)
                self.preview.set_meta(meta)
                return
            if not pix.isNull():
                self.icon.setPixmap(rounded(pix, self.ICON, self.ICON * 0.22))
                self.preview.set_icon(rounded(pix, 56, 56 * 0.22))
            if meta.get("developer") and not self.dev.text():
                self.dev.setText(meta["developer"])
            if meta.get("summary") and not self.about.text():
                self.about.setText(meta["summary"])
        except RuntimeError:                          # the tile was deleted while the art loaded
            pass

    def set_installed(self, installed: bool, busy: str = ""):
        """Whatever the app's state is now, in either direction: Install, Open / Installed, or what's happening."""
        self._installed = bool(installed)
        if self._blocked and not installed:
            return
        self._busy = busy
        name = "TileOpen" if (installed or busy) else "TileAction"
        self.action.setText(busy or (("Open" if self._on_open else "Installed") if installed else "Install"))
        self.action.setEnabled(not busy and (not installed or bool(self._on_open)))
        state = "busy" if busy else ""
        if self.action.objectName() != name or (self.action.property("state") or "") != state:
            self.action.setObjectName(name)
            self.action.setProperty("state", state)
            self.action.style().unpolish(self.action)
            self.action.style().polish(self.action)

    def flash(self, state: str, text: str, ms: int = 2400):
        """Say what the button's work came to ("busy", "done" or "failed"), then go back to the app's real state."""
        flash_action(self, self.action, state, text, ms)


def flash_action(owner, button, state: str, text: str, ms: int = 2400):
    """Show ``state`` on an app's action button; when it isn't "busy", the owner's set_installed puts it back."""
    from PySide6.QtCore import QTimer
    button.setProperty("state", state)
    button.setText(text)
    button.setEnabled(state != "busy")
    button.style().unpolish(button)
    button.style().polish(button)
    owner._flash_serial = getattr(owner, "_flash_serial", 0) + 1
    serial = owner._flash_serial
    if state == "busy":
        return

    def back():
        try:
            if owner._flash_serial == serial:
                button.setProperty("state", "")
                owner.set_installed(getattr(owner, "_installed", False) or getattr(owner.result, "installed", False),
                                    getattr(owner, "_busy", "") or getattr(owner, "busy", ""))
        except RuntimeError:                          # the tile is gone
            pass
    QTimer.singleShot(ms, back)


class TileGrid(QWidget):
    """Tiles in as many columns as fit; reflows when the page is resized. ``append`` adds to the end without
    touching what's there, so a long list grows as it's scrolled."""

    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.grid.setSizeConstraint(QLayout.SetNoConstraint)     # a row of tiles mustn't stop the window narrowing
        self.tiles = []
        self._cols = 0
        self.max_rows = 0                             # 0 = all; a shelf on the front page shows one row
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def minimumSizeHint(self):
        return QSize(TILE_W, self.minimumHeight())

    def sizeHint(self):
        return QSize(TILE_W, self.minimumHeight())

    def set_tiles(self, tiles, max_rows: int = 0):
        self.tiles = tiles
        self.max_rows = max_rows
        self._cols = 0
        self._reflow()

    def append(self, tiles):
        start = len(self.tiles)
        self.tiles = self.tiles + list(tiles)
        if not self._cols or self.max_rows:
            self._cols = 0
            self._reflow()
            return
        for i, t in enumerate(tiles, start):
            t.setParent(self)
            t.show()
            self.grid.addWidget(t, i // self._cols, i % self._cols, Qt.AlignLeft | Qt.AlignTop)
        self._fit(len(self.tiles))

    def clear(self):
        while self.grid.count():
            self.grid.takeAt(0)
        for t in self.tiles:
            t.hide()
            t.setParent(None)
            t.deleteLater()
        self.tiles = []
        self.setMinimumHeight(0)

    def _fit(self, shown: int):
        rows = (shown + self._cols - 1) // self._cols
        self.setMinimumHeight(rows * TILE_H + max(0, rows - 1) * 14)

    def _reflow(self):
        cols = max(1, (self.width() + 14) // (TILE_W + 14))
        if cols == self._cols:
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        shown = self.tiles[:cols * self.max_rows] if self.max_rows else self.tiles
        for t in self.tiles:
            t.setParent(self)                         # also the ones past the last row: a wider window shows them
        for t in self.tiles[len(shown):]:
            t.hide()
        for i, t in enumerate(shown):
            t.show()
            self.grid.addWidget(t, i // cols, i % cols, Qt.AlignLeft | Qt.AlignTop)
        for c in range(self.grid.columnCount()):
            self.grid.setColumnStretch(c, 0)
        self.grid.setColumnStretch(cols, 1)
        self._fit(len(shown))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow()


class HeroBanner(QFrame):
    """The featured app: its real screenshot edge to edge, darkened where the words sit, with its name, maker and
    action. Clicking it opens the app's page. Rotates through ``results`` every 9 s; the dots jump to one. Until
    a screenshot has loaded (or if an app has none) the banner is the app's brand colour."""

    def __init__(self, results, on_install, on_details=None, on_open=None):
        super().__init__()
        self.busy_of = None                           # result -> "Installing…" / "" (the page's queue)
        self.setObjectName("StoreHero")
        self.setFixedHeight(340)
        self.results = results
        self.on_install = on_install
        self.on_details = on_details
        self.on_open = on_open
        if on_details:
            self.setCursor(Qt.PointingHandCursor)
        self.i = 0
        self.shots, self.brand = {}, {}
        self._covers = {}
        h = QHBoxLayout(self)
        h.setContentsMargins(34, 28, 34, 24)
        col = QVBoxLayout()
        col.setSpacing(6)
        self.eyebrow = QLabel("FEATURED")
        self.eyebrow.setObjectName("RailEyebrow")
        self.eyebrow.setStyleSheet("padding: 0px;")
        f = self.eyebrow.font()
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.8)
        self.eyebrow.setFont(f)
        col.addWidget(self.eyebrow)
        col.addStretch()
        head = QHBoxLayout()
        head.setSpacing(16)
        self.icon = QLabel()
        self.icon.setFixedSize(72, 72)
        head.addWidget(self.icon, 0, Qt.AlignVCenter)
        names = QVBoxLayout()
        names.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("HeroTitle")
        self.title.setTextFormat(Qt.PlainText)
        self.dev = QLabel()
        self.dev.setObjectName("HeroDev")
        self.dev.setTextFormat(Qt.PlainText)
        names.addWidget(self.title)
        names.addWidget(self.dev)
        head.addLayout(names)
        head.addStretch()
        col.addLayout(head)
        self.about = QLabel()
        self.about.setObjectName("HeroAbout")
        self.about.setTextFormat(Qt.PlainText)
        self.about.setWordWrap(True)
        self.about.setMaximumWidth(460)
        col.addSpacing(4)
        col.addWidget(self.about)
        col.addSpacing(10)
        row = QHBoxLayout()
        self.install = QPushButton("Install")
        self.install.setObjectName("Primary")
        self.install.clicked.connect(self._clicked)
        row.addWidget(self.install)
        self.dots = QHBoxLayout()
        self.dots.setSpacing(6)
        self._dots = []
        for n in range(len(results)):
            d = QPushButton()
            d.setObjectName("HeroDot")
            d.setFixedSize(QSize(8, 8))
            d.setCursor(Qt.PointingHandCursor)
            d.clicked.connect(lambda _=False, k=n: self.show_index(k))
            self.dots.addWidget(d)
            self._dots.append(d)
        row.addSpacing(16)
        row.addLayout(self.dots)
        row.addStretch()
        col.addLayout(row)
        h.addLayout(col)
        h.addStretch(1)
        self.icons = {}
        loader = ArtLoader.get()
        loader.loaded.connect(self._art)
        for r in results:
            key, fid, url, lookup = art_key(r)
            loader.request(key, "hero", fid, "", lookup, priority=True)
            loader.request(key, "icon", fid, url, lookup, priority=True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.show_index((self.i + 1) % max(1, len(self.results))))
        self.timer.start(9000)
        self.show_index(0)

    def _clicked(self):
        r = self.results[self.i]
        if r.installed and self.on_open:
            self.on_open(r)
        else:
            self.on_install(r)

    def mouseReleaseEvent(self, e):
        if self.on_details and self.results and e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.on_details(self.results[self.i])
        super().mouseReleaseEvent(e)

    def resizeEvent(self, e):
        self.setFixedHeight(max(320, min(480, int(self.width() * 0.36))))    # wide windows get a wide picture
        self._covers = {}
        super().resizeEvent(e)

    def refresh(self):
        """The action follows the app's state."""
        if self.results:
            self.show_index(self.i)

    def show_index(self, i):
        if not self.results:
            return
        self.i = i
        r = self.results[i]
        key = art_key(r)[0]
        self.title.setText(r.name)
        cat = (r.extra or {}).get("category", "")
        self.eyebrow.setText("FEATURED" + (f"  ·  {cat.upper()}" if cat else ""))
        icon = self.icons.get(key) or bundled_icon(r)
        self.icon.setPixmap(rounded(icon, 72, 16) if icon is not None else monogram(r.name, 72))
        meta = self.brand.get(key, {})
        self.dev.setText(meta.get("developer") or r.label)
        self.about.setText(r.summary or meta.get("summary", ""))
        busy = self.busy_of(r) if self.busy_of else ""
        self.install.setText(busy or (("Open" if self.on_open else "Installed") if r.installed else "Install"))
        self.install.setEnabled(not busy and (not r.installed or bool(self.on_open)))
        if (self.install.property("state") or "") != ("busy" if busy else ""):
            self.install.setProperty("state", "busy" if busy else "")
            self.install.style().unpolish(self.install)
            self.install.style().polish(self.install)
        for n, d in enumerate(self._dots):
            d.setProperty("on", n == i)
            d.style().unpolish(d)
            d.style().polish(d)
        # Light words: a screenshot gets a dark scrim behind them, and dark-enough brand colours need nothing.
        light = key in self.shots or self._base().lightness() < 140
        ink = "#f4f5f7" if light else "#131417"
        soft = "rgba(244,245,247,0.78)" if light else "rgba(19,20,23,0.68)"
        self.title.setStyleSheet(f"color: {ink}; font-size: 34px; font-weight: 700;")
        self.dev.setStyleSheet(f"color: {soft}; font-size: 13px;")
        self.about.setStyleSheet(f"color: {ink}; font-size: 14px;")
        self.timer.start(9000)
        self.update()

    def _base(self) -> QColor:
        """The banner colour without a screenshot: the app's own brand colour for this theme, else SAINT's surface."""
        p = current_palette()
        key = art_key(self.results[self.i])[0] if self.results else ""
        meta = self.brand.get(key, {})
        base = QColor((meta.get("brand_dark") if p.dark else meta.get("brand_light")) or p.surface)
        return base.darker(115) if p.dark and base.lightness() > 90 else base

    def _art(self, key, kind, path, meta):
        try:
            if kind == "icon":
                if path and not QPixmap(path).isNull():
                    self.icons[key] = QPixmap(path)
                    if self.results and art_key(self.results[self.i])[0] == key:
                        self.show_index(self.i)
                return
            if kind != "hero" or not any(art_key(r)[0] == key for r in self.results):
                return
            self.brand[key] = meta
            if path:
                pix = QPixmap(path)
                if not pix.isNull():
                    self.shots[key] = pix
            if self.results and art_key(self.results[self.i])[0] == key:
                self.show_index(self.i)
        except RuntimeError:
            pass

    def paintEvent(self, _):
        p = current_palette()
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(r, 16, 16)
        g.setClipPath(clip)
        key = art_key(self.results[self.i])[0] if self.results else ""
        shot = self.shots.get(key)
        if shot is not None:
            pic = self._covers.get(key)
            if pic is None:
                pic = self._covers[key] = cover(shot, self.width(), self.height(), self.devicePixelRatioF())
            g.drawPixmap(0, 0, pic)
            # A scrim where the words are, whatever colours the screenshot happens to have.
            side = QLinearGradient(QPointF(0, 0), QPointF(r.width() * 0.72, 0))
            side.setColorAt(0, QColor(8, 9, 12, 225))
            side.setColorAt(0.55, QColor(8, 9, 12, 120))
            side.setColorAt(1, QColor(8, 9, 12, 0))
            g.fillRect(r, side)
            under = QLinearGradient(QPointF(0, r.height()), QPointF(0, r.height() * 0.45))
            under.setColorAt(0, QColor(8, 9, 12, 150))
            under.setColorAt(1, QColor(8, 9, 12, 0))
            g.fillRect(r, under)
        else:
            base = self._base()
            g.fillRect(r, base)
            glow = QRadialGradient(QPointF(r.width() * 0.72, r.height() * 0.5), r.width() * 0.45)
            lit = QColor(base).lighter(170)
            lit.setAlpha(110)
            glow.setColorAt(0, lit)
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            g.fillRect(r, glow)
        g.setClipping(False)
        g.setPen(QColor(p.border))
        g.drawRoundedRect(r, 16, 16)


class DetailHero(ShotCanvas):
    """An app page's full-width screenshot. Its height follows its width, up to a limit."""

    def __init__(self, name):
        super().__init__(name, radius=16, icon_size=96)
        self.setFixedHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def resizeEvent(self, e):
        self.setFixedHeight(max(220, min(440, int(self.width() * 0.46))))    # the action stays above the fold
        super().resizeEvent(e)


class _Thumb(QLabel):
    def __init__(self, on_click):
        super().__init__()
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("StoreShot")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._on_click()
        super().mouseReleaseEvent(e)


class AppDetails(QWidget):
    """One app's own page: Back, a full-width screenshot, its icon, name, developer, what it is, Install / Open /
    Uninstall, a gallery (click one to see it large), its description, where it comes from and how it runs, and
    apps like it. All from AppStream metadata: what the metadata doesn't say isn't shown."""
    THUMB_H = 150

    def __init__(self, result, on_install, on_back, on_open=None, on_uninstall=None):
        super().__init__()
        from core import store
        self.result = result
        self.on_open, self.on_uninstall, self.on_install = on_open, on_uninstall, on_install
        self.busy = ""
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 10, 14)
        v.setSpacing(14)
        back = QPushButton("←  Back")
        back.setObjectName("ShelfMore")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(on_back)
        v.addWidget(back, 0, Qt.AlignLeft)
        self.hero = DetailHero(result.name)
        v.addWidget(self.hero)
        head = QHBoxLayout()
        head.setSpacing(16)
        self.icon = QLabel()
        self.icon.setFixedSize(84, 84)
        own = bundled_icon(result)
        self.icon.setPixmap(rounded(own, 84, 19) if own is not None else monogram(result.name, 84))
        if own is not None:
            self.hero.set_icon(rounded(own, 96, 22))
        head.addWidget(self.icon, 0, Qt.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(3)
        title = QLabel(result.name)
        title.setObjectName("StoreHeadline")
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        self.dev = QLabel((result.extra or {}).get("developer", "") or "")
        self.dev.setObjectName("Muted")
        self.dev.setTextFormat(Qt.PlainText)
        self.about = QLabel(result.summary or "")
        self.about.setTextFormat(Qt.PlainText)
        self.about.setWordWrap(True)
        names.addWidget(title)
        names.addWidget(self.dev)
        names.addWidget(self.about)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(6)
        compat = store.compatibility(result)
        self.chips.addWidget(chip(result.label, "accent" if result.source == "featured" else ""))
        self.chips.addWidget(chip(store.COMPAT_LABEL[compat], "err" if compat == "blocked" else ""))
        if result.version:
            self.chips.addWidget(chip(result.version))
        self.chips.addStretch()
        names.addLayout(self.chips)
        head.addLayout(names, 1)
        buttons = QVBoxLayout()
        buttons.setSpacing(6)
        self.action = QPushButton("Install")
        self.action.setObjectName("Primary")
        self.action.setMinimumWidth(120)
        self.action.clicked.connect(self._clicked)
        self.remove = QPushButton("Uninstall")
        self.remove.setObjectName("Ghost")
        self.remove.clicked.connect(lambda: self.on_uninstall and self.on_uninstall(self.result))
        self.remove.hide()
        buttons.addWidget(self.action)
        buttons.addWidget(self.remove)
        buttons.addStretch()
        head.addLayout(buttons)
        v.addLayout(head)
        self._blocked = (result.extra or {}).get("blocked", "")
        if self._blocked:
            self.action.setText("Linux version" if (result.extra or {}).get("instead") else "Won't work")
            self.action.setEnabled(bool((result.extra or {}).get("instead")))
            why = QLabel(self._blocked)
            why.setObjectName("Muted")
            why.setTextFormat(Qt.PlainText)
            why.setWordWrap(True)
            v.addWidget(why)
        self.gallery_box = QScrollArea()
        self.gallery_box.setWidgetResizable(True)
        self.gallery_box.setFrameShape(QScrollArea.NoFrame)
        self.gallery_box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.gallery_box.setFixedHeight(self.THUMB_H + 16)
        inner = QWidget()
        self.gallery = QHBoxLayout(inner)
        self.gallery.setContentsMargins(0, 0, 0, 0)
        self.gallery.setSpacing(12)
        self.gallery_box.setWidget(inner)
        self.gallery_box.hide()
        v.addWidget(self.gallery_box)
        self.description = QLabel("")
        self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.RichText)
        self.description.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.description.setMaximumWidth(860)
        self.description.hide()
        v.addWidget(self.description)
        self.source = QLabel("")
        self.source.setObjectName("Muted")
        self.source.setWordWrap(True)
        self.source.setTextFormat(Qt.RichText)
        self.source.setOpenExternalLinks(True)
        self.source.setTextInteractionFlags(Qt.TextBrowserInteraction)
        v.addWidget(self.source)
        self.no_shots = QLabel("")
        self.no_shots.setObjectName("Faint")
        v.addWidget(self.no_shots)
        self.similar_title = QLabel("Apps like this")
        self.similar_title.setObjectName("ShelfTitle")
        self.similar_title.hide()
        v.addWidget(self.similar_title)
        self.similar = TileGrid()
        v.addWidget(self.similar)
        v.addStretch()
        self.shots, self.large = [], []
        self.selected = 0
        self._meta_facts = {}
        self._any_host = False
        self._show_source()
        self._key, self._fid, url, self._lookup = art_key(result)
        loader = ArtLoader.get()
        loader.loaded.connect(self._art)
        if own is None:
            loader.request(self._key, "icon", self._fid, url, self._lookup, priority=True)
        loader.request(self._key, "hero", self._fid, "", self._lookup, priority=True)
        loader.request(self._key, "meta", self._fid, "", self._lookup, priority=True)
        self.set_installed(result.installed)

    def _clicked(self):
        from core import store
        if self.result.installed and self.on_open and store.openable(self.result):
            self.on_open(self.result)
        else:
            self.on_install(self.result)

    def set_installed(self, installed: bool, busy: str = ""):
        from core import store
        self.busy = busy
        if self._blocked and not installed:
            return
        can_open = bool(self.on_open) and store.openable(self.result)
        self.action.setText(busy or (("Open" if can_open else "Installed") if installed else "Install"))
        self.action.setEnabled(not busy and (not installed or can_open))
        if (self.action.property("state") or "") != ("busy" if busy else ""):
            self.action.setProperty("state", "busy" if busy else "")
            self.action.style().unpolish(self.action)
            self.action.style().polish(self.action)
        self.remove.setVisible(bool(installed) and not busy and bool(self.on_uninstall) and store.can_uninstall(self.result))

    def flash(self, state: str, text: str, ms: int = 2400):
        flash_action(self, self.action, state, text, ms)

    def set_similar(self, tiles):
        self.similar_title.setVisible(bool(tiles))
        self.similar.set_tiles(tiles)

    def _show_source(self, meta=None):
        from core import store
        meta = meta or {}
        facts = []
        where = store.install_source(self.result)
        link = store.source_link(self.result)
        if where:
            facts.append(("Source", f'<a href="{html.escape(link, quote=True)}">{html.escape(where)}</a>' if link
                          else html.escape(where)))
        dev = self.dev.text()
        if dev:
            facts.append(("Developer", html.escape(dev)))
        if meta.get("license"):
            facts.append(("Licence", html.escape(meta["license"])))
        homepage = meta.get("homepage") or ""
        if homepage.startswith("https://"):
            facts.append(("Website", f'<a href="{html.escape(homepage, quote=True)}">{html.escape(homepage)}</a>'))
        self.source.setText(" &nbsp;·&nbsp; ".join(f"<b>{k}</b> {v}" for k, v in facts))

    def _art(self, key, kind, path, meta):
        try:
            if kind == "icon" and key == self._key and path:
                pix = QPixmap(path)
                if not pix.isNull():
                    self.icon.setPixmap(rounded(pix, 84, 19))
                    self.hero.set_icon(rounded(pix, 96, 22))
            elif kind == "hero" and key == self._key:
                self.hero.set_meta(meta)
                pix = QPixmap(path) if path else QPixmap()
                if not pix.isNull() and self.selected == 0:
                    self.hero.set_shot(pix)
            elif kind == "meta" and key == self._key:
                self._meta(meta)
            elif kind == "shot" and key.startswith(self._key + "#shot"):
                i = int(key.rsplit("#shot", 1)[1])
                pix = QPixmap(path) if path else QPixmap()
                if i < len(self.shots) and not pix.isNull():
                    self.shots[i].setPixmap(pix.scaledToHeight(self.THUMB_H, Qt.SmoothTransformation))
            elif kind == "hero" and key.startswith(self._key + "#large"):
                i = int(key.rsplit("#large", 1)[1])
                pix = QPixmap(path) if path else QPixmap()
                if i == self.selected and not pix.isNull():
                    self.hero.set_shot(pix)
        except (RuntimeError, ValueError):
            pass

    def _select(self, i):
        self.selected = i
        pix = self.shots[i].pixmap()
        if pix is not None and not pix.isNull():
            self.hero.set_shot(pix)                   # at once; the full size follows
        if i < len(self.large):
            ArtLoader.get().request(f"{self._key}#large{i}", "hero", "", self.large[i], any_host=self._any_host,
                                    priority=True)

    def _meta(self, meta):
        if meta.get("developer") and not self.dev.text():
            self.dev.setText(meta["developer"])
        if meta.get("summary") and not self.about.text():
            self.about.setText(meta["summary"])
        if meta.get("license"):
            self.chips.insertWidget(self.chips.count() - 1, chip(meta["license"]))
        if meta.get("description"):
            self.description.setText(meta["description"])
            self.description.show()
        self._show_source(meta)
        urls = (meta.get("screenshots") or ([meta["screenshot"]] if meta.get("screenshot") else []))
        self.large = meta.get("shots_large") or []
        self._any_host = bool(meta.get("local"))
        if not urls:
            self.no_shots.setText("The publisher's metadata has no screenshots.")
            return
        self.no_shots.setText("")
        loader = ArtLoader.get()
        for i, u in enumerate(urls):
            lbl = _Thumb(lambda k=i: self._select(k))
            lbl.setFixedHeight(self.THUMB_H)
            lbl.setMinimumWidth(120)
            self.shots.append(lbl)
            self.gallery.addWidget(lbl)
            loader.request(f"{self._key}#shot{i}", "shot", "", u, any_host=self._any_host, priority=True)
        self.gallery.addStretch()
        self.gallery_box.setVisible(len(urls) > 0)
